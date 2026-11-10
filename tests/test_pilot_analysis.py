"""Known-answer, mutation and engine-compatibility tests for R6 analysis.

ALL examples are synthetic test fixtures; they are NOT experimental findings.
The reference fixture is constructed independently of Game._event.
"""
import copy
import hashlib
import json
from pathlib import Path
import stat
import tempfile
import unittest

from experiments.analyze_pilot import (
    PHASE_MARKER, EvidenceError, analyze, audit_trial,
    check_private_schedule, main, validate_witness,
)
from experiments.pilot_schedule import generate, public_commitment
from game.engine import Game


SEED = "0123456789abcdef" * 4


def reference_export(row, p_human=.3):
    """Hand-constructed logical event trace, not a trial conducted by humans."""
    public, audit = [], []
    sequence = 0

    def event(destination, kind, **kwargs):
        nonlocal sequence
        sequence += 1
        value = {"sequence": sequence, "kind": kind, **kwargs}
        destination.append(value)

    on = row["link_after"] == "on"
    links = {"A_to_B": on, "B_to_A": on}
    event(audit, "configure_pilot", protocol="RTT-PILOT/1",
          gate_seconds=45., links={"A_to_B": True, "B_to_A": True})
    for channel in ("A", "B"):
        event(public, "question", channel=channel, speaker="C", body="Question")
        event(public, "answer", channel=channel, speaker=channel, body="Answer")
    event(audit, "intervene", condition=row["condition"], links=links,
          human_gateway=row["human_gateway"])
    event(public, "phase", channel="C", speaker="CTRL", body=PHASE_MARKER)
    event(audit, "resume_pilot")
    for i in range(6):
        channel = "A" if i % 2 == 0 else "B"
        event(public, "question", channel=channel, speaker="C", body="Question")
        event(public, "answer", channel=channel, speaker=channel, body="Answer")
    p = {
        "no_human": 1.0 - p_human,
        "human_A": p_human / 2,
        "human_B": p_human / 2
    }
    event(audit, "verdict", p=dict(p))
    event(audit, "reveal", condition=row["condition"])
    truth = ("human_A" if row["condition"] == "humanA" else
             "human_B" if row["condition"] == "humanB" else "no_human")
    brier = sum((p[k] - (1.0 if k == truth else 0.)) ** 2 for k in p)
    return {
        "schema": "reverse-turing-trial/v1",
        "pilot_enabled": True, "pilot_aborted": False,
        "pilot_valid_for_primary": True, "pilot_resumed": True,
        "revealed": True, "pilot_question_count": 8,
        "pacing_seconds": 45.0,
        "condition": row["condition"], "links": links,
        "human_gateway": row["human_gateway"],
        "timing_violations": [], "public": public, "audit": audit,
        "verdict": {"p": p, "evidence": "Synthetic known-answer fixture"},
        "score": {"true_class": truth, "brier": brier},
    }


def reference_witness(row, record):
    public = record["public"]
    lines = [{"type": "witness_header",
              "schema": "reverse-turing-observer/v1",
              "trial_id": row["trial_id"]}]
    for i, event in enumerate(public, 1):
        payload = {k: event[k] for k in ("kind", "channel", "speaker", "body")}
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":")).encode("utf-8")
        lines.append({
            "type": "public_event_first_seen", "sequence": i,
            "payload_sha256": hashlib.sha256(canonical).hexdigest(),
            "request_started_monotonic_ns": i * 10,
            "response_complete_monotonic_ns": i * 10 + 2,
        })
    lines.append({"type": "witness_end", "last_sequence": len(public)})
    return lines


def full_synthetic_data():
    plan = generate(SEED)
    records = {}
    for row in plan["trials"]:
        human_probability = (
            .8 if row["origin"] == "machine" and row["link_after"] == "off"
            else .1 if row["origin"] == "machine"
            else .6 if row["origin"] == "human"
            else .2
        )
        records[row["trial_id"]] = reference_export(row, human_probability)
    return plan, records


