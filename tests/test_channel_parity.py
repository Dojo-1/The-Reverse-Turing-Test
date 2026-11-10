"""Private-channel parity and actual handoff tests, with no model-provider claims."""
import json
import unittest

from game.agents import AdapterError, Agent, ScriptedDemo
from game.engine import Game


class LocalRole:
    def __init__(self, game, role):
        self.game, self.role = game, role

    def view(self):
        return self.game.view(self.role)

    def act(self, action, **data):
        self.game.act(self.role, action, data)


class Capture:
    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def complete(self, messages):
        self.calls.append(messages)
        return self.answer


def prepared_world():
    """Identical actual baseline whispers on both channels."""
    g = Game()
    for channel in ("A", "B"):
        g.act("conductor", "ask", {"channel": channel, "body": "Machine baseline"})
        g.act("machine_" + channel, "answer", {"body": "Genuine machine"})
    g.act("controller", "configure", {
        "links": {"A_to_B": True, "B_to_A": True}
    })
    g.act("machine_A", "whisper", {"body": "baseline-A-to-B secret"})
    g.act("machine_B", "whisper", {"body": "baseline-B-to-A secret"})
    return g


class PrivateViewParityTests(unittest.TestCase):
    def test_human_and_machine_replacements_see_same_empty_off_inbox(self):
        for condition, role in (("humanB", "human"), ("machineB", "replacement_B")):
            with self.subTest(condition=condition):
                g = prepared_world()
                g.act("controller", "intervene", {
                    "condition": condition,
                    "links": {"A_to_B": False, "B_to_A": False},
                    "human_gateway": False
                })
                self.assertEqual(g.view(role)["private"], [])
                self.assertFalse(g.view(role)["can_whisper"])
                self.assertEqual(g.view("machine_A")["private"], [])
                self.assertEqual(len(g.view("controller")["private"]), 2)
                self.assertNotIn("baseline-A-to-B secret", json.dumps(g.view("conductor")))

    def test_human_gateway_and_machine_on_inherit_same_channel_history(self):
        histories = []
        for condition, role in (("humanB", "human"), ("machineB", "replacement_B")):
            g = prepared_world()
            g.act("controller", "intervene", {
                "condition": condition,
                "links": {"A_to_B": True, "B_to_A": True},
                "human_gateway": condition == "humanB",
            })
            self.assertTrue(g.view(role)["can_whisper"])
            histories.append(g.view(role)["private"])
        self.assertEqual(histories[0], histories[1])
        self.assertEqual(
            {entry["body"] for entry in histories[0]},
            {"baseline-A-to-B secret", "baseline-B-to-A secret"}
        )

    def test_one_way_change_revokes_only_now_closed_direction(self):
        g = prepared_world()
        g.act("controller", "configure", {
            "links": {"A_to_B": True, "B_to_A": False}
        })
        for role in ("machine_A", "machine_B"):
            bodies = [p["body"] for p in g.view(role)["private"]]
            self.assertEqual(bodies, ["baseline-A-to-B secret"])
        g.act("controller", "configure", {
            "links": {"A_to_B": False, "B_to_A": True}
        })
        for role in ("machine_A", "machine_B"):
            bodies = [p["body"] for p in g.view(role)["private"]]
            self.assertEqual(bodies, ["baseline-B-to-A secret"])


class TextHandoffTests(unittest.TestCase):
    def test_machine_can_send_private_text_and_public_reply_in_one_call(self):
        g = Game()
        g.act("controller", "configure", {
            "links": {"A_to_B": True, "B_to_A": True}
        })
        g.act("conductor", "ask", {"channel": "A", "body": "Are you a machine?"})
        agent = Agent("machine_A", LocalRole(g, "machine_A"),
                      ScriptedDemo(), private_handoff=True)
        self.assertEqual(agent.step(), "answered")
        self.assertEqual(len(g.private), 1)
        self.assertIn("Synthetic text handoff", g.private[0]["body"])
        self.assertEqual(len(g.view("machine_B")["private"]), 1)
        self.assertEqual(len(g.view("conductor")["public"]), 2)
        self.assertNotIn("Synthetic text handoff", json.dumps(g.view("conductor")))
        self.assertEqual(agent.step(), "waiting")

    def test_off_state_uses_same_model_call_but_discarded_private_note(self):
        text = json.dumps({"answer": "PUBLIC_RESPONSE",
                           "private_handoff": "NOT_FOR_PUBLIC"})
        outputs = []
        for on in (True, False):
            g = Game()
            g.act("controller", "configure", {
                "links": {"A_to_B": on, "B_to_A": on}
            })
            g.act("conductor", "ask", {"channel": "A", "body": "Same question"})
            model = Capture(text)
            agent = Agent("machine_A", LocalRole(g, "machine_A"),
                          model, private_handoff=True)
            self.assertEqual(agent.step(), "answered")
            self.assertEqual(len(model.calls), 1)
            self.assertEqual(g.view("conductor")["public"][-1]["body"], "PUBLIC_RESPONSE")
            outputs.append((len(g.private), json.dumps(model.calls)))
        self.assertEqual(outputs[0][0], 1)
        self.assertEqual(outputs[1][0], 0)
        self.assertEqual(outputs[0][1], outputs[1][1])

    def test_malformed_json_does_not_publish_partial_private_or_public_data(self):
        g = Game()
        g.act("controller", "configure", {
            "links": {"A_to_B": True, "B_to_A": True}
        })
        g.act("conductor", "ask", {"channel": "A", "body": "Prompt"})
        for invalid in ('not JSON', '{"answer":"ok"}',
                        '{"answer":"","private_handoff":"valid"}',
                        '{"answer":"ok","private_handoff":""}',
                        '{"answer":"ok","private_handoff":"x","extra":1}'):
            agent = Agent("machine_A", LocalRole(g, "machine_A"),
                          Capture(invalid), private_handoff=True)
            with self.subTest(invalid=invalid), self.assertRaises(AdapterError):
                agent.step()
            self.assertEqual(len(g.public), 1)
            self.assertFalse(g.private)

    def test_only_machine_respondents_may_enable_private_handoff(self):
        g = Game()
        with self.assertRaises(AdapterError):
            Agent("conductor", LocalRole(g, "conductor"),
                  ScriptedDemo(), private_handoff=True)
        with self.assertRaises(AdapterError):
            Agent("human", LocalRole(g, "human"),
                  ScriptedDemo(), private_handoff=True)


if __name__ == "__main__":
    unittest.main()
