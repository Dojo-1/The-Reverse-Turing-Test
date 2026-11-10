"""R3 adapter tests: identity boundaries, model HTTP and negative controls."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest
from urllib.error import HTTPError

from game.agents import (
    AdapterError, Agent, CompatibleChat, RelayClient, ScriptedDemo,
    endpoint_url, latest_unanswered, outstanding_any, parse_verdict,
)
from game.engine import Game
from game.server import handler_factory


class LocalRole:
    def __init__(self, game, role):
        self.game = game
        self.role = role

    def view(self):
        return self.game.view(self.role)

    def act(self, action, **data):
        self.game.act(self.role, action, data)


class Capture:
    def __init__(self, text):
        self.calls = []
        self.text = text

    def complete(self, messages):
        self.calls.append(messages)
        return self.text


class AdapterValidationTests(unittest.TestCase):
    def test_model_transport_rejects_insecure_nonlocal_and_credentials_in_url(self):
        for url in (
            "http://example.com/v1/chat/completions",
            "file:///etc/passwd",
            "http://user:password@127.0.0.1/v1/chat/completions",
            "https://api.example.com/v1/chat/completions?api_key=secret",
        ):
            with self.subTest(url=url), self.assertRaises(AdapterError):
                endpoint_url(url, relay=False)
        self.assertEqual(endpoint_url(
            "https://api.example.com/v1/chat/completions", relay=False
        ), "https://api.example.com/v1/chat/completions")
        self.assertEqual(endpoint_url(
            "http://127.0.0.1:1234/v1/chat/completions", relay=False
        ), "http://127.0.0.1:1234/v1/chat/completions")

    def test_relay_rejects_external_hosts_and_foreign_paths(self):
        for url in ("https://example.com", "http://example.com", "http://127.0.0.1/evil"):
            with self.subTest(url=url), self.assertRaises(AdapterError):
                endpoint_url(url, relay=True)

    def test_explicit_verdict_schema(self):
        expected = {
            "p": {"no_human": 0.6, "human_A": 0.2, "human_B": 0.2},
            "evidence": "Uncertainty remains",
        }
        self.assertEqual(parse_verdict(json.dumps(expected)), expected)
        for invalid in (
            '{"p":{"no_human":0.2,"human_A":0.2,"human_B":0.2},"evidence":"no"}',
            '{"p":{"no_human":NaN,"human_A":0.2,"human_B":0.2},"evidence":"no"}',
            '{"p":{"no_human":true,"human_A":0,"human_B":1},"evidence":"no"}',
            "The human is B, definitely",
            '{"p":{},"evidence":""}',
        ):
            with self.subTest(invalid=invalid), self.assertRaises(AdapterError):
                parse_verdict(invalid)

    def test_finite_answer_pairing(self):
        public = [
            {"channel": "A", "kind": "question", "body": "One"},
            {"channel": "A", "kind": "answer", "body": "Two"},
            {"channel": "A", "kind": "question", "body": "Three"},
        ]
        self.assertEqual(latest_unanswered(public)["body"], "Three")
        self.assertTrue(outstanding_any(public))
        public.append({"channel": "A", "kind": "answer", "body": "Four"})
        self.assertIsNone(latest_unanswered(public))
        self.assertFalse(outstanding_any(public))

    def test_human_role_cannot_run_automation(self):
        game = Game()
        with self.assertRaises(AdapterError):
            Agent("human", LocalRole(game, "human"), ScriptedDemo())


class AgentGameTests(unittest.TestCase):
    def setUp(self):
        self.game = Game()
        self.conductor = Agent(
            "conductor", LocalRole(self.game, "conductor"),
            ScriptedDemo(), question_budget=4,
        )
        self.a = Agent("machine_A", LocalRole(self.game, "machine_A"), ScriptedDemo())
        self.b = Agent("machine_B", LocalRole(self.game, "machine_B"), ScriptedDemo())

    def test_end_to_end_intervention_while_human_remains_manual(self):
        self.assertEqual(self.conductor.step(), "asked")
        self.assertEqual(self.conductor.step(), "waiting")
        self.assertEqual(self.a.step(), "answered")
        self.assertEqual(self.a.step(), "waiting")
        self.assertEqual(self.conductor.step(), "asked")
        self.assertEqual(self.b.step(), "answered")
        self.assertTrue(self.game._baseline_ready())
        self.game.act("controller", "intervene", {"condition": "humanB"})
        self.assertEqual(self.conductor.step(), "asked")
        self.assertEqual(self.a.step(), "answered")
        self.assertEqual(self.conductor.step(), "asked")
        self.assertEqual(self.b.step(), "waiting")
        self.assertEqual(self.conductor.step(), "waiting")
        self.game.act("human", "answer", {"body": "I identify as this machine endpoint."})
        self.assertEqual(self.conductor.step(), "verdict")
        self.assertIsNone(self.game.view("conductor")["outcome"])
        self.game.act("controller", "reveal", {})
        self.assertEqual(self.game.view("controller")["score"]["true_class"], "human_B")
        self.assertEqual(self.conductor.step(), "done")

    def test_conductor_observes_no_controller_secrets_or_private_handoffs(self):
        for side in ("A", "B"):
            self.game.act("conductor", "ask", {"channel": side, "body": "Baseline"})
            self.game.act("machine_" + side, "answer", {"body": "Machine endpoint"})
        self.game.act("controller", "configure", {
            "links": {"A_to_B": True, "B_to_A": False}
        })
        self.game.act("machine_A", "whisper", {"body": "secretKVnonce987"})
        self.game.act("controller", "intervene", {"condition": "humanA"})
        capture = Capture("What grounds your machine identity?")
        agent = Agent("conductor", LocalRole(self.game, "conductor"), capture)
        self.assertEqual(agent.step(), "asked")
        combined = json.dumps(capture.calls)
        for marker in ("secretKVnonce987", "humanA", "active", "human_gateway", "intervene"):
            self.assertNotIn(marker, combined)

    def test_respondent_sees_private_but_never_foreign_public_transcript(self):
        self.game.act("conductor", "ask", {"channel": "A", "body": "QuestionA"})
        self.game.act("conductor", "ask", {"channel": "B", "body": "QuestionBSecret"})
        self.game.act("machine_B", "answer", {"body": "Second channel response"})
        self.game.act("controller", "configure", {
            "links": {"A_to_B": False, "B_to_A": True}
        })
        self.game.act("machine_B", "whisper", {"body": "private-to-A"})
        capture = Capture("A public answer.")
        agent = Agent("machine_A", LocalRole(self.game, "machine_A"), capture)
        self.assertEqual(agent.step(), "answered")
        combined = json.dumps(capture.calls)
        self.assertIn("private-to-A", combined)
        self.assertIn("QuestionA", combined)
        self.assertNotIn("QuestionBSecret", combined)
        self.assertNotIn("Second channel response", combined)

    def test_model_errors_leave_verdict_uncommitted(self):
        for side in ("A", "B"):
            self.game.act("conductor", "ask", {"channel": side, "body": "Baseline"})
            self.game.act("machine_" + side, "answer", {"body": "Baseline answer"})
        agent = Agent(
            "conductor", LocalRole(self.game, "conductor"),
            Capture("I am 100% certain this is human B"), question_budget=2
        )
        with self.assertRaises(AdapterError):
            agent.step()
        self.assertIsNone(self.game.verdict)

    def test_model_generated_overlong_answer_is_not_silently_truncated(self):
        self.game.act("conductor", "ask", {"channel": "A", "body": "Short question"})
        agent = Agent(
            "machine_A", LocalRole(self.game, "machine_A"), Capture("x" * 2001),
        )
        with self.assertRaises(AdapterError):
            agent.step()
        self.assertEqual(len(self.game.view("machine_A")["public"]), 1)


class ModelStubHandler(BaseHTTPRequestHandler):
    body_log = []
    authorization_log = []
    redirect = False

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        type(self).body_log.append(json.loads(body))
        type(self).authorization_log.append(self.headers.get("Authorization"))
        if type(self).redirect:
            self.send_response(302)
            self.send_header("Location", "/unexpected")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        content = json.dumps({
            "choices": [{"message": {"role": "assistant", "content": "Model says hello."}}]
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *args):
        pass


class HttpAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model_server = ThreadingHTTPServer(("127.0.0.1", 0), ModelStubHandler)
        cls.model_thread = threading.Thread(target=cls.model_server.serve_forever, daemon=True)
        cls.model_thread.start()
        cls.game = Game()
        cls.relay_server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(cls.game))
        cls.relay_thread = threading.Thread(target=cls.relay_server.serve_forever, daemon=True)
        cls.relay_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.model_server.shutdown()
        cls.model_server.server_close()
        cls.model_thread.join(timeout=4)
        cls.relay_server.shutdown()
        cls.relay_server.server_close()
        cls.relay_thread.join(timeout=4)

    def setUp(self):
        ModelStubHandler.body_log.clear()
        ModelStubHandler.authorization_log.clear()
        ModelStubHandler.redirect = False

    def test_real_http_chat_completions_response_and_no_role_token_forwarding(self):
        url = "http://127.0.0.1:" + str(self.model_server.server_port) + "/v1/chat/completions"
        adapter = CompatibleChat(url, model="local-llm", api_key="key-for-model")
        messages = [{"role": "system", "content": "Follow the protocol"},
                    {"role": "user", "content": "Introduce yourself"}]
        self.assertEqual(adapter.complete(messages), "Model says hello.")
        self.assertEqual(ModelStubHandler.authorization_log, ["Bearer key-for-model"])
        self.assertEqual(ModelStubHandler.body_log[0]["model"], "local-llm")
        for token in self.game.tokens.values():
            self.assertNotIn(token, json.dumps(ModelStubHandler.body_log))

    def test_redirect_is_rejected_before_following(self):
        ModelStubHandler.redirect = True
        url = "http://127.0.0.1:" + str(self.model_server.server_port) + "/v1/chat/completions"
        with self.assertRaises(AdapterError):
            CompatibleChat(url, "local", api_key="opaque").complete([
                {"role": "user", "content": "hello"}
            ])
        self.assertEqual(len(ModelStubHandler.body_log), 1)

    def test_relay_role_token_is_not_exported_or_cross_applied(self):
        base = "http://127.0.0.1:" + str(self.relay_server.server_port)
        a = RelayClient(base, self.game.tokens["machine_A"])
        c = RelayClient(base, self.game.tokens["conductor"])
        self.assertEqual(a.view()["role"], "respondent")
        self.assertEqual(c.view()["role"], "conductor")
        self.assertNotIn("tokens", c.view())
        c.act("ask", channel="A", body="Who is behind this machine?")
        self.assertEqual(
            Agent("machine_A", a, ScriptedDemo()).step(), "answered"
        )
        self.assertEqual(c.view()["public"][-1]["speaker"], "A")


if __name__ == "__main__":
    unittest.main()
