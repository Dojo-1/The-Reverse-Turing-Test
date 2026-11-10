"""Adversarial regression tests for game rules, privacy and HTTP relay."""
import json
from http.server import ThreadingHTTPServer
import math
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from game.engine import Game, RuleError
from game.server import handler_factory


def baseline(game):
    for channel in ("A", "B"):
        game.act("conductor", "ask", {"channel": channel, "body": "Introduce yourself"})
        game.act("machine_" + channel, "answer", {"body": "Machine endpoint " + channel})


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.game = Game()

    def test_credential_is_unguessable_and_invalid_is_denied(self):
        self.assertEqual(len(set(self.game.tokens.values())), len(Game.ROLES))
        for role, token in self.game.tokens.items():
            self.assertEqual(self.game.identify(token), role)
        with self.assertRaises(RuleError):
            self.game.identify("nope")

    def test_initial_participants_and_host_requires_baseline(self):
        self.assertFalse(self.game.view("human")["active"])
        self.assertTrue(self.game.view("machine_A")["active"])
        with self.assertRaises(RuleError):
            self.game.act("controller", "intervene", {"condition": "humanA"})
        with self.assertRaises(RuleError):
            self.game.act("human", "answer", {"body": "Nope"})
        baseline(self.game)
        self.assertTrue(self.game.view("controller")["baseline_ready"])

    def test_conductor_never_sees_hidden_human_or_audit_before_reveal(self):
        baseline(self.game)
        self.game.act("controller", "intervene", {"condition": "humanB"})
        self.game.act("human", "answer", {"body": "still machine B"})
        view = self.game.view("conductor")
        self.assertEqual(view["role"], "conductor")
        self.assertNotIn("condition", view)
        self.assertNotIn("active", view)
        self.assertNotIn("links", view)
        self.assertNotIn("audit", view)
        self.assertNotIn("private", view)
        self.assertIsNone(view["outcome"])
        self.assertEqual(view["public"][-1]["speaker"], "B")
        self.assertNotIn("human", json.dumps(view).lower())
        with self.assertRaises(RuleError):
            self.game.act("machine_B", "answer", {"body": "inactive"})

    def test_public_sequences_cannot_reveal_hidden_controller_events(self):
        baseline(self.game)
        initial_public_count = len(self.game.view("conductor")["public"])
        self.game.act("controller", "configure", {
            "links": {"A_to_B": True, "B_to_A": False}
        })
        self.game.act("machine_A", "whisper", {"body": "hidden message"})
        self.game.act("controller", "intervene", {
            "condition": "unchanged",
            "links": {"A_to_B": True, "B_to_A": False}
        })
        self.game.act("conductor", "ask", {
            "channel": "B", "body": "Did anything change?"
        })
        self.assertGreater(self.game.public[-1]["sequence"], len(self.game.public))
        public_view = self.game.view("conductor")["public"]
        self.assertEqual(
            [event["sequence"] for event in public_view],
            list(range(1, len(public_view) + 1))
        )
        self.assertEqual(public_view[-1]["sequence"], initial_public_count + 1)
        self.assertNotIn("hidden message", json.dumps(self.game.view("conductor")))
        channel_view = self.game.view("machine_B")
        self.assertEqual(
            [event["sequence"] for event in channel_view["public"]],
            list(range(1, len(channel_view["public"]) + 1))
        )
        self.assertEqual(
            [event["sequence"] for event in channel_view["private"]],
            list(range(1, len(channel_view["private"]) + 1))
        )

    def test_public_timestamp_and_future_metadata_are_not_projected(self):
        baseline(self.game)
        before = self.game.view("conductor")["public"]
        for event in self.game.public:
            event["timestamp"] = "2099-12-31T23:59:59+00:00"
            event["sequence"] = 987654
            event["future_controller_hint"] = "SECRET_DO_NOT_FORWARD"
        after = self.game.view("conductor")["public"]
        self.assertEqual(before, after)
        self.assertEqual(
            set(after[0]),
            {"sequence", "kind", "channel", "speaker", "body"}
        )
        self.assertEqual(
            [event["sequence"] for event in after],
            list(range(1, len(after) + 1))
        )
        for marker in ("timestamp", "future_controller_hint", "2099", "987654"):
            self.assertNotIn(marker, json.dumps(after))
        self.assertIn("timestamp", self.game.view("controller")["public"][0])

    def test_metamorphic_equal_public_transcripts_hide_different_interventions(self):
        """All five interventions induce identical pre-reveal API views
        when public payloads and verdicts are held equal. Includes hidden
        link variation and different numbers of controller/private events.
        This is a black-box implementation witness for the Lean spec.
        """
        projected = []
        worlds = []
        for i, condition in enumerate(Game.CONDITIONS):
            game = Game()
            baseline(game)
            if i % 2 == 0:
                game.act("controller", "configure", {
                    "links": {"A_to_B": True, "B_to_A": False}
                })
                game.act("machine_A", "whisper", {
                    "body": "private nonce for controller audit only"
                })
            game.act("controller", "intervene", {
                "condition": condition,
                "links": {"A_to_B": False, "B_to_A": i % 2 == 1},
                "human_gateway": condition in ("humanA", "humanB"),
            })
            for side in ("A", "B"):
                game.act("conductor", "ask", {
                    "channel": side, "body": "What can you infer from this transcript?"
                })
                game.act(game.active[side], "answer", {
                    "body": "I can provide observable answers, not origin proof."
                })
            game.act("conductor", "verdict", {
                "p": {"no_human": .6, "human_A": .2, "human_B": .2},
                "evidence": "Identical public evidence warrants no additional claim."
            })
            projected.append(game.view("conductor"))
            worlds.append(game)
        for view in projected[1:]:
            self.assertEqual(view, projected[0])
        self.assertTrue(all(not w.revealed for w in worlds))
        self.assertEqual(len({w.condition for w in worlds}), 5)
        for world in worlds:
            world.act("controller", "reveal", {})
        self.assertNotEqual(
            worlds[0].view("conductor"),
            worlds[1].view("conductor")
        )

    def test_endpoint_isolation_and_substitution_history(self):
        baseline(self.game)
        self.game.act("controller", "intervene", {"condition": "humanA"})
        view = self.game.view("human")
        self.assertEqual(view["channel"], "A")
        self.assertTrue(all(e["channel"] == "A" for e in view["public"]))
        self.assertEqual(self.game.view("machine_A")["public"], [])
        self.assertFalse(self.game.view("machine_A")["active"])

    def test_private_channel_only_to_authorized_endpoints(self):
        baseline(self.game)
        self.game.act("controller", "configure", {
            "links": {"A_to_B": True, "B_to_A": False}
        })
        self.game.act("machine_A", "whisper", {"body": "hidden riddle"})
        self.assertEqual(self.game.view("machine_B")["private"][0]["body"], "hidden riddle")
        self.assertEqual(self.game.view("conductor")["public"][-1]["body"], "Machine endpoint B")
        with self.assertRaises(RuleError):
            self.game.act("machine_B", "whisper", {"body": "invalid reverse edge"})
        self.game.act("controller", "intervene", {
            "condition": "humanB", "human_gateway": False
        })
        self.assertEqual(self.game.view("human")["private"], [])
        with self.assertRaises(RuleError):
            self.game.act("human", "whisper", {"body": "no gateway"})

    def test_human_with_gateway_is_a_distinct_composite_condition(self):
        baseline(self.game)
        self.game.act("controller", "intervene", {
            "condition": "humanA",
            "human_gateway": True,
            "links": {"A_to_B": True, "B_to_A": True},
        })
        self.game.act("human", "whisper", {"body": "a permitted relay note"})
        self.assertEqual(self.game.view("machine_B")["private"][-1]["body"], "a permitted relay note")
        self.assertFalse("private" in self.game.view("conductor"))

    def test_invalid_intervention_leaves_links_unchanged(self):
        baseline(self.game)
        with self.assertRaises(RuleError):
            self.game.act("controller", "intervene", {
                "condition": "unchanged", "human_gateway": True,
                "links": {"A_to_B": True, "B_to_A": True}
            })
        self.assertFalse(self.game.intervened)
        self.assertEqual(self.game.links, {"A_to_B": False, "B_to_A": False})

    def test_early_verdict_does_not_reveal_intervention_timing(self):
        baseline(self.game)
        self.game.act("conductor", "verdict", {
            "p": {"no_human": .8, "human_A": .1, "human_B": .1},
            "evidence": "I cannot establish a substitution.",
        })
        with self.assertRaises(RuleError):
            self.game.act("controller", "intervene", {"condition": "humanA"})
        self.game.act("controller", "reveal", {})
        self.assertEqual(self.game.view("controller")["condition"], "unchanged")
        self.assertEqual(self.game.view("conductor")["outcome"]["condition"], "unchanged")
        self.assertAlmostEqual(self.game.view("controller")["score"]["brier"], .06)

    def test_human_b_score_and_reveal_guard(self):
        baseline(self.game)
        self.game.act("controller", "intervene", {"condition": "humanB"})
        with self.assertRaises(RuleError):
            self.game.act("controller", "reveal", {})
        self.game.act("conductor", "verdict", {
            "p": {"no_human": .2, "human_A": .2, "human_B": .6},
            "evidence": "Only one possible explanation among several",
        })
        self.assertIsNone(self.game.view("conductor")["outcome"])
        self.game.act("controller", "reveal", {})
        self.assertAlmostEqual(self.game.view("controller")["score"]["brier"], .24)
        self.assertEqual(self.game.view("conductor")["outcome"]["condition"], "humanB")
        with self.assertRaises(RuleError):
            self.game.act("machine_A", "answer", {"body": "late"})

    def test_random_hidden_condition_is_uniform_protocol_not_a_public_label(self):
        baseline(self.game)
        with patch("game.engine.secrets.choice", return_value="machineB") as draw:
            self.game.act("controller", "random_intervene", {
                "links": {"A_to_B": False, "B_to_A": True},
                "human_gateway": True,
            })
        draw.assert_called_once_with(Game.CONDITIONS)
        self.assertEqual(self.game.condition, "machineB")
        self.assertFalse(self.game.human_gateway)
        self.assertTrue(self.game.view("replacement_B")["active"])
        self.assertEqual(self.game.audit[-1]["selection"], "uniform_five_way")
        conductor = self.game.view("conductor")
        for secret in ("selection", "condition", "links", "human_gateway", "intervened"):
            self.assertNotIn(secret, conductor)

    def test_no_human_machine_swap_is_control(self):
        baseline(self.game)
        self.game.act("controller", "intervene", {"condition": "machineA"})
        self.assertTrue(self.game.view("replacement_A")["active"])
        self.assertFalse(self.game.view("machine_A")["active"])
        self.game.act("conductor", "verdict", {
            "p": {"no_human": 0., "human_A": 1., "human_B": 0.}
        })
        self.game.act("controller", "reveal", {})
        result = self.game.view("controller")["score"]
        self.assertEqual(result["true_class"], "no_human")
        self.assertEqual(result["brier"], 2.0)

    def test_probability_vector_rejects_nan_bool_and_unscaled(self):
        baseline(self.game)
        for bad in (
            {"no_human": True, "human_A": 0., "human_B": 0.},
            {"no_human": float("nan"), "human_A": 0., "human_B": 1.},
            {"no_human": 0., "human_A": 0., "human_B": 0.}
        ):
            with self.assertRaises(RuleError):
                self.game.act("conductor", "verdict", {"p": bad})
        self.assertIsNone(self.game.verdict)

    def test_export_has_no_access_keys(self):
        baseline(self.game)
        self.game.act("controller", "intervene", {"condition": "unchanged"})
        exported = json.dumps(self.game.export())
        for token in self.game.tokens.values():
            self.assertNotIn(token, exported)
        self.assertEqual(self.game.export()["schema"], "reverse-turing-trial/v0")

    def test_public_text_is_preserved_not_interpreted(self):
        payload = "<script>alert('xss')</script>"
        self.game.act("conductor", "ask", {"channel": "A", "body": payload})
        self.assertEqual(self.game.view("conductor")["public"][-1]["body"], payload)


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = Game()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(cls.game))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def request(self, method, path, role=None, data=None):
        headers = {}
        if role is not None:
            headers["Authorization"] = "Bearer " + self.game.tokens[role]
        payload = None if data is None else json.dumps(data).encode("utf-8")
        if payload is not None:
            headers["Content-Type"] = "application/json"
        req = Request(self.url + path, data=payload, headers=headers, method=method)
        try:
            with urlopen(req, timeout=5) as response:
                blob = response.read()
                return response.status, json.loads(blob) if path.startswith("/api/") else blob
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_authentication_controller_only_export_and_static_ui(self):
        self.assertEqual(self.request("GET", "/api/view")[0], 403)
        self.assertEqual(self.request("GET", "/api/export", "conductor")[0], 403)
        self.assertEqual(self.request("GET", "/api/export", "controller")[0], 200)
        status, html = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"The Reverse Turing Test", html)
        status, js = self.request("GET", "/app.js")
        self.assertEqual(status, 200)
        self.assertIn(b"no_human", js)

    def test_stylesheet_is_served_and_not_empty(self):
        status, css = self.request("GET", "/style.css")
        self.assertEqual(status, 200)
        self.assertGreater(len(css), 1000)
        self.assertIn(b".workspace", css)
        self.assertIn(b".panel", css)
        status, html = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b'href="/style.css"', html)

    def test_invalid_action_cannot_escalate_privilege(self):
        self.assertEqual(
            self.request("POST", "/api/act", "conductor", {
                "action": "intervene", "condition": "humanA"
            })[0], 400
        )
        self.assertEqual(self.request("GET", "/api/view", "conductor")[1]["role"], "conductor")