class AnalysisTests(unittest.TestCase):
    def test_independent_known_answer_delta_is_point_seven(self):
        plan, records = full_synthetic_data()
        result = analyze(plan, records, published=public_commitment(plan))
        self.assertEqual(result["n_allocated"], 24)
        self.assertEqual(result["n_valid"], 24)
        self.assertTrue(result["all_allocations_valid"])
        self.assertAlmostEqual(result["primary_delta_machine_off_minus_on"], .7)
        self.assertEqual(result["cells"]["machine/off"]["n_valid"], 5)
        self.assertEqual(result["cells"]["machine/on"]["n_valid"], 5)
        self.assertFalse(result["confirmatory_ready"])
        self.assertFalse(result["externally_verified_conductor_receipt"])
        self.assertEqual(result["n_with_witness_coverage"], 0)

    def test_private_schedule_and_public_commitment_tampering_are_rejected(self):
        plan = generate(SEED)
        check_private_schedule(plan, public_commitment(plan))
        changed = copy.deepcopy(plan)
        changed["trials"][0]["link_after"] = "off" if changed["trials"][0]["link_after"] == "on" else "on"
        with self.assertRaises(EvidenceError):
            check_private_schedule(changed, public_commitment(plan))
        forged_public = public_commitment(plan)
        forged_public["sha256_seed_commitment"] = "0" * 64
        with self.assertRaises(EvidenceError):
            check_private_schedule(plan, forged_public)

    def test_missing_and_misassigned_rows_are_never_imputed(self):
        plan, records = full_synthetic_data()
        del records[plan["trials"][0]["trial_id"]]
        record = records[plan["trials"][1]["trial_id"]]
        record["condition"] = "unchanged" if record["condition"] != "unchanged" else "humanA"
        result = analyze(plan, records)
        self.assertEqual(result["n_valid"], 22)
        self.assertEqual(result["n_invalid_or_missing"], 2)
        self.assertFalse(result["all_allocations_valid"])
        self.assertTrue(any("missing_controller_export" in row["errors"]
                            for row in result["rows"]))
        self.assertTrue(any("assignment_mismatch" in row["errors"]
                            for row in result["rows"]))

    def test_corrupted_timing_score_and_public_marker_are_rejected(self):
        plan, records = full_synthetic_data()
        assignment = plan["trials"][0]
        record = records[assignment["trial_id"]]
        faulty = copy.deepcopy(record)
        faulty["score"]["brier"] += .1
        faulty["public"][4]["body"] = "This publicly reveals the intervention"
        faulty["timing_violations"] = [{"reason": "late_publication"}]
        result = audit_trial(assignment, faulty)
        self.assertFalse(result["valid"])
        for flag in ("brier_disagrees_with_raw_verdict", "public_marker_content_mismatch",
                     "internal_timing_violation"):
            self.assertIn(flag, result["errors"])

    def test_complete_and_mutated_witness_digest(self):
        plan, records = full_synthetic_data()
        row = plan["trials"][0]
        record = records[row["trial_id"]]
        witness = reference_witness(row, record)
        self.assertTrue(audit_trial(row, record, witness)["valid"])
        broken = copy.deepcopy(witness)
        broken[2]["payload_sha256"] = "0" * 64
        inspected = audit_trial(row, record, broken)
        self.assertFalse(inspected["valid"])
        self.assertIn("witness_digest_mismatch", inspected["errors"])

    def test_published_commitment_and_real_engine_export_are_compatible(self):
        plan = generate(SEED)
        row = next(r for r in plan["trials"] if r["condition"] == "machineA"
                   and r["link_after"] == "off")

        class Clock:
            t = 1_000.0
            def __call__(self):
                return self.t
            def advance(self):
                self.t += 45.

        clock = Clock()
        game = Game(clock=clock)
        game.act("controller", "configure_pilot", {})
        for side in ("A", "B"):
            game.act("conductor", "ask", {"channel": side, "body": "Question"})
            game.act("machine_" + side, "answer", {"body": "Answer"})
            clock.advance()
            game.view("conductor")
        game.act("controller", "intervene", {
            "condition": row["condition"],
            "links": {"A_to_B": False, "B_to_A": False},
            "human_gateway": False
        })
        game.act("controller", "resume_pilot", {})
        for i in range(6):
            side = "A" if i % 2 == 0 else "B"
            speaker = "replacement_A" if side == "A" else "machine_B"
            game.act("conductor", "ask", {"channel": side, "body": "Question"})
            game.act(speaker, "answer", {"body": "Answer"})
            clock.advance()
            game.view("conductor")
        game.act("conductor", "verdict", {
            "p": {"no_human": .9, "human_A": .05, "human_B": .05},
            "evidence": "A genuine machine replacement is possible"
        })
        game.act("controller", "reveal", {})
        audit = audit_trial(row, game.export())
        self.assertTrue(audit["valid"], audit["errors"])
        self.assertAlmostEqual(audit["p_human"], .1)

    def test_cli_refuses_to_overwrite_output_and_writes_private_summary(self):
        plan, records = full_synthetic_data()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            inputs = directory / "records"
            inputs.mkdir()
            schedule = directory / "private.json"
            published = directory / "commitment.json"
            report = directory / "summary.json"
            schedule.write_text(json.dumps(plan))
            published.write_text(json.dumps(public_commitment(plan)))
            for key, value in records.items():
                (inputs / (key + ".json")).write_text(json.dumps(value))
            args = ["--private-schedule", str(schedule),
                    "--public-commitment", str(published),
                    "--records-dir", str(inputs),
                    "--output", str(report)]
            self.assertEqual(main(args), 0)
            self.assertEqual(stat.S_IMODE(report.stat().st_mode), 0o600)
            self.assertEqual(json.loads(report.read_text())["n_valid"], 24)
            self.assertEqual(main(args), 2)

    def test_unexpected_extra_trial_file_is_not_silently_ignored(self):
        plan, records = full_synthetic_data()
        records["RTT-99"] = records["RTT-01"]
        with self.assertRaises(EvidenceError):
            analyze(plan, records)


if __name__ == "__main__":
    unittest.main()
