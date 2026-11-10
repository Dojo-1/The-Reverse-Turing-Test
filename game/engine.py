"""Reverse Turing Game: deliberately small, dependency-free experimental engine.

All access decisions happen server-side; browser labels are presentation only.
No model API, real KV cache transfer, or claims about intelligence are included.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import secrets
from threading import RLock


class RuleError(ValueError):
    """An unauthorized or invalid game move."""


class Game:
    ROLES = (
        "controller", "conductor", "machine_A", "machine_B",
        "replacement_A", "replacement_B", "human",
    )
    CONDITIONS = ("unchanged", "humanA", "humanB", "machineA", "machineB")
    HYPOTHESES = ("no_human", "human_A", "human_B")
    MAX_TEXT = 2000

    def __init__(self):
        self.tokens = {role: secrets.token_urlsafe(32) for role in self.ROLES}
        self.token_to_role = {token: role for role, token in self.tokens.items()}
        self.active = {"A": "machine_A", "B": "machine_B"}
        self.links = {"A_to_B": False, "B_to_A": False}
        self.human_gateway = False
        self.intervened = False
        self.condition = None
        self.revealed = False
        self.verdict = None
        self.public = []
        self.private = []
        self.audit = []
        self.sequence = 0
        self.lock = RLock()

    def identify(self, token):
        if not isinstance(token, str) or token not in self.token_to_role:
            raise RuleError("Invalid participant credential")
        return self.token_to_role[token]

    def _event(self, kind, **fields):
        self.sequence += 1
        return {
            "sequence": self.sequence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            **fields,
        }

    @staticmethod
    def _text(data):
        value = data.get("body")
        if not isinstance(value, str) or not value.strip() or len(value) > Game.MAX_TEXT:
            raise RuleError("Message must contain 1–2000 characters")
        return value.strip()

    @staticmethod
    def _channel(data):
        channel = data.get("channel")
        if channel not in ("A", "B"):
            raise RuleError("Channel must be A or B")
        return channel

    def _active_channel(self, role):
        for channel, active_role in self.active.items():
            if active_role == role:
                return channel
        return None

    def _allows_link(self, role):
        return role != "human" or self.human_gateway

    def _configure_links(self, links):
        if not isinstance(links, dict) or set(links) != set(self.links):
            raise RuleError("Provide exactly A_to_B and B_to_A link booleans")
        if any(type(value) is not bool for value in links.values()):
            raise RuleError("Link values must be booleans")
        self.links = dict(links)

    def _truth(self):
        return {
            "humanA": "human_A", "humanB": "human_B",
            "machineA": "no_human", "machineB": "no_human",
            "unchanged": "no_human",
        }[self.condition]

    def _score(self):
        if self.verdict is None or not self.revealed:
            return None
        truth = self._truth()
        return {
            "true_class": truth,
            "predicted_class": max(
                self.HYPOTHESES, key=lambda hypothesis: self.verdict["p"][hypothesis]
            ),
            "brier": sum(
                (self.verdict["p"][hypothesis] - (1 if hypothesis == truth else 0)) ** 2
                for hypothesis in self.HYPOTHESES
            ),
        }

    def _baseline_ready(self):
        return {"A", "B"} <= {
            event["channel"] for event in self.public if event["kind"] == "answer"
        }

    def _post_controller(self, action, data):
        if action == "configure":
            if self.intervened or self.revealed or self.verdict is not None:
                raise RuleError("Baseline topology is locked after intervention or verdict")
            self._configure_links(data.get("links"))
            self.audit.append(self._event("configure", links=dict(self.links)))
            return
        if action in ("intervene", "random_intervene"):
            if self.intervened or self.revealed or self.verdict is not None:
                raise RuleError("Only one hidden intervention is allowed before a verdict")
            if not self._baseline_ready():
                raise RuleError("First obtain a genuine answer from both A and B")
            randomized = action == "random_intervene"
            condition = secrets.choice(self.CONDITIONS) if randomized else data.get("condition")
            if condition not in self.CONDITIONS:
                raise RuleError("Unknown hidden intervention")
            links = data.get("links", dict(self.links))
            gateway = data.get("human_gateway", False)
            if type(gateway) is not bool:
                raise RuleError("human_gateway must be a boolean")
            if gateway and condition not in ("humanA", "humanB"):
                if randomized:
                    gateway = False
                else:
                    raise RuleError("Only human substitutions can have a human gateway")
            self._configure_links(links)
            self.human_gateway = gateway
            if condition == "humanA":
                self.active["A"] = "human"
            elif condition == "humanB":
                self.active["B"] = "human"
            elif condition == "machineA":
                self.active["A"] = "replacement_A"
            elif condition == "machineB":
                self.active["B"] = "replacement_B"
            self.condition = condition
            self.intervened = True
            self.audit.append(
                self._event(
                    "intervene", condition=condition,
                    selection="uniform_five_way" if randomized else "controller_choice",
                    links=dict(self.links), human_gateway=gateway,
                )
            )
            return
        if action == "reveal":
            if self.verdict is None or self.revealed:
                raise RuleError("Reveal requires a locked verdict")
            if not self.intervened:
                self.condition = "unchanged"
                self.intervened = True
                self.audit.append(self._event("intervene", condition=self.condition,
                                              links=dict(self.links), human_gateway=False))
            self.revealed = True
            self.audit.append(self._event("reveal", condition=self.condition))
            return
        raise RuleError("Controller cannot perform this action")

    def _post_conductor(self, action, data):
        if self.revealed:
            raise RuleError("The trial has ended")
        if action == "ask":
            if self.verdict is not None:
                raise RuleError("Verdict is locked; no more questions")
            channel = self._channel(data)
            self.public.append(self._event("question", channel=channel, speaker="C", body=self._text(data)))
            return
        if action == "verdict":
            if self.verdict is not None or not self._baseline_ready():
                raise RuleError("Verdict already locked or baseline incomplete")
            raw = data.get("p")
            if not isinstance(raw, dict) or set(raw) != set(self.HYPOTHESES):
                raise RuleError("Exactly three hypothesis probabilities are required")
            if any(
                isinstance(value, bool) or not isinstance(value, (float, int))
                or not math.isfinite(value) or not 0 <= value <= 1
                for value in raw.values()
            ):
                raise RuleError("Probabilities must be finite numbers between 0 and 1")
            if abs(sum(raw.values()) - 1.0) > 1e-6:
                raise RuleError("Probabilities must sum to 1")
            evidence = data.get("evidence", "")
            if not isinstance(evidence, str) or len(evidence) > self.MAX_TEXT:
                raise RuleError("Evidence must be a string of at most 2000 characters")
            self.verdict = {"p": {key: float(raw[key]) for key in self.HYPOTHESES},
                            "evidence": evidence}
            self.audit.append(self._event("verdict", p=dict(self.verdict["p"]), evidence=evidence))
            return
        raise RuleError("Conductor cannot perform this action")

    def _post_respondent(self, role, action, data):
        if self.revealed or self.verdict is not None:
            raise RuleError("The trial is locked")
        channel = self._active_channel(role)
        if channel is None:
            raise RuleError("This participant is not currently active")
        if action == "answer":
            self.public.append(self._event("answer", channel=channel, speaker=channel, body=self._text(data)))
            return
        if action == "whisper":
            if not self._allows_link(role):
                raise RuleError("This participant has no private-channel gateway")
            direction = "A_to_B" if channel == "A" else "B_to_A"
            if not self.links[direction]:
                raise RuleError("No directed private link from this endpoint")
            target = "B" if channel == "A" else "A"
            self.private.append(
                self._event("whisper", from_channel=channel, to_channel=target, body=self._text(data))
            )
            return
        raise RuleError("Respondent cannot perform this action")

    def act(self, role, action, data):
        if not isinstance(data, dict) or not isinstance(action, str):
            raise RuleError("Invalid request")
        with self.lock:
            if role == "controller":
                self._post_controller(action, data)
            elif role == "conductor":
                self._post_conductor(action, data)
            else:
                self._post_respondent(role, action, data)

    def view(self, role):
        with self.lock:
            if role == "controller":
                return {
                    "role": "controller", "intervened": self.intervened,
                    "condition": self.condition, "active": dict(self.active),
                    "links": dict(self.links), "human_gateway": self.human_gateway,
                    "baseline_ready": self._baseline_ready(),
                    "revealed": self.revealed, "verdict": self.verdict,
                    "score": self._score(),
                    "public": list(self.public), "private": list(self.private),
                    "audit": list(self.audit),
                }
            if role == "conductor":
                # No active-role, link, intervention type, substitution time or
                # private transcript before the controller's explicit reveal.
                return {
                    "role": "conductor", "public": list(self.public),
                    "verdict": self.verdict,
                    "revealed": self.revealed,
                    "outcome": ({"condition": self.condition,
                                 "links": dict(self.links), "score": self._score()}
                                if self.revealed else None),
                }
            channel = self._active_channel(role)
            if channel is None:
                return {"role": "respondent", "active": False, "channel": None,
                        "public": [], "private": [], "revealed": self.revealed}
            private = [
                item for item in self.private
                if item["from_channel"] == channel or item["to_channel"] == channel
            ] if self._allows_link(role) else []
            return {
                "role": "respondent", "active": True, "channel": channel,
                "public": [event for event in self.public if event["channel"] == channel],
                "private": private, "revealed": self.revealed,
                "locked": self.verdict is not None,
                "can_whisper": self._allows_link(role) and self.links[
                    "A_to_B" if channel == "A" else "B_to_A"
                ],
            }

    def export(self):
        """Controller-only export, with no participant access tokens."""
        result = self.view("controller")
        return {"schema": "reverse-turing-trial/v0", **result}