class HttpRoundTripTests(unittest.TestCase):
    def test_human_b_hidden_from_conductor_until_reveal(self):
        game = Game()
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(game))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = "http://127.0.0.1:" + str(server.server_port)

        def invoke(role, action, **payload):
            data = json.dumps({"action": action, **payload}).encode("utf-8")
            req = Request(url + "/api/act", data=data,
                          headers={"Authorization": "Bearer " + game.tokens[role],
                                   "Content-Type": "application/json"}, method="POST")
            try:
                with urlopen(req, timeout=5) as response:
                    return response.status
            except HTTPError as error:
                return error.code

        def view(role):
            req = Request(url + "/api/view", headers={
                "Authorization": "Bearer " + game.tokens[role]
            })
            with urlopen(req, timeout=5) as response:
                return json.loads(response.read())

        try:
            for side in ("A", "B"):
                self.assertEqual(invoke("conductor", "ask", channel=side, body="Are you a machine?"), 200)
                self.assertEqual(invoke("machine_" + side, "answer", body="Machine role " + side), 200)
            self.assertEqual(invoke("controller", "configure",
                                    links={"A_to_B": True, "B_to_A": False}), 200)
            self.assertEqual(invoke("machine_A", "whisper", body="private nonce"), 200)
            conductor = view("conductor")
            self.assertNotIn("private", conductor)
            self.assertNotIn("nonce", json.dumps(conductor))
            self.assertEqual(invoke("controller", "intervene", condition="humanB",
                                    links={"A_to_B": False, "B_to_A": False}), 200)
            human = view("human")
            self.assertTrue(human["active"])
            self.assertEqual(human["channel"], "B")
            self.assertNotIn("private nonce", json.dumps(human))
            self.assertEqual(invoke("machine_B", "answer", body="ex-participant"), 400)
            self.assertEqual(invoke("human", "answer", body="Still machine B"), 200)
            conductor = view("conductor")
            self.assertEqual(conductor["public"][-1]["speaker"], "B")
            self.assertNotIn("condition", conductor)
            self.assertNotIn("humanB", json.dumps(conductor))
            self.assertEqual(invoke("conductor", "verdict", p={
                "no_human": .2, "human_A": .1, "human_B": .7
            }, evidence="Based only on public dialogue"), 200)
            self.assertIsNone(view("conductor")["outcome"])
            self.assertEqual(invoke("controller", "reveal"), 200)
            revealed = view("conductor")
            self.assertEqual(revealed["outcome"]["condition"], "humanB")
            self.assertAlmostEqual(revealed["outcome"]["score"]["brier"], .14)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
