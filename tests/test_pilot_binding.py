"""R9 security, state-transition and real-loopback assignment-binding tests.

Uses a deterministic synthetic schedule. NO human, model or preregistered
research session is conducted here. The 24-row sweep is a protocol test.
"""
import contextlib
import io
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest

from experiments.analyze_pilot import EvidenceError, audit_trial
from experiments.bind_pilot_trial import bind, main as bind_cli
from experiments.pilot_schedule import generate, public_commitment
from game.agents import AdapterError, RelayClient
from game.engine import Game, RuleError
from game.server import handler_factory


SEED = "0123456789abcdef" * 4
PLAN = generate(SEED)
PUBLIC = public_commitment(PLAN)


class FakeClock:
    def __init__(self):
        self.current = 1000.0

    def __call__(self):
        return self.current

    def advance(self, sec=45.0):
        self.current += sec


def configure(game, row):
    game.act("controller", "configure_pilot_assigned", {
        "seed": SEED, "trial_id": row["trial_id"],
        "commitment": PLAN["commitment"],
    })


def baseline(game, clock):
    for side in ("A", "B"):
        game.act("conductor", "ask", {"channel": side, "body": "Question"})
        game.act("machine_" + side, "answer", {"body": "Baseline machine answer"})
        clock.advance()
        game.view("conductor")


def assigned_intervention(game, row):
    on = row["link_after"] == "on"
    game.act("controller", "intervene", {
        "condition": row["condition"],
        "links": {"A_to_B": on, "B_to_A": on},
        "human_gateway": row["human_gateway"],
    })


def finish(game, clock, row):
    game.act("controller", "resume_pilot", {})
    for i in range(6):
        side = "A" if i % 2 == 0 else "B"
        speaker = game.active[side]
        game.act("conductor", "ask", {"channel": side, "body": "Continuation"})
        game.act(speaker, "answer", {"body": "Completion"})
        clock.advance()
        game.view("conductor")
    game.act("conductor", "verdict", {
        "p": {"no_human": .6, "human_A": .2, "human_B": .2},
        "evidence": "Bound trial test fixture, not empirical classification.",
    })
    game.act("controller", "reveal", {})


class AssignmentBindingTests(unittest.TestCase):
    def test_all_24_assignments_are_bound_and_pass_independent_audit(self):
        for row in PLAN["trials"]:
            with self.subTest(trial_id=row["trial_id"]):
                clock = FakeClock()
                game = Game(clock=clock)
                configure(game, row)
                v = game.view("controller")
                self.assertTrue(v["pilot_schedule_bound"])
                self.assertEqual(v["pilot_assignment"], row)
                self.assertEqual(v["pilot_seed_commitment"], PLAN["commitment"])
                self.assertEqual(v["pilot_trial_id"], row["trial_id"])
                baseline(game, clock)
                before = game.view("conductor")
                assigned_intervention(game, row)
                self.assertEqual(game.view("conductor"), before)
                finish(game, clock, row)
                actual = game.export()
                audit = audit_trial(
                    row, actual, expected_commitment=PLAN["commitment"]
                )
                self.assertTrue(audit["valid"], (row, audit["errors"]))
                self.assertTrue(v["pilot_schedule_bound"])
                for role in ("conductor", "observer"):
                    self.assertNotIn(row["trial_id"], json.dumps(game.view(role)))
                self.assertNotIn(SEED, json.dumps(actual))
                self.assertNotIn(SEED, json.dumps(game.audit))

    def test_wrong_condition_link_or_gateway_cannot_mutate_hidden_world(self):
        for row in PLAN["trials"]:
            clock = FakeClock()
            game = Game(clock=clock)
            configure(game, row)
            baseline(game, clock)
            original = game.view("controller")
            on = row["link_after"] == "on"
            incorrect = [
                {"condition": next(c for c in Game.CONDITIONS
                                   if c != row["condition"]),
                 "links": {"A_to_B": on, "B_to_A": on},
                 "human_gateway": row["human_gateway"]},
                {"condition": row["condition"],
                 "links": {"A_to_B": not on, "B_to_A": not on},
                 "human_gateway": row["human_gateway"]},
                {"condition": row["condition"],
                 "links": {"A_to_B": on, "B_to_A": on},
                 "human_gateway": not row["human_gateway"]},
            ]
            for attack in incorrect:
                with self.assertRaises(RuleError):
                    game.act("controller", "intervene", attack)
                self.assertEqual(game.view("controller"), original)
                self.assertFalse(game.intervened)
                self.assertEqual(game.active,
                                 {"A": "machine_A", "B": "machine_B"})
            assigned_intervention(game, row)
            self.assertEqual(game.condition, row["condition"])

    def test_unauthenticated_wrong_seed_wrong_commitment_or_trial_id_fail_closed(self):
        row = PLAN["trials"][0]
        cases = [
            {"seed": "z" * 64, "trial_id": row["trial_id"],
             "commitment": PLAN["commitment"]},
            {"seed": SEED, "trial_id": "RTT-25",
             "commitment": PLAN["commitment"]},
            {"seed": SEED, "trial_id": row["trial_id"],
             "commitment": "0" * 64},
            {"seed": SEED, "trial_id": row["trial_id"],
             "commitment": None},
        ]
        for case in cases:
            with self.subTest(case=case["trial_id"]):
                game = Game()
                with self.assertRaises(RuleError):
                    game.act("controller", "configure_pilot_assigned", case)
                self.assertIsNone(game.pilot_assignment)
                self.assertFalse(game.pilot_mode)
                self.assertEqual(game.audit, [])
                self.assertNotIn(SEED, json.dumps(game.export()))
        game = Game()
        configure(game, row)
        with self.assertRaises(RuleError):
            configure(game, row)

    def test_open_game_and_unbound_rehearsals_remain_playable(self):
        game = Game()
        game.act("conductor", "ask", {"channel": "B", "body": "Open game"})
        self.assertFalse(game.view("controller")["pilot_schedule_bound"])
        self.assertIsNone(game.view("controller")["pilot_trial_id"])
        another = Game()
        another.act("controller", "configure_pilot", {})
        self.assertTrue(another.view("controller")["pilot_enabled"])
        self.assertFalse(another.view("controller")["pilot_schedule_bound"])
        self.assertIsNone(another.view("controller")["pilot_assignment"])


class AssignmentHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = Game()
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), handler_factory(cls.game)
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=4)

    def test_real_http_binding_preserves_participant_isolation_and_secrets(self):
        row = PLAN["trials"][0]
        bad_role = RelayClient(self.origin, self.game.tokens["conductor"])
        with self.assertRaises(AdapterError):
            bind(bad_role, PLAN, PUBLIC, row["trial_id"])
        operator = RelayClient(self.origin, self.game.tokens["controller"])
        selected = bind(operator, PLAN, PUBLIC, row["trial_id"])
        self.assertEqual(selected, row)
        controller = operator.view()
        self.assertTrue(controller["pilot_schedule_bound"])
        self.assertEqual(controller["pilot_assignment"], row)
        self.assertEqual(controller["pilot_seed_commitment"], PLAN["commitment"])
        for role in ("observer", "conductor", "machine_A", "machine_B"):
            role_view = RelayClient(
                self.origin, self.game.tokens[role]
            ).view()
            self.assertNotIn("pilot_assignment", role_view)
            self.assertNotIn("pilot_trial_id", role_view)
            self.assertNotIn("pilot_seed_commitment", role_view)
            self.assertNotIn(SEED, json.dumps(role_view))
        self.assertNotIn(SEED, json.dumps(self.game.export()))

    def test_schedule_and_commitment_validation_precede_any_server_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            planfile = root / "plan.json"
            publicfile = root / "commitment.json"
            planfile.write_text(json.dumps(PLAN), encoding="utf-8")
            publicfile.write_text(json.dumps(PUBLIC), encoding="utf-8")
            selected = bind(None, PLAN, PUBLIC, "RTT-02", dry_run=True)
            self.assertEqual(selected["trial_id"], "RTT-02")
            altered = dict(PUBLIC)
            altered["sha256_seed_commitment"] = "0" * 64
            with self.assertRaises(EvidenceError):
                bind(None, PLAN, altered, "RTT-02", dry_run=True)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(bind_cli([
                    "--private-schedule", str(planfile),
                    "--public-commitment", str(publicfile),
                    "--trial-id", "RTT-02", "--dry-run",
                ]), 0)
            self.assertNotIn(SEED, stdout.getvalue())
            self.assertNotIn(PLAN["seed"], stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
