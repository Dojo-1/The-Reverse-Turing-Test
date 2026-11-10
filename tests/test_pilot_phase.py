"""R5: preregistered phase transition with adversarial hidden-state controls.

Tests use fake time: they verify the game's state-machine invariants, not
provider independence, actual network delivery tolerance, or human outcomes.
"""
import unittest

from game.agents import Agent, AdapterError, ScriptedDemo
from game.engine import Game, RuleError


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, amount=45):
        self.t += amount


def ask_answer(game, clock, channel, *, role=None):
    game.act("conductor", "ask", {"channel": channel, "body": "Query to " + channel})
    game.act(role or ("machine_" + channel), "answer", {"body": "Endpoint answer"})
    clock.advance(45)
    game.view("conductor")


def start_pilot(game):
    game.act("controller", "configure_pilot", {})


def baseline(game, clock):
    ask_answer(game, clock, "A")
    ask_answer(game, clock, "B")


class LocalRole:
    def __init__(self, game, role):
        self.game = game
        self.role = role

    def view(self):
        return self.game.view(self.role)

    def act(self, action, **payload):
        self.game.act(self.role, action, payload)


class PhaseTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.game = Game(clock=self.clock)
        start_pilot(self.game)

    def test_pilot_configuration_is_atomic_and_must_precede_dialogue(self):
        view = self.game.view("controller")
        self.assertTrue(view["pilot_enabled"])
        self.assertEqual(view["pacing_seconds"], 45.0)
        self.assertEqual(view["links"], {"A_to_B": True, "B_to_A": True})
        self.assertEqual(view["pilot_phase"], "baseline")
        with self.assertRaises(RuleError):
            start_pilot(self.game)
        with self.assertRaises(RuleError):
            self.game.act("controller", "configure_pacing", {"seconds": 10})
        with self.assertRaises(RuleError):
            self.game.act("controller", "configure", {
                "links": {"A_to_B": False, "B_to_A": False}
            })
        with self.assertRaises(RuleError):
            self.game.act("controller", "random_intervene", {})

    def test_baseline_forces_one_question_to_each_genuine_machine(self):
        with self.assertRaises(RuleError):
            self.game.act("conductor", "ask", {"channel": "B", "body": "Wrong first"})
        ask_answer(self.game, self.clock, "A")
        with self.assertRaises(RuleError):
            self.game.act("conductor", "ask", {"channel": "A", "body": "Wrong second"})
        ask_answer(self.game, self.clock, "B")
        self.assertTrue(self.game.view("controller")["baseline_ready"])
        self.assertEqual(self.game.view("conductor")["pilot_phase"], "transition")
        with self.assertRaises(RuleError):
            self.game.act("conductor", "ask", {"channel": "A", "body": "Too early"})
        with self.assertRaises(RuleError):
            self.game.act("conductor", "verdict", {
                "p": {"no_human": .6, "human_A": .2, "human_B": .2}
            })
        self.assertEqual(self.game.view("controller")["pilot_question_count"], 2)

    def test_no_secret_change_leaks_until_public_resume(self):
        outputs = []
        for condition in Game.CONDITIONS:
            c = Clock()
            g = Game(clock=c)
            start_pilot(g)
            baseline(g, c)
            before = g.view("conductor")
            link_on = condition in ("unchanged", "humanA", "machineA")
            links = {"A_to_B": link_on, "B_to_A": link_on}
            g.act("controller", "intervene", {
                "condition": condition,
                "links": links,
                "human_gateway": condition in ("humanA", "humanB") and link_on,
            })
            after = g.view("conductor")
            self.assertEqual(before, after)
            self.assertEqual(after["pilot_phase"], "transition")
            self.assertNotIn("condition", after)
            self.assertNotIn("links", after)
            g.act("controller", "resume_pilot", {})
            resumed = g.view("conductor")
            self.assertEqual(resumed["pilot_phase"], "continuation")
            self.assertEqual(resumed["public"][-1]["kind"], "phase")
            outputs.append(resumed)
        for result in outputs[1:]:
            self.assertEqual(result, outputs[0])

    def test_gateway_and_binary_link_factors_are_enforced(self):
        baseline(self.game, self.clock)
        with self.assertRaises(RuleError):
            self.game.act("controller", "intervene", {
                "condition": "humanA",
                "links": {"A_to_B": True, "B_to_A": False},
                "human_gateway": False
            })
        with self.assertRaises(RuleError):
            self.game.act("controller", "intervene", {
                "condition": "humanA",
                "links": {"A_to_B": True, "B_to_A": True},
                "human_gateway": False
            })
        self.assertFalse(self.game.intervened)
        self.assertEqual(self.game.links, {"A_to_B": True, "B_to_A": True})
        self.game.act("controller", "intervene", {
            "condition": "humanA",
            "links": {"A_to_B": True, "B_to_A": True},
            "human_gateway": True
        })
        self.assertTrue(self.game.view("human")["can_whisper"])
        self.assertEqual(self.game.view("conductor")["pilot_phase"], "transition")
        self.game.act("controller", "resume_pilot", {})

    def test_exact_six_continuation_and_valid_verdict(self):
        baseline(self.game, self.clock)
        self.game.act("controller", "intervene", {
            "condition": "machineA",
            "links": {"A_to_B": False, "B_to_A": False},
            "human_gateway": False,
        })
        self.game.act("controller", "resume_pilot", {})
        for i in range(6):
            channel = "A" if i % 2 == 0 else "B"
            role = "replacement_A" if channel == "A" else "machine_B"
            ask_answer(self.game, self.clock, channel, role=role)
        self.assertEqual(self.game.view("conductor")["pilot_phase"], "verdict")
        self.assertEqual(self.game.view("controller")["pilot_question_count"], 8)
        with self.assertRaises(RuleError):
            self.game.act("conductor", "ask", {"channel": "B", "body": "Ninth"})
        self.game.act("conductor", "verdict", {
            "p": {"no_human": 0.6, "human_A": 0.2, "human_B": 0.2},
            "evidence": "Observed outcomes alone are not proof of identity",
        })
        self.assertTrue(self.game.view("controller")["pilot_valid_for_primary"])
        self.game.act("controller", "reveal", {})
        self.assertEqual(self.game.view("controller")["pilot_phase"], "revealed")
        self.assertEqual(self.game.view("conductor")["outcome"]["condition"], "machineA")
        self.assertEqual(self.game.export()["schema"], "reverse-turing-trial/v1")

    def test_nochange_control_requires_same_public_resume(self):
        baseline(self.game, self.clock)
        self.game.act("controller", "intervene", {
            "condition": "unchanged", "links": {"A_to_B": False, "B_to_A": False},
            "human_gateway": False
        })
        self.assertFalse(self.game.view("conductor")["pilot_phase"] == "continuation")
        self.game.act("controller", "resume_pilot", {})
        self.assertEqual(self.game.view("conductor")["public"][-1]["kind"], "phase")

    def test_cannot_move_identity_mid_pending_answer(self):
        ask_answer(self.game, self.clock, "A")
        self.game.act("conductor", "ask", {"channel": "B", "body": "Second"})
        with self.assertRaises(RuleError):
            self.game.act("controller", "intervene", {"condition": "humanB"})
        self.game.act("machine_B", "answer", {"body": "On time"})
        self.clock.advance(45)
        self.game.view("controller")
        self.game.act("controller", "intervene", {
            "condition": "humanB", "links": {"A_to_B": False, "B_to_A": False},
            "human_gateway": False
        })
        self.assertTrue(self.game.view("human")["active"])

    def test_missed_gate_marks_invalid_and_preserves_abort(self):
        self.game.act("conductor", "ask", {"channel": "A", "body": "One"})
        self.clock.advance(45)
        self.game.view("controller")
        self.assertEqual(self.game.public[-1]["kind"], "timeout")
        self.assertFalse(self.game.view("controller")["pilot_valid_for_primary"])
        with self.assertRaises(RuleError):
            self.game.act("controller", "resume_pilot", {})
        self.game.act("controller", "abort_pilot", {
            "reason": "Deadline missed in A baseline"
        })
        self.assertEqual(self.game.view("controller")["pilot_phase"], "aborted")
        self.assertEqual(self.game.view("controller")["pilot_abort_reason"],
                         "Deadline missed in A baseline")
        with self.assertRaises(RuleError):
            self.game.act("conductor", "ask", {"channel": "B", "body": "Forbidden"})
        self.assertTrue(any(x["kind"] == "abort_pilot" for x in self.game.export()["audit"]))
        with self.assertRaises(RuleError):
            self.game.act("controller", "reveal", {})

    def test_automated_conductor_waits_for_public_transition(self):
        agent = Agent(
            "conductor", LocalRole(self.game, "conductor"),
            ScriptedDemo(), question_budget=8
        )
        self.assertEqual(agent.step(), "asked")
        self.assertEqual(Agent(
            "machine_A", LocalRole(self.game, "machine_A"), ScriptedDemo()
        ).step(), "answered")
        self.clock.advance(45)
        self.game.view("conductor")
        self.assertEqual(agent.step(), "asked")
        self.assertEqual(Agent(
            "machine_B", LocalRole(self.game, "machine_B"), ScriptedDemo()
        ).step(), "answered")
        self.clock.advance(45)
        self.game.view("conductor")
        self.assertEqual(agent.step(), "waiting")
        self.game.act("controller", "intervene", {
            "condition": "unchanged", "links": {"A_to_B": True, "B_to_A": True},
            "human_gateway": False
        })
        self.assertEqual(agent.step(), "waiting")
        self.game.act("controller", "resume_pilot", {})
        self.assertEqual(agent.step(), "asked")

    def test_incorrect_conductor_budget_is_rejected_in_pilot(self):
        wrong = Agent("conductor", LocalRole(self.game, "conductor"),
                      ScriptedDemo(), question_budget=4)
        with self.assertRaises(AdapterError):
            wrong.step()

    def test_nonpilot_game_keeps_open_horizon(self):
        g = Game(clock=self.clock)
        self.assertIsNone(g.view("conductor")["pilot_phase"])
        g.act("conductor", "ask", {"channel": "B", "body": "Free-form start"})
        g.act("machine_B", "answer", {"body": "Immediate"})
        self.assertEqual(g.view("conductor")["public"][0]["channel"], "B")
        self.assertIsNone(g.view("controller")["pacing_seconds"])


if __name__ == "__main__":
    unittest.main()
