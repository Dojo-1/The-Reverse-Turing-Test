"""R10: atomic model handoff/answer controls and request-count parity.

Self-authored software tests. These do not validate model-provider compute
parity or create empirical human/machine trial observations.
"""
import json
from http.server import ThreadingHTTPServer
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from game.agents import Agent, ScriptedDemo
from game.engine import Game, RuleError
from game.server import handler_factory


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class RecordingRole:
    def __init__(self, game, role):
        self.game = game
        self.role = role
        self.actions = []

    def view(self):
        return self.game.view(self.role)

    def act(self, action, **data):
        self.actions.append((action, dict(data)))
        self.game.act(self.role, action, data)


class CapturingModel:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def complete(self, messages):
        self.calls.append(messages)
        return self.response


def configured(on, *, paced=False):
    clock = FakeClock()
    game = Game(clock=clock)
    if paced:
        game.act("controller", "configure_pacing", {"seconds": 10})
    game.act("controller", "configure", {
        "links": {"A_to_B": on, "B_to_A": on}
    })
    game.act("conductor", "ask", {
        "channel": "A", "body": "Question identical in all conditions"
    })
    return game, clock


class AtomicHandoffTests(unittest.TestCase):
    def test_link_on_and_off_use_equal_request_and_model_call_counts(self):
        observed = []
        for enabled in (True, False):
            with self.subTest(link_on=enabled):
                game, _ = configured(enabled)
                role = RecordingRole(game, "machine_A")
                model = CapturingModel(json.dumps({
                    "answer": "public answer",
                    "private_handoff": "private generated note",
                }))
                agent = Agent(
                    "machine_A", role, model, private_handoff=True
                )
                self.assertEqual(agent.step(), "answered")
                self.assertEqual(len(model.calls), 1)
                self.assertEqual([action for action, _ in role.actions], ["respond"])
                self.assertEqual(len(game.public), 2)
                self.assertEqual(game.public[-1]["body"], "public answer")
                self.assertEqual(len(game.private), 1 if enabled else 0)
                self.assertNotIn("private generated note", json.dumps(game.view("conductor")))
                ledger = [
                    x for x in game.audit if x["kind"] == "atomic_response"
                ]
                self.assertEqual(len(ledger), 1)
                self.assertEqual(ledger[0]["private_transmitted"], enabled)
                self.assertEqual(ledger[0]["private_discarded"], not enabled)
                observed.append(model.calls)
        self.assertEqual(observed[0], observed[1])

    def test_validation_failure_never_commits_partial_private_text(self):
        for body, note in (
            ("", "private note"), ("answer", ""), ("answer", None),
            ("answer", 4), ("x" * 2001, "private"),
            ("answer", "x" * 2001),
        ):
            with self.subTest(body=repr(body)[:22], note=repr(note)[:22]):
                game, _ = configured(True, paced=True)
                before = game.export()
                with self.assertRaises(RuleError):
                    game.act("machine_A", "respond", {
                        "body": body, "private_handoff": note
                    })
                self.assertEqual(game.export(), before)

    def test_rejection_of_duplicate_answer_does_not_transmit_second_note(self):
        game, _ = configured(True, paced=True)
        game.act("machine_A", "respond", {
            "body": "first", "private_handoff": "FIRST SECRET"
        })
        before = game.export()
        with self.assertRaises(RuleError):
            game.act("machine_A", "respond", {
                "body": "second", "private_handoff": "SECOND SECRET"
            })
        self.assertEqual(game.export(), before)
        self.assertEqual([p["body"] for p in game.private], ["FIRST SECRET"])

    def test_expired_gate_never_allows_last_second_private_only_transfer(self):
        game, clock = configured(True, paced=True)
        clock.advance(10)
        with self.assertRaises(RuleError):
            game.act("machine_A", "respond", {
                "body": "too late", "private_handoff": "MUST NOT ARRIVE"
            })
        self.assertEqual(game.private, [])
        self.assertEqual(game.public[-1]["kind"], "timeout")
        self.assertFalse(any(x["kind"] == "atomic_response" for x in game.audit))
        self.assertEqual(game.timing_violations[0]["reason"], "deadline_miss")

    def test_inactive_actor_cannot_transmit_even_with_valid_note(self):
        game, _ = configured(True)
        game.act("machine_A", "answer", {"body": "baseline A"})
        game.act("conductor", "ask", {"channel": "B", "body": "baseline B"})
        game.act("machine_B", "answer", {"body": "baseline B"})
        game.act("controller", "intervene", {"condition": "machineA"})
        before = game.export()
        with self.assertRaises(RuleError):
            game.act("machine_A", "respond", {
                "body": "inactive", "private_handoff": "SHOULD NOT EXIST"
            })
        self.assertEqual(game.export(), before)

    def test_manual_answer_and_whisper_endpoints_remain_available(self):
        game, _ = configured(True)
        game.act("machine_A", "whisper", {"body": "manual private message"})
        game.act("machine_A", "answer", {"body": "manual public response"})
        self.assertEqual(len(game.private), 1)
        self.assertEqual(len(game.public), 2)
        self.assertFalse(any(x["kind"] == "atomic_response" for x in game.audit))


class AtomicHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clock = FakeClock()
        cls.game = Game(clock=cls.clock)
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
        headers = {
            "Authorization": "Bearer " + self.game.tokens[role]
        }
        if action is None:
            req = Request(self.origin + "/api/view", headers=headers)
        else:
            headers["Content-Type"] = "application/json"
            req = Request(
                self.origin + "/api/act", headers=headers, method="POST",
                data=json.dumps({"action": action, **data}).encode("utf-8")
            )
        try:
            with urlopen(req, timeout=3) as result:
                return result.status, json.loads(result.read())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_one_http_action_is_atomic_and_role_scoped(self):
        self.assertEqual(self.request(
            "controller", "configure",
            links={"A_to_B": True, "B_to_A": True}
        )[0], 200)
        self.assertEqual(self.request(
            "conductor", "ask", channel="A", body="Prove what you can."
        )[0], 200)
        self.assertEqual(self.request(
            "observer", "respond",
            body="forbidden", private_handoff="should not store"
        )[0], 400)
        self.assertEqual(self.request(
            "machine_A", "respond",
            body="public", private_handoff=""
        )[0], 400)
        self.assertEqual(self.game.private, [])
        self.assertEqual(len(self.request("conductor")[1]["public"]), 1)
        self.assertEqual(self.request(
            "machine_A", "respond",
            body="public", private_handoff="private delivered"
        )[0], 200)
        self.assertEqual(len(self.game.private), 1)
        self.assertEqual(
            self.request("conductor")[1]["public"][-1]["body"], "public"
        )
        self.assertNotIn(
            "private delivered", json.dumps(self.request("conductor")[1])
        )
        self.assertNotIn(
            "private delivered", json.dumps(self.request("observer")[1])
        )


if __name__ == "__main__":
    unittest.main()
