"""Independent invariants for the proposed (NOT executed) pilot schedule."""
from collections import Counter
import json
from pathlib import Path
import stat
import tempfile
import unittest

from experiments.pilot_schedule import (
    PROTOCOL, commitment, exclusive_json, generate, public_commitment,
)


class PilotScheduleTests(unittest.TestCase):
    def setUp(self):
        self.seed = "0123456789abcdef" * 4

    def test_reproducible_allocation_and_exact_balance(self):
        schedule = generate(self.seed)
        self.assertEqual(schedule, generate(self.seed))
        self.assertNotEqual(schedule["trials"], generate("abcdef0123456789" * 4)["trials"])
        self.assertEqual(schedule["protocol"], PROTOCOL)
        self.assertEqual(len(schedule["trials"]), 24)
        self.assertEqual(len({r["trial_id"] for r in schedule["trials"]}), 24)
        counts = Counter((r["origin"], r["link_after"]) for r in schedule["trials"])
        self.assertEqual(counts[("human", "on")], 5)
        self.assertEqual(counts[("human", "off")], 5)
        self.assertEqual(counts[("machine", "on")], 5)
        self.assertEqual(counts[("machine", "off")], 5)
        self.assertEqual(counts[("unchanged", "on")], 2)
        self.assertEqual(counts[("unchanged", "off")], 2)
        for origin in ("human", "machine"):
            self.assertEqual(sum(r["condition"] == origin + "A" for r in schedule["trials"]), 5)
            self.assertEqual(sum(r["condition"] == origin + "B" for r in schedule["trials"]), 5)
        self.assertEqual(sum(r["link_after"] == "on" for r in schedule["trials"]), 12)
        self.assertTrue(all(r["human_gateway"] == (
            r["origin"] == "human" and r["link_after"] == "on"
        ) for r in schedule["trials"]))

    def test_public_commitment_does_not_expose_secret_draw(self):
        record = generate(self.seed)
        public = public_commitment(record)
        self.assertEqual(public["sha256_seed_commitment"], commitment(self.seed))
        self.assertFalse(public["seed_revealed"])
        self.assertNotIn("trials", public)
        self.assertNotIn("seed", public)
        self.assertNotIn(self.seed, json.dumps(public))
        self.assertEqual(public["factorial_counts"]["unchanged/off"], 2)

    def test_exclusive_private_file_and_no_overwrite(self):
        record = generate(self.seed)
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private.json"
            public = Path(directory) / "commitment.json"
            exclusive_json(private, record, 0o600)
            exclusive_json(public, public_commitment(record), 0o644)
            self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o600)
            self.assertEqual(json.loads(private.read_text())["seed"], self.seed)
            self.assertNotIn(self.seed, public.read_text())
            with self.assertRaises(FileExistsError):
                exclusive_json(private, record, 0o600)

    def test_seed_format_rejected(self):
        for bad in ("", "not_hex" * 9, "0" * 63, "z" * 64):
            with self.subTest(seed=bad), self.assertRaises(ValueError):
                commitment(bad)


if __name__ == "__main__":
    unittest.main()
