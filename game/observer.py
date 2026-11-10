"""Read-only local timing witness for the Reverse Turing Game.

A separate observer token can poll the same public transcript as C and record
when events FIRST become visible to its own HTTP client. This is a separate
reference path, not proof of the conductor's actual delivery time and not
independent authorship or a synchronization protocol.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from .agents import AdapterError, RelayClient


class Witness:
    """Stateful first-observation intervals for an explicitly public view."""

    def __init__(self, *, require_empty_start=True):
        self.last_sequence = 0
        self.last_poll_end_ns = None
        self.initialized = False
        self.require_empty_start = require_empty_start

    def sample(self, view, *, request_start_ns, response_end_ns, wall_end_ns):
        if view.get("role") != "observer":
            raise AdapterError("Witness requires a separate observer credential")
        events = view.get("public")
        if not isinstance(events, list):
            raise AdapterError("Observer did not receive an event list")
        if request_start_ns > response_end_ns:
            raise AdapterError("Invalid local monotonic clock ordering")
        if not self.initialized:
            self.initialized = True
            if events and self.require_empty_start:
                raise AdapterError(
                    "Witness started after public events: cannot certify first-observation windows"
                )
        if len(events) < self.last_sequence:
            raise AdapterError("Observer history unexpectedly shrank")
        if any(event.get("sequence") != i for i, event in enumerate(events, 1)):
            raise AdapterError("Observer event indexing is non-dense or modified")
        rows = []
        for event in events[self.last_sequence:]:
            public = {
                "kind": event["kind"], "channel": event["channel"],
                "speaker": event["speaker"], "body": event["body"],
            }
            canonical = json.dumps(
                public, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            rows.append({
                "type": "public_event_first_seen",
                "sequence": event["sequence"],
                "kind": public["kind"],
                "channel": public["channel"],
                "payload_sha256": hashlib.sha256(canonical).hexdigest(),
                "payload_bytes": len(canonical),
                "request_started_monotonic_ns": request_start_ns,
                "response_complete_monotonic_ns": response_end_ns,
                "previous_poll_complete_monotonic_ns": self.last_poll_end_ns,
                "response_complete_wall_utc_ns": wall_end_ns,
                "interval_bounded_by_polls": self.last_poll_end_ns is not None,
            })
        self.last_sequence = len(events)
        self.last_poll_end_ns = response_end_ns
        return rows


def create_private_record(path: Path):
    path = path.expanduser()
    if path.exists():
        raise AdapterError("Refusing to overwrite an existing witness record")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    return os.fdopen(fd, "w", encoding="utf-8")


def write_record(handle, value):
    handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
    handle.flush()


def main(argv=None):
    parser = argparse.ArgumentParser(description="R5 read-only public timing witness")
    parser.add_argument("--relay", default="http://127.0.0.1:8765")
    parser.add_argument("--output", required=True,
                        help="new private JSONL path (must not already exist)")
    parser.add_argument("--trial-id", required=True)
    parser.add_argument("--poll-seconds", type=float, default=.1)
    parser.add_argument("--duration-seconds", type=float, default=1800)
    args = parser.parse_args(argv)
    try:
        if not 0.02 <= args.poll_seconds <= 3:
            raise AdapterError("Poll interval must be between 20ms and 3s")
        if not 1 <= args.duration_seconds <= 14400:
            raise AdapterError("Duration must be between 1 and 14400 seconds")
        if len(args.trial_id) > 80 or not args.trial_id.strip():
            raise AdapterError("Trial ID must contain 1–80 characters")
        relay = RelayClient(args.relay, os.environ.get("RTT_ROLE_TOKEN", ""))
        witness = Witness()
        # Reject a late-starting witness before creating a seemingly complete file.
        t0 = time.monotonic_ns()
        first = relay.view()
        t1 = time.monotonic_ns()
        witness.sample(
            first, request_start_ns=t0,
            response_end_ns=t1, wall_end_ns=time.time_ns(),
        )
        with create_private_record(Path(args.output)) as handle:
            write_record(handle, {
                "type": "witness_header",
                "schema": "reverse-turing-observer/v1",
                "trial_id": args.trial_id,
                "poll_seconds": args.poll_seconds,
                "started_wall_utc_ns": time.time_ns(),
                "observer_scope": "own first HTTP visibility, not conductor reception",
            })
            print("Read-only witness active (credentials not logged).", flush=True)
            deadline = time.monotonic() + args.duration_seconds
            while time.monotonic() < deadline:
                time.sleep(args.poll_seconds)
                started = time.monotonic_ns()
                view = relay.view()
                ended = time.monotonic_ns()
                for row in witness.sample(
                    view, request_start_ns=started,
                    response_end_ns=ended, wall_end_ns=time.time_ns(),
                ):
                    write_record(handle, row)
            write_record(handle, {
                "type": "witness_end", "last_sequence": witness.last_sequence,
                "finished_wall_utc_ns": time.time_ns(),
            })
        return 0
    except (AdapterError, OSError, ValueError) as error:
        print("Timing witness error:", str(error), flush=True)
        return 2
    except KeyboardInterrupt:
        print("Timing witness interrupted; incomplete record.", flush=True)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
