"""Read-only witness regression suite: privacy, first-seen bounds and HTTP auth.

No test here is an independent human observation or C-receipt measurement.
"""
import json
import os
from http.server import ThreadingHTTPServer
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from game.engine import Game, RuleError
from game.observer import Witness, create_private_record, write_record
from game.server import handler_factory
from game.agents import AdapterError


def one_event(kind="question", seq=1):
    return {
        "sequence": seq, "kind": kind, "channel": "A",
        "speaker": "C" if kind == "question" else "A",
        "body": "Sensitive? Observed only as a digest."
    }


class WitnessTests(unittest.TestCase):
    def test_read_only_role_projection_cannot_access_private_or_controller_data(self):
        game = Game()
        self.assertEqual(game.identify(game.tokens["observer"]), "observer")
        game.act("conductor", "ask", {"channel": "A", "body": "Pilot?"})
        view = game.view("observer")
        self.assertEqual(set(view), {"role", "public"})
        self.assertEqual(set(view["public"][0]), {
            "sequence", "kind", "channel", "speaker", "body"
        })
        for forbidden in ("condition", "audit", "links", "active",
                          "timestamp", "pilot_enabled", "pacing_seconds"):
            self.assertNotIn(forbidden, json.dumps(view))
        with self.assertRaises(RuleError):
            game.act("observer", "ask", {"channel": "A", "body": "Unauthorized"})
        with self.assertRaises(RuleError):
            game.act("observer", "configure_pilot", {})

    def test_first_observation_window_is_bounded_by_poll_endpoints(self):
        witness = Witness()
        self.assertEqual(witness.sample(
            {"role": "observer", "public": []},
            request_start_ns=100, response_end_ns=110, wall_end_ns=200
        ), [])
        rows = witness.sample(
            {"role": "observer", "public": [one_event()]},
            request_start_ns=200, response_end_ns=210, wall_end_ns=300
        )
        self.assertEqual(len(rows), 1)
        item = rows[0]
        self.assertEqual(item["previous_poll_complete_monotonic_ns"], 110)
        self.assertEqual(item["request_started_monotonic_ns"], 200)
        self.assertEqual(item["response_complete_monotonic_ns"], 210)
        self.assertTrue(item["interval_bounded_by_polls"])
        self.assertNotIn("body", item)
        self.assertIn("payload_sha256", item)
        self.assertEqual(witness.sample(
            {"role": "observer", "public": [one_event()]},
            request_start_ns=215, response_end_ns=220, wall_end_ns=400
        ), [])

    def test_rejects_late_start_non_dense_history_and_clock_reversal(self):
        with self.assertRaises(AdapterError):
            Witness().sample(
                {"role": "observer", "public": [one_event()]},
                request_start_ns=1, response_end_ns=2, wall_end_ns=3
            )
        with self.assertRaises(AdapterError):
            Witness().sample(
                {"role": "conductor", "public": []},
                request_start_ns=1, response_end_ns=2, wall_end_ns=3
            )
        witness = Witness()
        witness.sample({"role": "observer", "public": []},
                       request_start_ns=1, response_end_ns=2, wall_end_ns=3)
        with self.assertRaises(AdapterError):
            witness.sample({"role": "observer", "public": [
                one_event(seq=5)
            ]}, request_start_ns=3, response_end_ns=4, wall_end_ns=5)
        with self.assertRaises(AdapterError):
            witness.sample({"role": "observer", "public": []},
                           request_start_ns=9, response_end_ns=6, wall_end_ns=7)

    def test_private_nonoverwrite_file_and_no_tokens_in_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            name = Path(tmp) / "witness.jsonl"
            with create_private_record(name) as f:
                write_record(f, {"type": "test", "public": "none"})
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(name.stat().st_mode), 0o600)
            self.assertEqual(json.loads(name.read_text().splitlines()[0])["type"], "test")
            with self.assertRaises(AdapterError):
                create_private_record(name)

    def test_witness_sees_only_public_phase_marker(self):
        game = Game()
        game.act("controller", "configure_pilot", {})
        self.assertNotIn("pilot_mode", json.dumps(game.view("observer")))
        self.assertEqual(game.view("observer")["public"], [])


class ObserverHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = Game()
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(cls.game))
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.srv.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=4)

    def test_observer_http_can_get_projection_but_not_write(self):
        headers = {
            "Authorization": "Bearer " + self.game.tokens["observer"]
        }
        with urlopen(Request(self.base + "/api/view", headers=headers), timeout=4) as resp:
            data = json.loads(resp.read())
            self.assertEqual(resp.status, 200)
        self.assertEqual(set(data), {"role", "public"})
        payload = json.dumps({
            "action": "intervene", "condition": "humanA"
        }).encode("utf-8")
        req = Request(self.base + "/api/act", method="POST", data=payload,
                      headers={**headers, "Content-Type": "application/json"})
        with self.assertRaises(HTTPError) as err:
            urlopen(req, timeout=4)
        self.assertEqual(err.exception.code, 400)
        self.assertFalse(self.game.intervened)


if __name__ == "__main__":
    unittest.main()
