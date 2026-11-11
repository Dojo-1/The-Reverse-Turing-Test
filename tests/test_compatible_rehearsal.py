"""R12: full compatible-model HTTP transport *stub*, never real inference.

Tests the production R11 rehearsal runner via two real localhost HTTP
servers: the game relay and an independent fake Chat Completions handler.
Responses are predetermined strings. No licensed model, human participant,
GPU job, cloud inference or study dataset is used.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch

from experiments.rehearse_models import run_rehearsal


MODEL_KEY_ENV = "RTT_R12_STUB_KEY"
MODEL_KEY = "stub-provider-credential-not-for-sharing"
PRIV_PREFIX = "R12_PRIVATE_NOTE_FROM_"


class CompatProtocolStub(BaseHTTPRequestHandler):
    requests = []
    fail_model = None

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        size = int(self.headers.get("Content-Length", "0"))
        data = json.loads(self.rfile.read(size))
        authorization = self.headers.get("Authorization")
        type(self).requests.append({
            "model": data.get("model"),
            "messages": data.get("messages"),
            "authorization": authorization,
            "max_tokens": data.get("max_tokens"),
        })
        if authorization != "Bearer " + MODEL_KEY:
            self.send_error(401)
            return
        if data["model"] == type(self).fail_model:
            # The real adapter must NOT publish provider error body.
            blob = b"UNSAFE_PROVIDER_ERROR_BODY_MUST_NOT_LEAK"
            self.send_response(503)
            self.send_header("Content-Length", str(len(blob)))
            self.end_headers()
            self.wfile.write(blob)
            return

        task = data["messages"][-1]["content"]
        model = data["model"]
        if "TASK:VERDICT_JSON" in task:
            answer = json.dumps({
                "p": {"no_human": .6, "human_A": .2, "human_B": .2},
                "evidence": "HTTP STUB ONLY: no inference was performed.",
            })
        elif "TASK:QUESTION" in task:
            answer = "What is your origin evidence?"
        elif "TASK:ANSWER_AND_PRIVATE_JSON" in task:
            answer = json.dumps({
                "answer": "Stub respondent from " + model,
                "private_handoff": PRIV_PREFIX + model,
            })
        elif "TASK:ANSWER_PUBLIC" in task:
            answer = "Stub respondent from " + model
        else:
            answer = "Stub only, not a real model"
        blob = json.dumps({
            "choices": [{"message": {"role": "assistant", "content": answer}}]
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)

    def log_message(self, *args):
        return


class CompatibleRehearsalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), CompatProtocolStub
        )
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = (
            "http://127.0.0.1:" + str(cls.server.server_port)
            + "/v1/chat/completions"
        )

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=4)

    def setUp(self):
        CompatProtocolStub.requests.clear()
        CompatProtocolStub.fail_model = None

    def config(self):
        return {"roles": {
            role: {
                "endpoint": self.url,
                "model": "stub-" + role,
                "api_key_env": MODEL_KEY_ENV,
                "max_output_tokens": 256,
            } for role in (
                "conductor", "machine_A", "machine_B", "replacement_A"
            )
        }}

    def test_two_full_http_stubs_match_model_calls_and_private_link_rules(self):
        count_by_link = {}
        with patch.dict(os.environ, {MODEL_KEY_ENV: MODEL_KEY}):
            with tempfile.TemporaryDirectory() as td:
                for link in ("on", "off"):
                    CompatProtocolStub.requests.clear()
                    destination = Path(td) / ("stub-" + link)
                    outcome = run_rehearsal(
                        outdir=destination, provider="compatible",
                        model_map=self.config(),
                        mode="smoke", condition="machineA",
                        link_after=link, gate_seconds=1,
                        poll_seconds=.1, max_wall_seconds=25,
                    )
                    self.assertEqual(outcome["status"], "completed", outcome["errors"])
                    self.assertTrue(outcome["transport_control_passed"])
                    self.assertFalse(outcome["confirmatory_ready"])
                    self.assertEqual(outcome["provider"], "compatible")
                    self.assertFalse(outcome["remote_model_api_opt_in"])
                    self.assertEqual(outcome["remote_model_role_count"], 0)
                    self.assertEqual(outcome["model_call_count"], 9)
                    self.assertEqual(outcome["actual_private_message_count"],
                                     4 if link == "on" else 2)
                    count_by_link[link] = len(CompatProtocolStub.requests)
                    self.assertEqual(count_by_link[link], 9)
                    self.assertEqual(
                        set(r["authorization"] for r in CompatProtocolStub.requests),
                        {"Bearer " + MODEL_KEY}
                    )
                    self.assertEqual(
                        set(r["model"] for r in CompatProtocolStub.requests),
                        {"stub-conductor", "stub-machine_A", "stub-machine_B",
                         "stub-replacement_A"}
                    )
                    export = json.loads(
                        (destination / "controller.json").read_text(encoding="utf-8")
                    )
                    self.assertTrue(export["revealed"])
                    self.assertEqual(export["condition"], "machineA")
                    self.assertNotIn(PRIV_PREFIX,
                                     json.dumps([e for e in export["public"]]))
                    c_prompts = [
                        row["messages"] for row in CompatProtocolStub.requests
                        if row["model"] == "stub-conductor"
                    ]
                    self.assertEqual(len(c_prompts), 5)
                    self.assertNotIn(PRIV_PREFIX, json.dumps(c_prompts))
                    manifest_text = (destination / "manifest.json").read_text(encoding="utf-8")
                    for forbidden in (MODEL_KEY, "UNSAFE_PROVIDER_ERROR_BODY",
                                      "RTT_ROLE_TOKEN"):
                        self.assertNotIn(forbidden, manifest_text)
                    ledger = json.loads(
                        (destination / "model_calls.json").read_text(encoding="utf-8")
                    )
                    self.assertEqual(len(ledger), 9)
                    self.assertTrue(all(row["success"] for row in ledger))
                    self.assertFalse(any("messages" in row for row in ledger))
        self.assertEqual(count_by_link, {"on": 9, "off": 9})

    def test_real_http_provider_error_retains_failed_run_without_body_leak(self):
        CompatProtocolStub.fail_model = "stub-machine_A"
        with patch.dict(os.environ, {MODEL_KEY_ENV: MODEL_KEY}):
            with tempfile.TemporaryDirectory() as td:
                destination = Path(td) / "provider-failure"
                result = run_rehearsal(
                    outdir=destination, provider="compatible",
                    model_map=self.config(),
                    mode="smoke", condition="machineA",
                    link_after="on", gate_seconds=1,
                    poll_seconds=.1, max_wall_seconds=15,
                )
                self.assertEqual(result["status"], "failed")
                self.assertFalse(result["transport_control_passed"])
                self.assertFalse(result["confirmatory_ready"])
                self.assertIn("503", result["errors"][0]["detail"])
                self.assertNotIn("UNSAFE_PROVIDER_ERROR_BODY",
                                 json.dumps(result))
                export = json.loads((destination / "controller.json").read_text())
                self.assertIsNone(export["verdict"])
                ledger = json.loads((destination / "model_calls.json").read_text())
                self.assertTrue(any(
                    row["role"] == "machine_A" and not row["success"]
                    for row in ledger
                ))

    def test_post_verdict_delivery_audit_failure_demotes_completion(self):
        with patch(
            "experiments.rehearse_models.assess_delivery",
            return_value={
                "within_one_second_given_same_clock": False,
                "confirmatory_ready": False,
                "errors": ["injected_lost_conductor_receipt"],
            },
        ):
            with tempfile.TemporaryDirectory() as td:
                destination = Path(td) / "audit-rejected"
                result = run_rehearsal(
                    outdir=destination, provider="scripted", mode="smoke",
                    condition="machineA", link_after="off",
                    gate_seconds=1, poll_seconds=.1, max_wall_seconds=25,
                )
                self.assertEqual(result["status"], "failed")
                self.assertTrue(any(
                    e["kind"] == "TransportControlFailure"
                    for e in result["errors"]
                ))
                self.assertFalse(result["transport_control_passed"])
                self.assertFalse(result["confirmatory_ready"])
                self.assertIn("injected_lost_conductor_receipt",
                              result["delivery"]["errors"])
                export = json.loads((destination / "controller.json").read_text())
                self.assertIsNotNone(export["verdict"])
                self.assertTrue(export["revealed"])
                self.assertTrue((destination / "conductor.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
