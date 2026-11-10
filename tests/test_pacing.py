"""Deterministic-clock R4 release-gate tests.

These tests do not measure actual server scheduling jitter, typing latency,
OS queues or remote model performance. The clock is a controlled test witness.
"""
import json
from http.server import ThreadingHTTPServer
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from game.agents import Agent, AdapterError, ScriptedDemo
from game.engine import Game, RuleError
from game.server import handler_factory, run_release_worker


class FakeClock:
    def __init__(self, t=100.0):
        self.t = float(t)

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += float(dt)


def configure(game, seconds=10):
    game.act("controller", "configure_pacing", {"seconds": seconds})


def answer_baseline(game, clock):
    for side in ("A", "B"):
        game.act("conductor", "ask", {"channel": side, "body": "Baseline " + side})
        game.act("machine_" + side, "answer", {"body": "Machine " + side})
        clock.advance(game.pacing_seconds)
        game.view("conductor")


class PacingEngineTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.game = Game(clock=self.clock)

    def test_configuration_is_valid_and_immutable_after_first_question(self):
        for bad in (0, -1, 601, True, float("nan"), float("inf"), "45"):
            with self.subTest(value=bad), self.assertRaises(RuleError):
                self.game.act("controller", "configure_pacing", {"seconds": bad})
        configure(self.game, 45)
        self.assertEqual(self.game.view("controller")["pacing_seconds"], 45.0)
        with self.assertRaises(RuleError):
            configure(self.game, 10)
        self.game.act("controller", "configure", {
            "links": {"A_to_B": True, "B_to_A": True}
        })
        self.game.act("conductor", "ask", {"channel": "A", "body": "First"})
        with self.assertRaises(RuleError):
            self.game.act("controller", "configure", {
                "links": {"A_to_B": False, "B_to_A": False}
            })

    def test_buffer_until_gate_and_prevent_double_submit(self):
        configure(self.game, 10)
        self.game.act("conductor", "ask", {"channel": "A", "body": "What are you?"})
        self.clock.advance(1)
        self.game.act("machine_A", "answer", {"body": "A genuine machine."})
        self.assertEqual(len(self.game.view("conductor")["public"]), 1)
        self.assertTrue(self.game.view("machine_A")["awaiting_release"])
        self.assertTrue(self.game.view("controller")["pending_gate"]["response_buffered"])
        self.assertEqual(self.game.view("controller")["pending_gate"]["channel"], "A")
        with self.assertRaises(RuleError):
            self.game.act("machine_A", "answer", {"body": "Replace earlier answer"})
        with self.assertRaises(RuleError):
            self.game.act("conductor", "ask", {"channel": "B", "body": "New question"})
        with self.assertRaises(RuleError):
            self.game.act("conductor", "verdict", {
                "p": {"no_human": .6, "human_A": .2, "human_B": .2}
            })
        self.clock.advance(8.999)
        self.assertEqual(len(self.game.view("conductor")["public"]), 1)
        self.clock.advance(.001)
        projected = self.game.view("conductor")
        self.assertEqual(projected["public"][-1]["kind"], "answer")
        self.assertEqual(projected["public"][-1]["body"], "A genuine machine.")
        self.assertEqual(projected["public"][-1]["sequence"], 2)
        self.assertNotIn("timestamp", json.dumps(projected))
        self.assertNotIn("pacing_seconds", projected)
        self.assertIsNone(self.game.view("controller")["pending_gate"])
        self.assertEqual(self.game.view("controller")["timing_violations"], [])

    def test_early_and_late_ready_answers_have_same_public_view(self):
        def run(submitted_after):
            clock = FakeClock()
            g = Game(clock=clock)
            configure(g, 10)
            g.act("conductor", "ask", {"channel": "A", "body": "Prove your origin"})
            clock.advance(submitted_after)
            g.act("machine_A", "answer", {"body": "I cannot certify provenance in text."})
            just_before = g.view("conductor")
            clock.advance(10 - submitted_after)
            released = g.view("conductor")
            return just_before, released, g
        early_before, early_after, early = run(1)
        late_before, late_after, late = run(9.99)
        self.assertEqual(early_before, late_before)
        self.assertEqual(early_after, late_after)
        self.assertEqual(len(early_after["public"]), 2)
        self.assertNotEqual(
            early.view("controller")["audit"][-2]["accepted_at_monotonic"],
            late.view("controller")["audit"][-2]["accepted_at_monotonic"]
        )

    def test_deadline_timeout_invalidates_pilot_and_not_a_real_baseline_reply(self):
        configure(self.game, 10)
        self.game.act("conductor", "ask", {"channel": "A", "body": "Question"})
        self.clock.advance(10)
        response = self.game.view("conductor")
        self.assertEqual(response["public"][-1]["kind"], "timeout")
        self.assertEqual(response["public"][-1]["body"], "[NO RESPONSE BY DEADLINE]")
        self.assertFalse(self.game.view("controller")["baseline_ready"])
        self.assertEqual(
            self.game.view("controller")["timing_violations"][0]["reason"],
            "deadline_miss"
        )
        with self.assertRaises(RuleError):
            self.game.act("machine_A", "answer", {"body": "Late answer"})
        agent = Agent("conductor", _LocalRole(self.game, "conductor"),
                      ScriptedDemo(), question_budget=4)
        with self.assertRaises(AdapterError):
            agent.step()

    def test_intervention_only_between_released_turns(self):
        configure(self.game, 3)
        answer_baseline(self.game, self.clock)
        self.assertTrue(self.game.view("controller")["baseline_ready"])
        self.game.act("conductor", "ask", {"channel": "A", "body": "Continuation"})
        with self.assertRaises(RuleError):
            self.game.act("controller", "intervene", {"condition": "humanA"})
        self.game.act("machine_A", "answer", {"body": "Continuation by machine"})
        self.clock.advance(3)
        self.game.view("controller")
        self.game.act("controller", "intervene", {"condition": "humanA"})
        self.assertTrue(self.game.view("human")["active"])
        self.assertNotIn("condition", self.game.view("conductor"))

    def test_respondent_agent_does_not_repeat_a_buffered_answer(self):
        configure(self.game, 4)
        self.game.act("conductor", "ask", {"channel": "A", "body": "Question"})
        agent = Agent("machine_A", _LocalRole(self.game, "machine_A"),
                      ScriptedDemo())
        self.assertEqual(agent.step(), "answered")
        self.assertEqual(agent.step(), "waiting")
        self.assertEqual(len(self.game.public), 1)
        self.assertTrue(self.game.view("machine_A")["awaiting_release"])
        self.clock.advance(4)
        self.game.view("conductor")
        self.assertEqual(agent.step(), "waiting")
        self.assertEqual(len(self.game.public), 2)

    def test_publishing_after_tolerance_is_an_explicit_violation(self):
        configure(self.game, 10)
        self.game.act("conductor", "ask", {"channel": "A", "body": "Deadline"})
        self.game.act("machine_A", "answer", {"body": "Buffered answer"})
        self.clock.advance(11.5)
        self.assertEqual(
            self.game.view("conductor")["public"][-1]["body"],
            "Buffered answer"
        )
        violations = self.game.view("controller")["timing_violations"]
        self.assertEqual([v["reason"] for v in violations], ["late_publication"])
        self.assertAlmostEqual(violations[0]["lateness_seconds"], 1.5)
        self.assertIn("publication_lateness_seconds", 
                      json.dumps(self.game.view("controller")["audit"]))
        self.assertNotIn("publication_lateness_seconds", 
                         json.dumps(self.game.view("conductor")))

    def test_server_worker_releases_without_any_view_polls(self):
        configure(self.game, 4)
        self.game.act("conductor", "ask", {"channel": "A", "body": "Unpolled?"})
        self.game.act("machine_A", "answer", {"body": "Ready ahead of deadline"})
        self.assertEqual(len(self.game.public), 1)
        stop = threading.Event()
        worker = threading.Thread(
            target=run_release_worker, args=(self.game, stop, .005),
            daemon=True,
        )
        worker.start()
        try:
            self.clock.advance(4)
            for _ in range(40):
                if len(self.game.public) == 2:
                    break
                time.sleep(.01)
            self.assertEqual(len(self.game.public), 2)
            self.assertEqual(self.game.public[-1]["body"],
                             "Ready ahead of deadline")
            self.assertFalse(self.game.timing_violations)
        finally:
            stop.set()
            worker.join(1)
            self.assertFalse(worker.is_alive())

    def test_pending_error_is_independent_of_buffered_reply(self):
        configure(self.game, 6)
        self.game.act("conductor", "ask", {"channel": "A", "body": "First"})
        with self.assertRaises(RuleError) as before:
            self.game.act("conductor", "ask", {"channel": "B", "body": "Second"})
        self.game.act("machine_A", "answer", {"body": "Response"})
        with self.assertRaises(RuleError) as after:
            self.game.act("conductor", "ask", {"channel": "B", "body": "Second"})
        self.assertEqual(str(before.exception), str(after.exception))

    def test_unpaced_original_semantics_unchanged(self):
        self.game.act("conductor", "ask", {"channel": "A", "body": "Question"})
        self.game.act("machine_A", "answer", {"body": "Immediate answer"})
        self.assertEqual(self.game.view("conductor")["public"][-1]["kind"], "answer")
        self.assertEqual(len(self.game.view("conductor")["public"]), 2)
        self.assertEqual(self.game.view("controller")["pacing_seconds"], None)


