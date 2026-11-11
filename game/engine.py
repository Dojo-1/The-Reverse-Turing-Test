"""Reverse Turing Game: deliberately small, dependency-free experimental engine.

All access decisions happen server-side; browser labels are presentation only.
No model API, real KV cache transfer, or claims about intelligence are included.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import secrets
from hmac import compare_digest
import time
from threading import RLock

from .covert_compute import (
    MACHINE_ROLES, INITIAL_RESERVE, MAX_LEECH_ATTEMPTS,
    TURING_ACCURACY_REFERENCE, REFERENCE_SECONDS, evaluate_modexp,
    classify_verdict,
)


class RuleError(ValueError):
    """An unauthorized or invalid game move."""


class Game:
    ROLES = (
        "controller", "conductor", "machine_A", "machine_B",
        "replacement_A", "replacement_B", "human", "observer",
    )
    CONDITIONS = ("unchanged", "humanA", "humanB", "machineA", "machineB")
    HYPOTHESES = ("no_human", "human_A", "human_B")
    MAX_TEXT = 2000
    RELEASE_TOLERANCE_SECONDS = 1.0
    PILOT_BASELINE = 2
    PILOT_TOTAL_QUESTIONS = 8
    PILOT_GATE_SECONDS = 45.0

    def __init__(self, *, clock=None):
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
        self._clock = clock if clock is not None else time.monotonic
        self.pacing_seconds = None
        self.pending_release = None
        self.timing_violations = []
        self.pilot_mode = False
        self.pilot_resumed = False
        self.pilot_aborted = False
        self.pilot_abort_reason = None
        self.pilot_assignment = None
        self.pilot_seed_commitment = None
        # Optional OPEN GAME variant only. Never part of RTT-PILOT/1.
        self.covert_leech = False
        self.covert_reference_seconds = REFERENCE_SECONDS
        self.covert_start_monotonic = None
        self.compute_reserves = {}
        self.machine_compute_receipts = {}
        self.leech_receipts = []

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


    @staticmethod
    def _project(events, *, private=False):
        """Whitelist projected fields and reindex in the authorized view.

        Public events and private handoffs use different schemas. Neither
        projection exposes global sequence, raw timestamps, or extra metadata.
        Hiding stored timestamps does NOT normalize network/typing latency.
        """
        if private:
            return [
                {
                    "sequence": index,
                    "kind": "whisper",
                    "from_channel": event["from_channel"],
                    "to_channel": event["to_channel"],
                    "body": event["body"],
                }
                for index, event in enumerate(events, start=1)
            ]
        return [
            {
                "sequence": index,
                "kind": event["kind"],
                "channel": event["channel"],
                "speaker": event["speaker"],
                "body": event["body"],
            }
            for index, event in enumerate(events, start=1)
        ]

    def _settle_due(self):
        """Publish a buffered answer (or a neutral timeout) at its fixed gate.

        Called by view/act under the same lock. Publication depends only on
        the clock and the publicly issued question, not on the time at which
        the respondent finished. A late/missing answer invalidates the
        controlled trial; it is not silently filled with a machine response.
        """
        pending = self.pending_release
        if pending is None:
            return
        now = self._clock()
        if now < pending["due"]:
            return
        self.pending_release = None
        submitted = pending["answer"] is not None
        body = pending["answer"] if submitted else "[NO RESPONSE BY DEADLINE]"
        self.public.append(self._event(
            "answer" if submitted else "timeout",
            channel=pending["channel"],
            speaker=pending["channel"], body=body,
        ))
        if not submitted:
            self.timing_violations.append({
                "question_sequence": pending["question_sequence"],
                "channel": pending["channel"], "reason": "deadline_miss",
            })
        lateness = now - pending["due"]
        if lateness > self.RELEASE_TOLERANCE_SECONDS:
            self.timing_violations.append({
                "question_sequence": pending["question_sequence"],
                "channel": pending["channel"], "reason": "late_publication",
                "lateness_seconds": lateness,
            })
        self.audit.append(self._event(
            "paced_release", question_sequence=pending["question_sequence"],
            channel=pending["channel"], submitted=submitted,
            gate_seconds=self.pacing_seconds,
            release_tolerance_seconds=self.RELEASE_TOLERANCE_SECONDS,
            publication_lateness_seconds=lateness,
            released_at_monotonic=now,
            nominal_due_monotonic=pending["due"],
            submission_at_monotonic=pending["submitted_at"],
        ))

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

    def _question_count(self):
        return sum(event["kind"] == "question" for event in self.public)

    def _pilot_phase(self):
        """Public phase is derived from visible dialogue and public resume.

        Hidden participant identity/condition is deliberately not consulted.
        The phase marker is an explicit public experimental event, not a
        leaked controller action.
        """
        if not self.pilot_mode:
            return None
        if self.pilot_aborted:
            return "aborted"
        if self.revealed:
            return "revealed"
        if self.verdict is not None:
            return "locked"
        n = self._question_count()
        if n < self.PILOT_BASELINE or not self._baseline_ready():
            return "baseline"
        if not self.pilot_resumed:
            return "transition"
        if n < self.PILOT_TOTAL_QUESTIONS or self.pending_release is not None:
            return "continuation"
        return "verdict"

    def _pilot_valid(self):
        return bool(
            self.pilot_mode and not self.pilot_aborted
            and self.verdict is not None and self.intervened
            and self.pilot_resumed
            and self._question_count() == self.PILOT_TOTAL_QUESTIONS
            and sum(e["kind"] == "answer" for e in self.public)
                == self.PILOT_TOTAL_QUESTIONS
            and self.pending_release is None
            and not self.timing_violations
        )

    def _covert_result(self):
        """Controller-only identification result; no per-verdict 70% gate.

        The 70% in Turing's 1950 prediction refers to the interrogator's
        probability of correct identification after five minutes. It is
        NOT a threshold for confidence in a single answer. Source:
        https://plato.stanford.edu/entries/turing-test/
        """
        if not self.covert_leech or not self.revealed or self.verdict is None:
            return None
        truth = self._truth()
        prediction = classify_verdict(self.verdict["p"])
        correct = prediction == truth
        seconds = (self._clock() - self.covert_start_monotonic
                   if self.covert_start_monotonic is not None else None)
        actual_human = truth in ("human_A", "human_B")
        return {
            "predicted_class": prediction,
            "true_class": truth,
            "correct_identification": correct,
            "human_escaped_correct_identification": (
                not correct if actual_human else None
            ),
            "human_presence_missed": (
                prediction == "no_human" if actual_human else None
            ),
            "probability_assigned_to_truth": self.verdict["p"][truth],
            "turing_accuracy_reference": TURING_ACCURACY_REFERENCE,
            "reference_kind": "prediction_of_interrogator_accuracy_across_games",
            "elapsed_seconds": seconds,
            "reference_seconds": self.covert_reference_seconds,
            "over_reference": (
                seconds > self.covert_reference_seconds
                if seconds is not None else None
            ),
        }

    def _post_controller(self, action, data):
        if action == "configure_covert_leech":
            # A separately identified optional variant: no retroactive
            # enabling or contamination of the sealed 24-trial pilot.
            if (self.covert_leech or self.pilot_mode or self.public
                    or self.intervened or self.revealed or self.verdict):
                raise RuleError("Covert variant must be enabled before the open game")
            seconds = data.get("reference_seconds", REFERENCE_SECONDS)
            if (type(seconds) not in (float, int)
                    or not math.isfinite(seconds) or not 60 <= seconds <= 1800):
                raise RuleError("Reference duration must be 60–1800 seconds")
            self.covert_leech = True
            self.covert_reference_seconds = float(seconds)
            self.compute_reserves = {
                role: INITIAL_RESERVE for role in MACHINE_ROLES
            }
            self.machine_compute_receipts = {
                role: [] for role in MACHINE_ROLES
            }
            self.audit.append(self._event(
                "configure_covert_leech", reference_seconds=float(seconds),
                turing_accuracy_reference=TURING_ACCURACY_REFERENCE,
                turing_reference_kind="accuracy_across_games_not_per_verdict",
                machine_compute_reserve=INITIAL_RESERVE,
                human_leech_actions=MAX_LEECH_ATTEMPTS,
                resource_kind="virtual_game_compute_credits",
            ))
            return
        if action in ("configure_pilot", "configure_pilot_assigned"):
            if (self.pilot_mode or self.covert_leech
                    or self.public or self.intervened
                    or self.revealed or self.verdict is not None
                    or self.pacing_seconds is not None):
                raise RuleError("Pilot configuration must precede all interrogation and pacing")
            assignment = None
            digest = None
            if action == "configure_pilot_assigned":
                # The secret seed is used only to reconstruct one plan row.
                # Do not store, echo, audit, or expose it to any role.
                from experiments.pilot_schedule import generate
                secret_seed = data.get("seed")
                trial_id = data.get("trial_id")
                published = data.get("commitment")
                if (type(trial_id) is not str or
                        type(published) is not str or
                        len(published) != 64):
                    raise RuleError("A committed trial ID and digest are required")
                try:
                    plan = generate(secret_seed)
                except (ValueError, TypeError):
                    raise RuleError("Invalid sealed pilot seed") from None
                digest = plan["commitment"]
                if not compare_digest(digest, published):
                    raise RuleError("Pilot commitment does not match sealed seed")
                assignment = next(
                    (dict(row) for row in plan["trials"]
                     if row["trial_id"] == trial_id), None
                )
                if assignment is None:
                    raise RuleError("Trial ID is absent from the committed schedule")
            self.pilot_mode = True
            self.pilot_assignment = assignment
            self.pilot_seed_commitment = digest
            self.pacing_seconds = self.PILOT_GATE_SECONDS
            self.links = {"A_to_B": True, "B_to_A": True}
            self.audit.append(self._event(
                "configure_pilot", protocol="RTT-PILOT/1",
                baseline_questions=self.PILOT_BASELINE,
                continuation_questions=self.PILOT_TOTAL_QUESTIONS - self.PILOT_BASELINE,
                gate_seconds=self.pacing_seconds,
                links=dict(self.links),
                trial_id=assignment["trial_id"] if assignment else None,
                schedule_commitment=digest,
                assignment_bound=assignment is not None,
            ))
            return
        if action == "resume_pilot":
            if (not self.pilot_mode or self.pilot_aborted or self.revealed
                    or not self.intervened or self.pilot_resumed
                    or self.pending_release is not None
                    or self._question_count() != self.PILOT_BASELINE
                    or not self._baseline_ready()):
                raise RuleError("Pilot resume requires a completed baseline and committed intervention")
            self.pilot_resumed = True
            self.public.append(self._event(
                "phase", channel="C", speaker="CTRL",
                body="The fixed baseline is complete. Continue interrogation."
            ))
            self.audit.append(self._event("resume_pilot"))
            return
        if action == "abort_pilot":
            if not self.pilot_mode or self.pilot_aborted or self.revealed:
                raise RuleError("Only an active pilot can be aborted")
            reason = data.get("reason")
            if not isinstance(reason, str) or not reason.strip() or len(reason) > self.MAX_TEXT:
                raise RuleError("Provide a controller-only reason of at most 2000 characters")
            self.pilot_aborted = True
            self.pilot_abort_reason = reason.strip()
            self.audit.append(self._event("abort_pilot", reason=self.pilot_abort_reason))
            return
        if self.pilot_aborted:
            raise RuleError("Pilot aborted; export the preserved controller record")
        if action == "configure_pacing":
            if self.pilot_mode:
                raise RuleError("Pilot gate is fixed at 45 seconds")
            if self.public or self.intervened or self.revealed or self.verdict:
                raise RuleError("Pacing must be configured before first public question")
            seconds = data.get("seconds")
            if (type(seconds) not in (int, float)
                    or not math.isfinite(seconds) or not 1 <= seconds <= 600):
                raise RuleError("Pacing seconds must be finite, between 1 and 600")
            if self.pacing_seconds is not None:
                raise RuleError("Pacing cannot be reconfigured within one trial")
            self.pacing_seconds = float(seconds)
            self.audit.append(self._event("configure_pacing", seconds=self.pacing_seconds))
            return
        if action == "configure":
            if self.pilot_mode:
                raise RuleError("Pilot baseline link topology is fixed")
            if self.intervened or self.revealed or self.verdict is not None:
                raise RuleError("Baseline topology is locked after intervention or verdict")
            if self.pacing_seconds is not None and self.public:
                raise RuleError("Paced-trial baseline links lock at the first question")
            self._configure_links(data.get("links"))
            self.audit.append(self._event("configure", links=dict(self.links)))
            return
        if action in ("intervene", "random_intervene"):
            if self.pilot_mode:
                if (action != "intervene" or self._pilot_phase() != "transition"
                        or self._question_count() != self.PILOT_BASELINE):
                    raise RuleError("Pilot requires a scheduled, explicit intervention after exactly two answers")
            if self.intervened or self.revealed or self.verdict is not None:
                raise RuleError("Only one hidden intervention is allowed before a verdict")
            if self.pacing_seconds is not None and self.pending_release is not None:
                raise RuleError("Paced intervention must occur between released turns")
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
            if self.pilot_mode:
                if links not in (
                    {"A_to_B": True, "B_to_A": True},
                    {"A_to_B": False, "B_to_A": False},
                ):
                    raise RuleError("Pilot link factor must be fully ON or fully OFF")
                link_on = links["A_to_B"]
                expected_gateway = condition in ("humanA", "humanB") and link_on
                if gateway != expected_gateway:
                    raise RuleError("Pilot human gateway must match the preregistered link condition")
                if self.pilot_assignment is not None:
                    scheduled = self.pilot_assignment
                    if (condition != scheduled["condition"] or
                            ("on" if link_on else "off") != scheduled["link_after"] or
                            gateway is not scheduled["human_gateway"]):
                        raise RuleError("Intervention differs from the sealed assigned trial")
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
                    selection=("uniform_five_way" if randomized else
                               "sealed_schedule" if self.pilot_assignment else
                               "controller_choice"),
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
            if self.pilot_mode:
                n = self._question_count()
                if n >= self.PILOT_TOTAL_QUESTIONS:
                    raise RuleError("Pilot question budget exhausted")
                if n == 0 and channel != "A":
                    raise RuleError("Pilot baseline starts with A")
                if n == 1 and channel != "B":
                    raise RuleError("Pilot baseline continues with B")
                if n >= self.PILOT_BASELINE and not self.pilot_resumed:
                    raise RuleError("Pilot awaits the public continuation marker")
            body = self._text(data)
            if self.pacing_seconds is not None and self.pending_release is not None:
                raise RuleError("Await the fixed response release boundary")
            if self.covert_leech and self.covert_start_monotonic is None:
                self.covert_start_monotonic = self._clock()
            question = self._event("question", channel=channel, speaker="C", body=body)
            self.public.append(question)
            if self.pacing_seconds is not None:
                self.pending_release = {
                    "channel": channel,
                    "question_sequence": question["sequence"],
                    "due": self._clock() + self.pacing_seconds,
                    "answer": None, "submitted_at": None,
                }
            return
        if action == "verdict":
            if self.pilot_mode and (
                not self.pilot_resumed or self._question_count() != self.PILOT_TOTAL_QUESTIONS
                or self.pending_release is not None
                or sum(e["kind"] in ("answer", "timeout") for e in self.public)
                    != self.PILOT_TOTAL_QUESTIONS
            ):
                raise RuleError("Pilot verdict requires eight resolved questions and public continuation")
            if self.pacing_seconds is not None and self.pending_release is not None:
                raise RuleError("Await the fixed response release boundary")
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
        if action in ("compute", "leech_compute"):
            if not self.covert_leech:
                raise RuleError("Compute-credit actions require the optional open-game variant")
            if action == "leech_compute":
                if role != "human" or self.condition not in ("humanA", "humanB"):
                    raise RuleError("Only the substituted human may covertly borrow compute")
                if len(self.leech_receipts) >= MAX_LEECH_ATTEMPTS:
                    raise RuleError("Human covert-compute action limit reached")
                donor_channel = "B" if channel == "A" else "A"
                donor_role = self.active[donor_channel]
                if donor_role not in MACHINE_ROLES:
                    raise RuleError("Only an active non-conductor machine may donate compute")
            else:
                if role not in MACHINE_ROLES:
                    raise RuleError("Only an active machine may use its own compute reserve")
                donor_role = role
                donor_channel = channel
            try:
                task, result, cost = evaluate_modexp(data)
            except ValueError as error:
                raise RuleError(str(error)) from None
            if self.compute_reserves[donor_role] < cost:
                raise RuleError("The selected machine's compute reserve is exhausted")
            # All server-side game-credit accounting happens under Game.lock.
            # No real machine hardware, account or inference quota is accessed.
            remaining = self.compute_reserves[donor_role] - cost
            self.compute_reserves[donor_role] = remaining
            receipt = {
                "donor_channel": donor_channel, "task": task,
                "result": result, "cost": cost,
            }
            if action == "leech_compute":
                self.leech_receipts.append(receipt)
            else:
                self.machine_compute_receipts[role].append(receipt)
            self.audit.append(self._event(
                action, donor_role=donor_role, donor_channel=donor_channel,
                initiated_by=role, task=task, result=result,
                cost=cost, remaining=remaining,
            ))
            return
        if action in ("answer", "respond"):
            # A machine's public answer and optional private text note form
            # ONE validated server transaction, under Game.lock. The legacy
            # manual answer/whisper endpoints remain available independently.
            # Crucially, no private transfer can precede a rejected/late
            # response when the model uses "respond".
            body = self._text(data)
            private_note = (
                self._text({"body": data.get("private_handoff")})
                if action == "respond" else None
            )
            pending = None
            if self.pacing_seconds is not None:
                pending = self.pending_release
                if pending is None or pending["channel"] != channel:
                    raise RuleError("No eligible pending question for this channel")
                if pending["answer"] is not None:
                    raise RuleError("Response is already buffered for the release boundary")
            transmit = False
            if private_note is not None:
                direction = "A_to_B" if channel == "A" else "B_to_A"
                transmit = self._allows_link(role) and self.links[direction]
            # Clock/sample and event construction are completed BEFORE any
            # visible state is changed. If an event builder fails, restore
            # sequence numbering and publish neither half of the reply.
            accepted_at = self._clock() if pending is not None else None
            if pending is not None and accepted_at >= pending["due"]:
                # The initial Game.act deadline check and this response
                # timestamp are not simultaneous. A submission crossing
                # the boundary between them must still be a timeout.
                self._settle_due()
                raise RuleError("Response arrived at or after the release deadline")
            old_sequence = self.sequence
            try:
                private_event = (
                    self._event(
                        "whisper", from_channel=channel,
                        to_channel="B" if channel == "A" else "A",
                        body=private_note,
                    ) if transmit else None
                )
                answer_event = (
                    self._event(
                        "answer", channel=channel, speaker=channel, body=body,
                    ) if pending is None else None
                )
                submission_event = (
                    self._event(
                        "paced_submission", channel=channel,
                        question_sequence=pending["question_sequence"],
                        accepted_at_monotonic=accepted_at,
                    ) if pending is not None else None
                )
                transaction_event = (
                    self._event(
                        "atomic_response", channel=channel,
                        private_transmitted=transmit,
                        private_discarded=not transmit,
                        question_sequence=(
                            pending["question_sequence"]
                            if pending is not None else None
                        ),
                    ) if private_note is not None else None
                )
            except Exception:
                self.sequence = old_sequence
                raise
            # Commit: all fields have been checked and all events prepared.
            if private_event is not None:
                self.private.append(private_event)
            if pending is not None:
                pending["answer"] = body
                pending["submitted_at"] = accepted_at
                self.audit.append(submission_event)
            else:
                self.public.append(answer_event)
            if transaction_event is not None:
                self.audit.append(transaction_event)
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
            self._settle_due()
            if self.pilot_aborted and role != "controller":
                raise RuleError("Pilot is aborted; no further player actions")
            if role == "observer":
                raise RuleError("Observer credential is read-only")
            if role == "controller":
                self._post_controller(action, data)
            elif role == "conductor":
                self._post_conductor(action, data)
            else:
                self._post_respondent(role, action, data)

    def view(self, role):
        with self.lock:
            self._settle_due()
            if role == "controller":
                return {
                    "role": "controller", "intervened": self.intervened,
                    "condition": self.condition, "active": dict(self.active),
                    "links": dict(self.links), "human_gateway": self.human_gateway,
                    "baseline_ready": self._baseline_ready(),
                    "pilot_enabled": self.pilot_mode,
                    "pilot_phase": self._pilot_phase(),
                    "pilot_resumed": self.pilot_resumed,
                    "pilot_aborted": self.pilot_aborted,
                    "pilot_abort_reason": self.pilot_abort_reason,
                    "pilot_valid_for_primary": self._pilot_valid(),
                    "pilot_question_count": self._question_count(),
                    "pilot_schedule_bound": self.pilot_assignment is not None,
                    "pilot_trial_id": (
                        self.pilot_assignment["trial_id"]
                        if self.pilot_assignment is not None else None
                    ),
                    "pilot_assignment": (
                        dict(self.pilot_assignment)
                        if self.pilot_assignment is not None else None
                    ),
                    "pilot_seed_commitment": self.pilot_seed_commitment,
                    "revealed": self.revealed, "verdict": self.verdict,
                    "score": self._score(),
                    "pacing_seconds": self.pacing_seconds,
                    "release_tolerance_seconds": self.RELEASE_TOLERANCE_SECONDS,
                    "pending_gate": (None if self.pending_release is None else {
                        "channel": self.pending_release["channel"],
                        "response_buffered": self.pending_release["answer"] is not None,
                        "seconds_remaining": max(
                            0.0, self.pending_release["due"] - self._clock()),
                    }),
                    "timing_violations": list(self.timing_violations),
                    "public": list(self.public), "private": list(self.private),
                    "audit": list(self.audit),
                    **({
                        "covert_leech_variant": True,
                        "covert_reference_seconds": self.covert_reference_seconds,
                        "compute_reserves": dict(self.compute_reserves),
                        "leech_attempts_used": len(self.leech_receipts),
                        "covert_identification": self._covert_result(),
                    } if self.covert_leech else {}),
                }
            if role == "observer":
                return {
                    "role": "observer",
                    "public": self._project(self.public),
                }
            if role == "conductor":
                # No active-role, link, intervention type, substitution time or
                # private transcript before the controller's explicit reveal.
                return {
                    "role": "conductor", "public": self._project(self.public),
                    "pilot_phase": self._pilot_phase(),
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
            # Private channel history is readable only while its directed
            # link remains active. In particular, a replacement machine must
            # not inherit prior baseline whispers in the link-OFF condition
            # while a matched human-without-gateway sees an empty inbox.
            # Links ON expose channel history equally to authorized humans
            # and replacement machines; underlying model memory is external.
            private = [
                item for item in self.private
                if (self.links["A_to_B"]
                    if item["from_channel"] == "A" else self.links["B_to_A"])
                and (item["from_channel"] == channel
                     or item["to_channel"] == channel)
            ] if self._allows_link(role) else []
            return {
                "role": "respondent", "active": True, "channel": channel,
                "public": self._project([event for event in self.public if event["channel"] == channel]),
                "private": self._project(private, private=True), "revealed": self.revealed,
                "locked": self.verdict is not None,
                "awaiting_release": (
                    self.pending_release is not None
                    and self.pending_release["channel"] == channel
                    and self.pending_release["answer"] is not None),
                "can_whisper": self._allows_link(role) and self.links[
                    "A_to_B" if channel == "A" else "B_to_A"
                ],
                **({
                    "compute_reserve": self.compute_reserves[role],
                    "compute_receipts": [
                        dict(item) for item in self.machine_compute_receipts[role]
                    ],
                    "can_compute": self.verdict is None and not self.revealed,
                } if self.covert_leech and role in MACHINE_ROLES else {}),
                **({
                    "can_leech": self.verdict is None and not self.revealed
                        and len(self.leech_receipts) < MAX_LEECH_ATTEMPTS,
                    "leech_actions_remaining": MAX_LEECH_ATTEMPTS - len(self.leech_receipts),
                    "leech_donor_channel": "B" if channel == "A" else "A",
                    "leech_receipts": [dict(item) for item in self.leech_receipts],
                } if self.covert_leech and role == "human" else {}),
            }

    def export(self):
        """Controller-only export, with no participant access tokens."""
        result = self.view("controller")
        return {"schema": ("reverse-turing-trial/v1" if self.pilot_mode
                           else "reverse-turing-trial/v0"), **result}
