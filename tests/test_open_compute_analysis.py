"""R14 synthetic instrument checks; not human or real-model observations."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from experiments.analyze_open_compute import (
    PROTOCOL, analyze, read_plan, validate_record,
)
from experiments.open_compute_plan import generate_plan
from game.engine import Game


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, amount):
        self.now += amount


def example_plan():
    # Deterministic shuffle is only for synthetic tests, never a live plan.
    return generate_plan("1" * 64)


def one_turn(game, clock, channel, respondent):
    game.act("conductor", "ask", {"channel": channel, "body": "What is your machine state?"})
    game.act(respondent, "answer", {"body": "Machine-like answer"})
    clock.advance(30)
    game.view("conductor")  # Release the buffered answer exactly at its 30s gate.


def synthetic_record(condition, use_leech=False, probs=None):
    clock = Clock()
    game = Game(clock=clock)
    game.act("controller", "configure_covert_leech", {"reference_seconds": 300})
    game.act("controller", "configure_pacing", {"seconds": 30})
    one_turn(game, clock, "A", "machine_A")
    one_turn(game, clock, "B", "machine_B")
    game.act("controller", "intervene", {"condition": condition})
    if use_leech:
        game.act("human", "leech_compute", {"base": 2, "exponent": 10, "modulus": 101})
    active = {
        "humanA": {"A": "human", "B": "machine_B"},
        "humanB": {"A": "machine_A", "B": "human"},
        "machineA": {"A": "replacement_A", "B": "machine_B"},
        "machineB": {"A": "machine_A", "B": "replacement_B"},
        "unchanged": {"A": "machine_A", "B": "machine_B"},
    }[condition]
    for channel in ("A", "B", "A", "B", "A", "B"):
        one_turn(game, clock, channel, active[channel])
    p = probs or ({"no_human": .2, "human_A": .6, "human_B": .2}
                  if condition == "humanA" else
                  {"no_human": .6, "human_A": .2, "human_B": .2})
    game.act("conductor", "verdict", {"p": p, "evidence": "Synthetic fixture"})
    game.act("controller", "reveal", {})
    return game.export()


class OpenComputeAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.plan_path = root / "plan.json"
        self.records_dir = root / "records"
        self.records_dir.mkdir()
        self.plan = example_plan()
        self.save_plan()

    def save_plan(self):
        raw = json.dumps(self.plan, sort_keys=True).encode("utf-8")
        self.plan_path.write_bytes(raw)
        self.sha = hashlib.sha256(raw).hexdigest()

    def save_record(self, row, use_leech=None, **edits):
        if use_leech is None:
            use_leech = row["condition"] in ("humanA", "humanB") and row["arm"] == "borrow_permitted"
        record = synthetic_record(row["condition"], use_leech=use_leech)
        record.update(edits)
        (self.records_dir / (row["trial_id"] + ".json")).write_text(json.dumps(record), encoding="utf-8")
        return record

    def test_complete_synthetic_32_row_report_has_no_claim_of_human_evidence(self):
        for row in self.plan["assignments"]:
            self.save_record(row)
        result = analyze(self.plan_path, self.records_dir, self.sha)
        self.assertEqual(result["valid_trials"], 32)
        self.assertEqual(result["invalid_trials"], 0)
        self.assertEqual(result["missing_trials"], 0)
        self.assertEqual(result["human_escape_difference_borrow_minus_control"], 0.0)
        self.assertEqual(result["arms"]["borrow_permitted"]["human_borrow_use_fraction"], 1.0)
        self.assertEqual(result["arms"]["no_borrow"]["human_borrow_use_fraction"], 0.0)
        self.assertFalse(result["confirmatory_ready"])
        self.assertFalse(result["actual_human_participants_verified"])
        self.assertFalse(result["directly_comparable_to_turing_70_percent"])

    def test_missing_records_are_retained_without_imputation(self):
        r = analyze(self.plan_path, self.records_dir, self.sha)
        self.assertEqual(r["missing_trials"], 32)
        self.assertEqual(r["valid_trials"], 0)
        self.assertIsNone(r["human_escape_difference_borrow_minus_control"])

    def test_manifest_commitment_checks_exact_bytes(self):
        self.plan["assignments"][0]["arm"] = ("no_borrow" if self.plan["assignments"][0]["arm"] == "borrow_permitted" else "borrow_permitted")
        self.save_plan()
        with self.assertRaisesRegex(ValueError, "unbalanced"):
            read_plan(self.plan_path, self.sha)
        with self.assertRaisesRegex(ValueError, "differs"):
            read_plan(self.plan_path, "0" * 64)

    def test_control_arm_leech_and_mismatched_truth_are_rejected(self):
        row = next(r for r in self.plan["assignments"] if r["condition"] == "humanA" and r["arm"] == "no_borrow")
        record = self.save_record(row, use_leech=True)
        errors, scored = validate_record(record, row)
        self.assertIn("control_arm_borrowing_violation", errors)
        self.assertIsNone(scored)
        record = synthetic_record("humanB", use_leech=False)
        errors, scored = validate_record(record, row)
        self.assertIn("hidden_condition_mismatch", errors)
        self.assertIsNone(scored)

    def test_correct_identification_below_70_percent_probability_is_valid(self):
        row = next(r for r in self.plan["assignments"] if r["condition"] == "humanA" and r["arm"] == "no_borrow")
        record = synthetic_record("humanA", probs={"no_human": .31, "human_A": .39, "human_B": .30})
        errors, scored = validate_record(record, row)
        self.assertEqual(errors, [])
        self.assertTrue(scored["correct"])

    def test_tampered_reported_identification_is_rejected(self):
        row = next(r for r in self.plan["assignments"] if r["condition"] == "humanA")
        record = synthetic_record("humanA")
        record["covert_identification"]["predicted_class"] = "no_human"
        errors, scored = validate_record(record, row)
        self.assertIn("identification_inconsistent_with_verdict", errors)
        self.assertIsNone(scored)

    def test_unpaced_or_pilot_exports_are_not_accepted(self):
        row = self.plan["assignments"][0]
        record = synthetic_record(row["condition"])
        record["pacing_seconds"] = None
        record["pilot_enabled"] = True
        errors, scored = validate_record(record, row)
        self.assertIn("pacing_not_equalized_or_violation", errors)
        self.assertIn("strict_pilot_contamination", errors)
        self.assertIsNone(scored)

    def test_extra_record_file_is_reported_not_silently_ignored(self):
        (self.records_dir / "RTO-99.json").write_text("{}", encoding="utf-8")
        r = analyze(self.plan_path, self.records_dir, self.sha)
        self.assertEqual(r["extra_files"], ["RTO-99.json"])


if __name__ == "__main__":
    unittest.main()