class _LocalRole:
    def __init__(self, game, role):
        self.game, self.role = game, role

    def view(self):
        return self.game.view(self.role)

    def act(self, action, **payload):
        self.game.act(self.role, action, payload)


class PacingHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clock = FakeClock()
        cls.game = Game(clock=cls.clock)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(cls.game))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def _req(self, role, action=None, **kwargs):
        token = self.game.tokens[role]
        headers = {"Authorization": "Bearer " + token}
        if action is None:
            request = Request(self.base + "/api/view", headers=headers)
        else:
            headers["Content-Type"] = "application/json"
            request = Request(
                self.base + "/api/act", method="POST", headers=headers,
                data=json.dumps({"action": action, **kwargs}).encode("utf-8"),
            )
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_http_answer_not_visible_before_boundary(self):
        self.assertEqual(self._req("controller", "configure_pacing", seconds=10)[0], 200)
        self.assertEqual(self._req("conductor", "ask", channel="A", body="Hi")[0], 200)
        self.clock.advance(1)
        self.assertEqual(self._req("machine_A", "answer", body="Behind the mask")[0], 200)
        self.assertEqual(len(self._req("conductor")[1]["public"]), 1)
        self.assertTrue(self._req("machine_A")[1]["awaiting_release"])
        self.assertNotIn("pending_gate", self._req("conductor")[1])
        self.clock.advance(9)
        view = self._req("conductor")[1]
        self.assertEqual(len(view["public"]), 2)
        self.assertEqual(view["public"][-1]["body"], "Behind the mask")
        self.assertNotIn("timestamp", json.dumps(view))
        self.assertEqual(self._req("controller")[1]["timing_violations"], [])


if __name__ == "__main__":
    unittest.main()
