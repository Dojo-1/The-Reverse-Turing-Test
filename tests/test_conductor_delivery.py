"""R8 regression tests. Synthetic timing fixtures and one real loopback relay.

The physical loopback test measures only the local software transport. It is
NOT an independent C-side observer, human experiment or model evaluation.
"""
import copy
import hashlib
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
import os
import stat
import tempfile
import time
import unittest
from unittest.mock import patch

from experiments.check_conductor_delivery import assess_delivery, main
from game.agents import AdapterError, Agent, RelayClient, ScriptedDemo, main as actor_main
from game.conductor_receipt import ConductorReceipt
from game.engine import Game
from game.server import handler_factory, run_release_worker


def payload_hash(event):
    blob = json.dumps(
        {k: event[k] for k in ("kind", "channel", "speaker", "body")},
        ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def one_turn_fixture(*, lag_ms=100., answered=True):
    """Independent hand-constructed one-question reference oracle.

    Use a fake common monotonic clock at 100 seconds (not real participants).
    """
    kind = "answer" if answered else "timeout"
    public = [
        {"sequence": 2, "kind": "question", "channel": "A",
         "speaker": "C", "body": "Why identify your origin?"},
        {"sequence": 5, "kind": kind, "channel": "A",
         "speaker": "A", "body": "Observable evidence only"},
    ]
    release = {
        "kind": "paced_release", "question_sequence": 2,
        "channel": "A", "submitted": answered,
        "released_at_monotonic": 100.0,
        "nominal_due_monotonic": 100.0,
    }
    controller = {
        "schema": "reverse-turing-trial/v0", "pacing_seconds": 1.0,
        "public": public, "audit": [release],
        "timing_violations": [],
    }
    start1, end1 = 99_000_000_000, 99_005_000_000
    start2, end2 = 99_500_000_000, int(100_000_000_000 + lag_ms * 1e6)
    public_reads = []
    for i, event in enumerate(public, 1):
        public_reads.append({
            "type": "public_event_first_seen",
            "sequence": i,
            "payload_sha256": payload_hash(event),
            "request_started_monotonic_ns": start2,
            "response_complete_monotonic_ns": end2,
        })
    trace = [
        {"type": "conductor_receipt_header",
         "schema": "reverse-turing-conductor-receipt/v1",
         "role": "conductor", "trial_id": "REHEARSAL-01"},
        {"type": "conductor_poll",
         "request_started_monotonic_ns": start1,
         "response_complete_monotonic_ns": end1,
         "public_event_count": 0},
        {"type": "conductor_poll",
         "request_started_monotonic_ns": start2,
         "response_complete_monotonic_ns": end2,
         "public_event_count": 2},
        *public_reads,
        {"type": "conductor_receipt_end", "status": "rehearsal",
         "last_sequence": 2},
    ]
    return controller, trace


class OfflineDeliveryTests(unittest.TestCase):
    def test_known_answer_timely_receipt_and_units(self):
        controller, trace = one_turn_fixture(lag_ms=125)
        report = assess_delivery(controller, trace, require_complete_pilot=False)
        self.assertEqual(report["errors"], [], report["errors"])
        self.assertTrue(report["within_one_second_given_same_clock"])
        self.assertAlmostEqual(report["max_delivery_lag_ms"], 125)
        self.assertEqual(report["n_paced_responses"], 1)
        self.assertFalse(report["confirmatory_ready"])

    def test_tardy_delivery_and_clock_mismatch_fail(self):
        for ms, flag in (
            (1600, "conductor_receipt_exceeds_one_second"),
            (-400, "negative_delivery_lag_or_clock_domain_mismatch"),
        ):
            with self.subTest(ms=ms):
                controller, trace = one_turn_fixture(lag_ms=ms)
                report = assess_delivery(controller, trace, require_complete_pilot=False)
                self.assertFalse(report["within_one_second_given_same_clock"])
                self.assertIn(flag, report["errors"])

    def test_tampered_message_and_missing_poll_fail(self):
        controller, trace = one_turn_fixture()
        modified = copy.deepcopy(trace)
        modified[3]["payload_sha256"] = "0" * 64
        report = assess_delivery(controller, modified, require_complete_pilot=False)
        self.assertIn("conductor_event_digest_mismatch", report["errors"])
        modified = copy.deepcopy(trace)
        del modified[2]
        report = assess_delivery(controller, modified, require_complete_pilot=False)
        self.assertIn("conductor_event_not_from_logged_poll", report["errors"])

    def test_missing_respondent_and_premature_trial_claim_fail(self):
        controller, trace = one_turn_fixture(answered=False)
        report = assess_delivery(controller, trace, require_complete_pilot=False)
        self.assertIn("server_answer_deadline_missed", report["errors"])
        controller, trace = one_turn_fixture()
        report = assess_delivery(controller, trace, require_complete_pilot=True)
        self.assertFalse(report["within_one_second_given_same_clock"])
        self.assertIn("not_strict_pilot_export", report["errors"])
        self.assertIn("pilot_needs_eight_paced_answers", report["errors"])

    def test_cannot_hide_ending_or_start_after_existing_transcript(self):
        controller, trace = one_turn_fixture()
        missing_end = trace[:-1]
        report = assess_delivery(controller, missing_end, require_complete_pilot=False)
        self.assertIn("receipt_end_missing", report["errors"])
        delayed = copy.deepcopy(trace)
        delayed[1]["public_event_count"] = 1
        report = assess_delivery(controller, delayed, require_complete_pilot=False)
        self.assertIn("conductor_log_started_after_public_events", report["errors"])

    def test_duplicate_controller_sequences_are_rejected(self):
        controller, trace = one_turn_fixture()
        controller["public"][1]["sequence"] = controller["public"][0]["sequence"]
        report = assess_delivery(controller, trace, require_complete_pilot=False)
        self.assertIn("controller_public_payload_invalid", report["errors"])
        self.assertFalse(report["within_one_second_given_same_clock"])

    def test_cli_refuses_to_overwrite_and_records_negative_control(self):
        controller, trace = one_turn_fixture(lag_ms=1800)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cf = root / "controller.json"
            rf = root / "receipt.jsonl"
            output = root / "delivery.json"
            cf.write_text(json.dumps(controller), encoding="utf-8")
            rf.write_text("\n".join(json.dumps(r) for r in trace), encoding="utf-8")
            argv = [
                "--controller-export", str(cf),
                "--conductor-receipt", str(rf),
                "--output", str(output), "--rehearsal",
            ]
            self.assertEqual(main(argv), 2)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(report["within_one_second_given_same_clock"])
            self.assertFalse(report["confirmatory_ready"])
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            self.assertEqual(main(argv), 2)


class ConductorClientTests(unittest.TestCase):
    def test_model_receives_only_original_view_without_timing_metadata(self):
        class Model:
            def __init__(self):
                self.calls = []
            def complete(self, messages):
                self.calls.append(messages)
                return "What is your observable origin evidence?"
        class Relay:
            def __init__(self):
                self.actions = []
            def view(self):
                return {
                    "role": "conductor", "public": [], "pilot_phase": None,
                    "verdict": None, "revealed": False, "outcome": None,
                }
            def act(self, action, **kwargs):
                self.actions.append((action, kwargs))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "C.jsonl"
            model = Model()
            original = Relay()
            measured = ConductorReceipt(
                original, path, "LOCAL-UNIT", poll_seconds=0.25
            )
            try:
                self.assertEqual(
                    Agent("conductor", measured, model, question_budget=2).step(),
                    "asked"
                )
            finally:
                measured.close("rehearsal")
            prompt = json.dumps(model.calls)
            self.assertNotIn("monotonic", prompt)
            self.assertNotIn("request_started", prompt)
            self.assertNotIn("response_complete", prompt)
            self.assertNotIn("receipt", prompt)
            self.assertEqual(original.actions[0][0], "ask")
            self.assertIn("conductor_poll", path.read_text(encoding="utf-8"))

    def test_conductor_only_cli_flags_fail_closed(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ, {"RTT_ROLE_TOKEN": "dummy-not-used-for-network"}
        ):
            path = str(Path(td) / "C.jsonl")
            forbidden = actor_main([
                "--role", "machine_A", "--provider", "scripted",
                "--trial-id", "RTT-01", "--receipt-log", path,
            ])
            self.assertEqual(forbidden, 2)
            incomplete = actor_main([
                "--role", "conductor", "--provider", "scripted",
                "--receipt-log", path,
            ])
            self.assertEqual(incomplete, 2)
            self.assertFalse(Path(path).exists())


    def test_real_local_relay_conductor_poll_is_measured_in_same_client(self):
        game = Game()
        http = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(game))
        http_worker = Thread(target=http.serve_forever, daemon=True)
        http_worker.start()
        stop = Event()
        timer_worker = Thread(target=run_release_worker, args=(game, stop, 0.01),
                              daemon=True)
        timer_worker.start()
        base = "http://127.0.0.1:" + str(http.server_port)
        try:
            with tempfile.TemporaryDirectory() as td:
                receipt_path = Path(td) / "C.jsonl"
                c = RelayClient(base, game.tokens["conductor"])
                instrumented = ConductorReceipt(
                    c, receipt_path, "REHEARSAL-LOCAL", poll_seconds=0.1,
                )
                try:
                    game.act("controller", "configure_pacing", {"seconds": 1})
                    conductor = Agent(
                        "conductor", instrumented, ScriptedDemo(),
                        question_budget=2,
                    )
                    respondent = Agent(
                        "machine_A", RelayClient(base, game.tokens["machine_A"]),
                        ScriptedDemo(),
                    )
                    self.assertEqual(conductor.step(), "asked")
                    self.assertEqual(respondent.step(), "answered")
                    first = instrumented.view()
                    self.assertEqual(first["public"][-1]["kind"], "question")
                    deadline = time.monotonic() + 3
                    found = False
                    while time.monotonic() < deadline:
                        v = instrumented.view()
                        if v["public"][-1]["kind"] == "answer":
                            found = True
                            break
                        time.sleep(0.05)
                    self.assertTrue(found, "Background release did not become visible")
                    self.assertEqual(len(game.public), 2)
                    self.assertEqual(game.view("controller")["timing_violations"], [])
                finally:
                    instrumented.close(status="rehearsal")
                trace = [
                    json.loads(line) for line in receipt_path.read_text(
                        encoding="utf-8").splitlines()
                ]
                audit = assess_delivery(game.export(), trace,
                                        require_complete_pilot=False)
                self.assertTrue(audit["within_one_second_given_same_clock"],
                                audit["errors"])
                self.assertGreaterEqual(audit["max_delivery_lag_ms"], 0)
                self.assertLess(audit["max_delivery_lag_ms"], 1000)
                self.assertEqual(trace[0]["trial_id"], "REHEARSAL-LOCAL")
                self.assertEqual(trace[-1]["status"], "rehearsal")
                self.assertNotIn("Bearer ", receipt_path.read_text())
                self.assertNotIn(game.tokens["conductor"], receipt_path.read_text())
        finally:
            stop.set()
            timer_worker.join(timeout=2)
            http.shutdown()
            http.server_close()
            http_worker.join(timeout=2)

    def test_no_prior_events_allowed_and_no_log_overwrite(self):
        class FakeRelay:
            calls = []
            def view(self):
                return {"role": "conductor", "public": [
                    {"sequence": 1, "kind": "question", "channel": "A",
                     "speaker": "C", "body": "Too late"}
                ]}
            def act(self, action, **data):
                self.calls.append((action, data))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "receipt.jsonl"
            receipt = ConductorReceipt(
                FakeRelay(), path, "TRIAL", poll_seconds=0.25,
            )
            with self.assertRaises(AdapterError):
                receipt.view()
            receipt.close(status="error")
            with self.assertRaises(AdapterError):
                ConductorReceipt(FakeRelay(), path, "TRIAL", poll_seconds=0.25)

    def test_non_conductor_cannot_use_attested_view_writer(self):
        class FakeRelay:
            def view(self):
                return {"role": "respondent", "public": []}
            def act(self, action, **data):
                pass
        with tempfile.TemporaryDirectory() as td:
            receipt = ConductorReceipt(
                FakeRelay(), Path(td) / "w.jsonl", "TRIAL", poll_seconds=0.25,
            )
            with self.assertRaises(AdapterError):
                receipt.view()
            receipt.close(status="error")


if __name__ == "__main__":
    unittest.main()
