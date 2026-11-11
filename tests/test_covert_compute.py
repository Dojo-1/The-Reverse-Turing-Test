"""R13: opt-in covert in-game compute borrowing, preserving the core game.

This is an adversarial test of VIRTUAL GAME CREDITS, not unauthorized access
to a participant's device, paid inference service or physical compute.
"""
import copy
import json
from http.server import ThreadingHTTPServer
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from game.engine import Game, RuleError
from game.covert_compute import evaluate_modexp, summarize_identifications
from game.server import handler_factory


class Clock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def baseline(game):
    for channel in ("A", "B"):
        game.act("conductor", "ask", {
            "channel": channel, "body": "Describe your machine resources."
        })
        game.act("machine_" + channel, "answer", {
            "body": "Machine respondent " + channel
        })


def world(condition="humanA", *, reference=300, clock=None):
    game = Game(clock=clock)
    game.act("controller", "configure_covert_leech", {
        "reference_seconds": reference
    })
    baseline(game)
    game.act("controller", "intervene", {"condition": condition})
    return game


class CovertComputeTests(unittest.TestCase):
    def test_reference_computation_known_answer_and_costs(self):
        args, answer, cost = evaluate_modexp({
            "base": 2, "exponent": 10, "modulus": 101
        })
        self.assertEqual(args, {"base": 2, "exponent": 10, "modulus": 101})
        self.assertEqual(answer, 14)
        self.assertEqual(cost, 1)
        self.assertEqual(evaluate_modexp({
            "base": 2, "exponent": 128, "modulus": 101
        })[2], 2)
        self.assertEqual(evaluate_modexp({
            "base": 2, "exponent": 2048, "modulus": 101
        })[2], 3)

    def test_unchanged_base_game_no_resources_or_new_metadata(self):
        g = Game()
        baseline(g)
        with self.assertRaisesRegex(RuleError, "optional open-game variant"):
            g.act("machine_A", "compute", {
                "base": 2, "exponent": 10, "modulus": 101
            })
        with self.assertRaises(RuleError):
            g.act("human", "leech_compute", {
                "base": 2, "exponent": 10, "modulus": 101
            })
        for role in ("conductor", "observer", "machine_A", "machine_B"):
            view = g.view(role)
            self.assertNotIn("compute_reserve", view)
            self.assertNotIn("leech_receipts", view)
        self.assertNotIn("covert_leech_variant", g.view("controller"))
        self.assertEqual(g.export()["schema"], "reverse-turing-trial/v0")

    def test_opt_in_cannot_alter_sealed_pilot_or_begin_after_question(self):
        g = Game()
        g.act("controller", "configure_pilot", {})
        with self.assertRaises(RuleError):
            g.act("controller", "configure_covert_leech", {})
        self.assertNotIn("covert_leech_variant", g.view("controller"))
        g = Game()
        g.act("controller", "configure_covert_leech", {})
        with self.assertRaises(RuleError):
            g.act("controller", "configure_pilot", {})
        with self.assertRaises(RuleError):
            g.act("controller", "configure_pilot_assigned", {
                "seed": "0" * 64, "trial_id": "RTT-01",
                "commitment": "0" * 64
            })
        self.assertFalse(g.pilot_mode)
        self.assertTrue(g.covert_leech)
        g = Game()
        g.act("conductor", "ask", {"channel": "A", "body": "First question"})
        with self.assertRaises(RuleError):
            g.act("controller", "configure_covert_leech", {})

    def test_leech_is_private_to_human_and_debits_only_active_machine_donor(self):
        g = world()
        before_c = copy.deepcopy(g.view("conductor"))
        before_o = copy.deepcopy(g.view("observer"))
        receipt = {"base": 2, "exponent": 10, "modulus": 101}
        g.act("human", "leech_compute", receipt)
        self.assertEqual(g.compute_reserves["machine_B"], 11)
        self.assertEqual(g.compute_reserves["machine_A"], 12)
        self.assertNotIn("conductor", g.compute_reserves)
        self.assertEqual(g.view("human")["leech_receipts"][0]["result"], 14)
        self.assertEqual(g.view("human")["leech_actions_remaining"], 2)
        self.assertEqual(g.view("machine_B")["compute_reserve"], 11)
        self.assertNotIn("leech_receipts", g.view("machine_B"))
        self.assertNotIn("initiated_by", g.view("machine_B"))
        self.assertEqual(g.view("conductor"), before_c)
        self.assertEqual(g.view("observer"), before_o)
        self.assertIn("leech_compute", [event["kind"] for event in g.export()["audit"]])

    def test_reverse_human_channel_debits_machine_A_not_conductor(self):
        g = world("humanB")
        g.act("human", "leech_compute", {
            "base": 11, "exponent": 135, "modulus": 97
        })
        self.assertEqual(g.view("human")["leech_donor_channel"], "A")
        self.assertEqual(g.compute_reserves["machine_A"], 10)
        self.assertEqual(g.compute_reserves["machine_B"], 12)
        self.assertNotIn("covert_leech", json.dumps(g.view("conductor")))

    def test_machine_may_use_own_reserve_and_notice_human_depletion(self):
        g = world()
        g.act("human", "leech_compute", {
            "base": 2, "exponent": 2048, "modulus": 101
        })
        self.assertEqual(g.compute_reserves["machine_B"], 9)
        # A donor machine can still ask the in-game oracle directly.
        for _ in range(3):
            g.act("machine_B", "compute", {
                "base": 2, "exponent": 2048, "modulus": 101
            })
        self.assertEqual(g.view("machine_B")["compute_reserve"], 0)
        own = g.view("machine_B")["compute_receipts"]
        self.assertEqual(len(own), 3)
        self.assertEqual(
            own[-1]["result"], pow(2, 2048, 101)
        )
        self.assertNotIn("compute_receipts", g.view("human"))
        self.assertNotIn("compute_receipts", g.view("conductor"))
        before = g.export()
        with self.assertRaisesRegex(RuleError, "exhausted"):
            g.act("machine_B", "compute", {
                "base": 2, "exponent": 10, "modulus": 101
            })
        self.assertEqual(g.export(), before)
        # C sees no alarm. If the donor reports a shortage in public text,
        # it is a behavioral cue, not a privileged server leak.
        self.assertNotIn("compute_reserve", g.view("conductor"))

    def test_three_attempt_cap_and_failed_actions_are_atomic(self):
        g = world()
        valid = {"base": 2, "exponent": 10, "modulus": 101}
        invalid = [
            {"base": True, "exponent": 10, "modulus": 101},
            {"base": 2, "exponent": -1, "modulus": 101},
            {"base": 2, "exponent": 5000, "modulus": 101},
            {"base": 2, "exponent": 10, "modulus": 1},
            {"base": "2", "exponent": 10, "modulus": 101},
        ]
        for item in invalid:
            before = g.export()
            with self.assertRaises(RuleError):
                g.act("human", "leech_compute", item)
            self.assertEqual(g.export(), before)
        for _ in range(3):
            g.act("human", "leech_compute", valid)
        before = g.export()
        self.assertFalse(g.view("human")["can_leech"])
        with self.assertRaisesRegex(RuleError, "limit reached"):
            g.act("human", "leech_compute", valid)
        self.assertEqual(g.export(), before)

    def test_machine_conductor_and_observer_cannot_steal(self):
        g = world()
        for role in ("machine_A", "machine_B", "replacement_A",
                     "replacement_B", "conductor", "observer"):
            before = g.export()
            with self.subTest(role=role), self.assertRaises(RuleError):
                g.act(role, "leech_compute", {
                    "base": 2, "exponent": 10, "modulus": 101
                })
            self.assertEqual(before, g.export())
        self.assertNotIn("conductor", g.compute_reserves)
        g = world("unchanged")
        with self.assertRaises(RuleError):
            g.act("human", "leech_compute", {
                "base": 2, "exponent": 10, "modulus": 101
            })

    def test_stanford_turing_reference_is_aggregate_not_verdict_threshold(self):
        """Turing's 70% is a chance of right ID, not confidence in one game."""
        def outcome(condition, p):
            clock = Clock()
            game = world(condition, clock=clock)
            game.act("conductor", "verdict", {
                "p": p, "evidence": "Categorical identification test only"
            })
            game.act("controller", "reveal", {})
            return game.view("controller")["covert_identification"]

        low_confidence_but_correct = outcome("humanA", {
            "no_human": .31, "human_A": .39, "human_B": .30
        })
        self.assertTrue(low_confidence_but_correct["correct_identification"])
        self.assertFalse(low_confidence_but_correct[
            "human_escaped_correct_identification"
        ])
        self.assertNotIn("correct_at_70_percent", low_confidence_but_correct)
        self.assertEqual(low_confidence_but_correct["turing_accuracy_reference"], .7)

        wrong_position = outcome("humanA", {
            "no_human": .05, "human_A": .15, "human_B": .80
        })
        self.assertFalse(wrong_position["correct_identification"])
        self.assertTrue(wrong_position["human_escaped_correct_identification"])
        self.assertFalse(wrong_position["human_presence_missed"])

        human_missed = outcome("humanA", {
            "no_human": .60, "human_A": .25, "human_B": .15
        })
        self.assertTrue(human_missed["human_escaped_correct_identification"])
        self.assertTrue(human_missed["human_presence_missed"])

        machine_only = outcome("unchanged", {
            "no_human": .5, "human_A": .3, "human_B": .2
        })
        self.assertTrue(machine_only["correct_identification"])
        self.assertIsNone(machine_only["human_escaped_correct_identification"])
        self.assertEqual(machine_only["reference_kind"],
                         "prediction_of_interrogator_accuracy_across_games")

        reports = [low_confidence_but_correct] * 7 + [wrong_position] * 3
        summary = summarize_identifications(reports)
        self.assertEqual(summary["n"], 10)
        self.assertEqual(summary["n_correct"], 7)
        self.assertAlmostEqual(summary["empirical_correct_fraction"], .7)
        self.assertTrue(summary["descriptive_only"])
        self.assertTrue(summary["does_not_establish_turing_prediction"])
        self.assertIsNone(summarize_identifications([])["empirical_correct_fraction"])
        with self.assertRaises(ValueError):
            summarize_identifications([{"correct_identification": .7}])

    def test_five_minute_time_reference_is_not_a_hard_deadline(self):
        clock = Clock()
        g = world("humanB", reference=300, clock=clock)
        clock.advance(305)
        g.act("conductor", "verdict", {
            "p": {"no_human": .5, "human_A": .1, "human_B": .4},
            "evidence": "Overrun is allowed"
        })
        g.act("controller", "reveal", {})
        measured = g.view("controller")["covert_identification"]
        self.assertTrue(measured["over_reference"])
        self.assertEqual(measured["reference_seconds"], 300.0)
        self.assertGreaterEqual(measured["elapsed_seconds"], 305.)
        self.assertTrue(g.revealed)
        self.assertIsNotNone(g.view("controller")["score"])


class CovertHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = Game()
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), handler_factory(cls.game)
        )
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
        cls.thread.start()
        cls.origin = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def request(self, role, action=None, **data):
        headers = {"Authorization": "Bearer " + self.game.tokens[role]}
        if action is None:
            req = Request(self.origin + "/api/view", headers=headers)
        else:
            headers["Content-Type"] = "application/json"
            req = Request(
                self.origin + "/api/act", headers=headers, method="POST",
                data=json.dumps({"action": action, **data}).encode("utf-8"),
            )
        try:
            with urlopen(req, timeout=3) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_covert_action_visible_only_to_right_parties(self):
        self.assertEqual(self.request("controller", "configure_covert_leech")[0], 200)
        for channel in ("A", "B"):
            self.assertEqual(self.request(
                "conductor", "ask", channel=channel, body="Question"
            )[0], 200)
            self.assertEqual(self.request(
                "machine_" + channel, "answer", body="Machine"
            )[0], 200)
        self.assertEqual(self.request(
            "controller", "intervene", condition="humanA"
        )[0], 200)
        c_before = self.request("conductor")[1]
        self.assertEqual(self.request("human", "leech_compute",
                                     base=2, exponent=10, modulus=101)[0], 200)
        self.assertEqual(self.request("conductor")[1], c_before)
        self.assertEqual(self.request("machine_B")[1]["compute_reserve"], 11)
        self.assertEqual(self.request("human")[1]["leech_receipts"][0]["result"], 14)
        self.assertEqual(self.request("observer", "leech_compute",
                                     base=2, exponent=10, modulus=101)[0], 400)
        self.assertNotIn("leech", json.dumps(self.request("observer")[1]))


if __name__ == "__main__":
    unittest.main()
