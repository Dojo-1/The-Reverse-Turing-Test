"""R11: adversarial non-study rehearsal tests.

One fast real localhost HTTP smoke test uses scripted model responses. The
eight-question pilot tests use a deliberately synthetic injected clock and
are NOT timing measurements or genuine-model inference. Model providers are
never called in CI.
"""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.rehearse_models import (
    RehearsalError, run_rehearsal, validate_config, main
)
from game.agents import ScriptedDemo


class FakeClock:
    def __init__(self):
        self.now = 1000.

    def __call__(self):
        return self.now

    def advance(self, delta):
        self.now += 45.


def config_for(roles):
    return {"roles": {
        role: {
            "endpoint": "http://127.0.0.1:1234/v1/chat/completions",
            "model": "explicit-local-non-study-model-" + role,
            "max_output_tokens": 256,
        }
        for role in roles
    }}


class ConfigurationTests(unittest.TestCase):
    def test_local_endpoints_and_secret_free_schemas(self):
        roles = ("conductor", "machine_A", "machine_B", "replacement_A")
        specs = validate_config(config_for(roles), roles)
        self.assertEqual(set(specs), set(roles))
        self.assertEqual(specs["conductor"]["max_output_tokens"], 256)
        for role in roles:
            self.assertNotIn("api_key", specs[role])
            self.assertIsNone(specs[role]["api_key_env"])
        forged = config_for(roles)
        forged["roles"]["machine_A"]["api_key"] = "DO_NOT_EMBED"
        with self.assertRaises(RehearsalError):
            validate_config(forged, roles)
        forged = config_for(roles)
        forged["roles"]["machine_A"]["endpoint"] = "http://not-local.example/v1/chat/completions"
        with self.assertRaises(RehearsalError):
            validate_config(forged, roles)
        forged = config_for(roles)
        forged["roles"]["machine_A"]["endpoint"] = "https://secret:pass@api.example.com/v1/chat/completions"
        with self.assertRaises(RehearsalError):
            validate_config(forged, roles)
        forged = config_for(roles)
        forged["roles"]["replacement_B"] = forged["roles"].pop("replacement_A")
        with self.assertRaises(RehearsalError):
            validate_config(forged, roles)

    def test_does_not_create_output_dir_for_invalid_config_or_role(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "invalid"
            with self.assertRaises(RehearsalError):
                run_rehearsal(
                    outdir=p, provider="compatible", model_map={"roles": {}},
                    mode="smoke", gate_seconds=1
                )
            self.assertFalse(p.exists())
            p = Path(td) / "RTT-01"
            with self.assertRaises(RehearsalError):
                run_rehearsal(
                    outdir=p, provider="scripted", mode="smoke",
                    gate_seconds=1
                )
            self.assertFalse(p.exists())

    def test_missing_model_api_key_stops_and_preserves_partial_manifest(self):
        roles = ("conductor", "machine_A", "machine_B", "replacement_A")
        spec = config_for(roles)
        spec["roles"]["machine_A"]["api_key_env"] = "RTT_NONEXISTENT_R11_KEY"
        with patch.dict(os.environ, {"RTT_NONEXISTENT_R11_KEY": ""}):
            with tempfile.TemporaryDirectory() as td:
                folder = Path(td) / "missing_key"
                result = run_rehearsal(
                    outdir=folder, provider="compatible", model_map=spec,
                    mode="smoke", gate_seconds=1, max_wall_seconds=15
                )
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["errors"][0]["kind"], "RehearsalError")
                self.assertIn("model credential", result["errors"][0]["detail"])
                self.assertFalse(result["confirmatory_ready"])
                self.assertTrue((folder / "controller.json").exists())
                self.assertTrue((folder / "manifest.json").exists())
                # C's receipt file is opened before the next role's
                # credential check. Retaining an explicitly incomplete
                # file is more faithful than pretending no attempt began.
                self.assertTrue((folder / "conductor.jsonl").exists())
                lines = [
                    json.loads(line) for line in
                    (folder / "conductor.jsonl").read_text(
                        encoding="utf-8").splitlines()
                ]
                self.assertEqual(lines[-1]["status"], "incomplete")
                self.assertFalse(result["delivery"]["within_one_second_given_same_clock"])

    def test_private_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "existing"
            p.mkdir()
            with self.assertRaises(FileExistsError):
                run_rehearsal(
                    outdir=p, provider="scripted", mode="smoke",
                    gate_seconds=1
                )


