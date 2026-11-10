"""Conductor-side first-receipt log for the exact views used by Agent.step.

This wraps the conductor's EXISTING RelayClient. It observes the HTTP GET
return path of the actual model-driving process, without introducing receipt
times into prompts or adding a second polling connection.

Not a trusted timestamp authority, independent observer or model benchmark.
A separate reader must compare this log with the controller's release audit.
"""
from __future__ import annotations

import os
from pathlib import Path
import time

from .agents import AdapterError
from .observer import Witness, create_private_record, write_record


class ConductorReceipt:
    """Forward authenticated relay actions while logging exact conductor views.

    New file only. A first view containing an existing public transcript fails
    closed, because its earlier first-seen timestamps cannot be reconstructed.
    """

    def __init__(self, relay, output, trial_id: str, *, poll_seconds: float):
        if not isinstance(trial_id, str) or not trial_id.strip() or len(trial_id) > 80:
            raise AdapterError("Conductor receipt trial ID must contain 1–80 characters")
        if type(poll_seconds) not in (float, int) or not 0.1 <= poll_seconds <= 60:
            raise AdapterError("Conductor receipt requires bounded polling cadence")
        self._relay = relay
        self._witness = Witness(expected_role="conductor")
        self._closed = False
        self._handle = create_private_record(Path(output))
        try:
            write_record(self._handle, {
                "type": "conductor_receipt_header",
                "schema": "reverse-turing-conductor-receipt/v1",
                "trial_id": trial_id,
                "role": "conductor",
                "poll_seconds": float(poll_seconds),
                "clock": "python_time_monotonic_ns_on_conductor_host",
                "scope": "HTTP response completed in actual Agent.step() client",
                "started_wall_utc_ns": time.time_ns(),
                "source": "model_driving_client_not_independent_attestation",
            })
        except BaseException:
            self._handle.close()
            raise

    def view(self):
        if self._closed:
            raise AdapterError("Conductor receipt log is closed")
        started = time.monotonic_ns()
        view = self._relay.view()
        completed = time.monotonic_ns()
        rows = self._witness.sample(
            view,
            request_start_ns=started,
            response_end_ns=completed,
            wall_end_ns=time.time_ns(),
        )
        # Include each poll, including unchanged transcripts. This makes
        # gaps and time spent blocked outside polling visible to the auditor.
        write_record(self._handle, {
            "type": "conductor_poll",
            "request_started_monotonic_ns": started,
            "response_complete_monotonic_ns": completed,
            "public_event_count": len(view["public"]),
        })
        for row in rows:
            write_record(self._handle, row)
        # The exact same view, unmodified and without timing fields, flows
        # into Agent._conductor_step and then into the model's prompt builder.
        return view

    def act(self, action, **data):
        if self._closed:
            raise AdapterError("Conductor receipt log is closed")
        return self._relay.act(action, **data)

    def close(self, status="incomplete"):
        if self._closed:
            return
        self._closed = True
        try:
            write_record(self._handle, {
                "type": "conductor_receipt_end",
                "status": status,
                "last_sequence": self._witness.last_sequence,
                "finished_wall_utc_ns": time.time_ns(),
            })
        finally:
            self._handle.close()
