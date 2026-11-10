"""R5 black-box protocol test using real loopback HTTP and a fake clock.

No LLM calls and no human trials. Verifies endpoint-specific privileges,
public phase marker, hidden intervention and fixed score across eight turns.
"""
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from game.engine import Game
from game.server import handler_factory


class Clock:
    def __init__(self):
        self.value = 1000.0

    def __call__(self):
        return self.value

    def add(self, dt=45.0):
        self.value += dt


class PilotHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clock = Clock()
        cls.game = Game(clock=cls.clock)
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), handler_factory(cls.game)
        )
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.origin = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join(timeout=4)

    def http(self, role, action=None, **data):
        headers = {
            "Authorization": "Bearer " + self.game.tokens[role]
        }
        if action is None:
            request = Request(self.origin + "/api/view", headers=headers)
        else:
            headers["Content-Type"] = "application/json"
            body = json.dumps({"action": action, **data}).encode("utf-8")
            request = Request(self.origin + "/api/act",
                              data=body, method="POST", headers=headers)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def turn(self, channel, speaker):
        self.assertEqual(self.http("conductor", "ask", channel=channel,
                                   body="One public question")[0], 200)
        self.assertEqual(self.http(speaker, "answer", body="One public answer")[0], 200)
        before = self.http("conductor")[1]
        self.assertEqual(before["public"][-1]["kind"], "question")
        self.clock.add(45)
        released = self.http("conductor")[1]
        self.assertEqual(released["public"][-1]["kind"], "answer")

    def test_eight_turn_blind_trial_with_public_resume_and_observer(self):
        self.assertEqual(self.http("controller", "configure_pilot")[0], 200)
        self.assertEqual(self.http("conductor")[1]["pilot_phase"], "baseline")
        self.turn("A", "machine_A")
        self.turn("B", "machine_B")
        baseline = self.http("conductor")[1]
        self.assertEqual(baseline["pilot_phase"], "transition")
        self.assertEqual(self.http("conductor", "ask", channel="A",
                                   body="Premature question")[0], 400)

        self.assertEqual(self.http("controller", "intervene",
                                   condition="humanB",
                                   links={"A_to_B": False, "B_to_A": False},
                                   human_gateway=False)[0], 200)
        self.assertEqual(self.http("conductor")[1], baseline)
        self.assertEqual(self.http("observer")[1]["public"], baseline["public"])
        self.assertEqual(self.http("observer", "reveal")[0], 400)
        self.assertEqual(self.http("controller", "resume_pilot")[0], 200)
        visible = self.http("conductor")[1]
        self.assertEqual(visible["pilot_phase"], "continuation")
        self.assertEqual(visible["public"][-1]["kind"], "phase")
        self.assertNotIn("humanB", json.dumps(visible))

        for side in ("A", "B", "A", "B", "A", "B"):
            speaker = "human" if side == "B" else "machine_A"
            self.turn(side, speaker)

        self.assertEqual(self.http("conductor")[1]["pilot_phase"], "verdict")
        self.assertEqual(self.http("conductor", "ask", channel="A",
                                   body="Ninth")[0], 400)
        self.assertEqual(self.http("conductor", "verdict", p={
            "no_human": 0.2, "human_A": 0.1, "human_B": 0.7,
        }, evidence="A tentative evidence-based classification.")[0], 200)
        self.assertTrue(self.http("controller")[1]["pilot_valid_for_primary"])
        self.assertIsNone(self.http("conductor")[1]["outcome"])
        self.assertEqual(self.http("controller", "reveal")[0], 200)
        self.assertEqual(self.http("conductor")[1]["outcome"]["condition"], "humanB")
        self.assertAlmostEqual(self.http("controller")[1]["score"]["brier"], 0.14)


if __name__ == "__main__":
    unittest.main()