class ScriptedRehearsalTests(unittest.TestCase):
    def test_actual_local_http_smoke_produces_controller_and_c_receipt_logs(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "scripted_http"
            result = run_rehearsal(
                outdir=p, provider="scripted",
                mode="smoke", condition="machineA", link_after="off",
                gate_seconds=1., poll_seconds=.1, max_wall_seconds=30
            )
            self.assertEqual(result["status"], "completed", result["errors"])
            self.assertEqual(result["provider"], "scripted")
            self.assertEqual(result["human_participants"], 0)
            self.assertFalse(result["is_preregistered_trial"])
            self.assertEqual(result["clock_source"], "OS_monotonic")
            self.assertEqual(result["model_call_count"], 9)
            self.assertTrue(result["delivery"]["within_one_second_given_same_clock"],
                            result["delivery"]["errors"])
            export = json.loads((p / "controller.json").read_text(encoding="utf-8"))
            self.assertEqual(export["schema"], "reverse-turing-trial/v0")
            self.assertEqual(export["condition"], "machineA")
            self.assertEqual(len([e for e in export["public"] if e["kind"] == "question"]), 4)
            self.assertEqual(len(export["private"]), 2)
            calls = json.loads((p / "model_calls.json").read_text(encoding="utf-8"))
            self.assertEqual(len(calls), 9)
            self.assertFalse(any("api_key" in json.dumps(call) for call in calls))
            self.assertTrue((p / "conductor.jsonl").exists())
            self.assertFalse(result["confirmatory_ready"])

    def test_8q_synthetic_clock_pilot_checks_phase_barrier_but_not_latency(self):
        for link_after in ("on", "off"):
            for condition in ("unchanged", "machineA", "machineB"):
                clock = FakeClock()
                with self.subTest(condition=condition, links=link_after):
                    with tempfile.TemporaryDirectory() as td:
                        p = Path(td) / "clock_fixture"
                        result = run_rehearsal(
                            outdir=p, provider="scripted", condition=condition,
                            link_after=link_after,
                            mode="unbound-pilot", gate_seconds=45,
                            poll_seconds=.1, max_wall_seconds=20,
                            clock=clock, sleeper=clock.advance
                        )
                        self.assertEqual(result["status"], "completed", result["errors"])
                        self.assertEqual(result["model_call_count"], 17)
                        self.assertEqual(result["actual_private_message_count"],
                                         8 if link_after == "on" else 2)
                        self.assertFalse(result["delivery"]["within_one_second_given_same_clock"])
                        self.assertIn("synthetic_clock_not_comparable_to_conductor",
                                      result["delivery"]["errors"])
                        export = json.loads((p / "controller.json").read_text(encoding="utf-8"))
                        self.assertEqual(export["pilot_phase"], "revealed")
                        self.assertEqual(export["pilot_question_count"], 8)
                        self.assertFalse(export["pilot_schedule_bound"])
                        self.assertTrue(export["pilot_valid_for_primary"])
                        self.assertEqual(export["condition"], condition)

    def test_scripted_mock_failure_preserves_partial_abort_without_verdict(self):
        class FailingDemo:
            def complete(self, messages):
                if "TASK:QUESTION" in messages[-1]["content"]:
                    return "What is your origin?"
                raise RuntimeError("injected mock provider failure")
        with tempfile.TemporaryDirectory() as td, patch(
            "experiments.rehearse_models.ScriptedDemo", FailingDemo
        ):
            p = Path(td) / "failed_stub"
            result = run_rehearsal(
                outdir=p, provider="scripted", mode="unbound-pilot",
                gate_seconds=45, clock=FakeClock(),
                sleeper=lambda seconds: None,
                max_wall_seconds=10,
            )
            self.assertEqual(result["status"], "failed")
            self.assertIn("injected mock", result["errors"][0]["detail"])
            export = json.loads((p / "controller.json").read_text(encoding="utf-8"))
            self.assertTrue(export["pilot_aborted"])
            self.assertIsNone(export["verdict"])
            self.assertFalse(export["pilot_valid_for_primary"])
            self.assertTrue((p / "model_calls.json").exists())

    def test_cli_requires_provider_and_never_counts_scripted_as_study(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "cli_scripted"
            out = main([
                "--output-dir", str(folder), "--provider", "scripted",
                "--mode", "smoke", "--gate-seconds", "1",
                "--max-wall-seconds", "20"
            ])
            self.assertEqual(out, 0)
            self.assertFalse(json.loads(
                (folder / "manifest.json").read_text()
            )["confirmatory_ready"])


if __name__ == "__main__":
    unittest.main()
