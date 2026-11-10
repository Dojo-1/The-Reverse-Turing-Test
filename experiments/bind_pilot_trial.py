"""Bind one strict-pilot run to the previously sealed 24-trial schedule.

The secret seed is sent only to the *local* controller-authenticated relay,
then discarded by the server after deriving that trial's assignment. It is
not stored in server audit, controller export or participant views.
No commitment mechanism independently attests pre-study publication.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .analyze_pilot import EvidenceError, check_private_schedule
from .pilot_schedule import PROTOCOL
from game.agents import AdapterError, RelayClient


def _load(path: str):
    try:
        with Path(path).open(encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, UnicodeError, ValueError) as error:
        raise EvidenceError("Cannot load a valid sealed schedule/commitment") from error


def assigned_row(plan, trial_id):
    """Resolve a committed row, failing closed on duplicates or unknown IDs."""
    matches = [
        row for row in plan["trials"] if row.get("trial_id") == trial_id
    ]
    if len(matches) != 1:
        raise EvidenceError("Trial ID must name exactly one sealed assignment")
    return matches[0]


def bind(relay, plan, published, trial_id, *, dry_run=False):
    check_private_schedule(plan, published)
    if plan["protocol"] != PROTOCOL:
        raise EvidenceError("Unexpected pilot schedule protocol")
    row = assigned_row(plan, trial_id)
    if dry_run:
        return dict(row)
    current = relay.view()
    if current.get("role") != "controller":
        raise AdapterError("Schedule binding requires a controller role token")
    if (current.get("pilot_enabled") or current.get("public")
            or current.get("intervened") or current.get("pacing_seconds") is not None):
        raise AdapterError("Bind an assignment only in a fresh, untouched trial")
    relay.act(
        "configure_pilot_assigned", seed=plan["seed"],
        trial_id=trial_id, commitment=plan["commitment"],
    )
    after = relay.view()
    if (after.get("pilot_schedule_bound") is not True
            or after.get("pilot_assignment") != row
            or after.get("pilot_seed_commitment") != plan["commitment"]
            or after.get("pilot_trial_id") != trial_id):
        raise AdapterError("Server did not confirm the committed assignment")
    return dict(row)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Lock local pilot server to one sealed 24-trial assignment"
    )
    parser.add_argument("--private-schedule", required=True)
    parser.add_argument("--public-commitment", required=True)
    parser.add_argument("--trial-id", required=True)
    parser.add_argument("--relay", default="http://127.0.0.1:8765")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        plan = _load(args.private_schedule)
        public = _load(args.public_commitment)
        if args.dry_run:
            row = bind(None, plan, public, args.trial_id, dry_run=True)
            print("Validated sealed assignment:", row["trial_id"])
            print("No relay action performed. Keep this row confidential.")
        else:
            relay = RelayClient(args.relay, os.environ.get("RTT_ROLE_TOKEN", ""))
            row = bind(relay, plan, public, args.trial_id)
            print("Pilot assignment bound:", row["trial_id"])
            print("Server will reject any different intervention.")
            print("Seed and participant credentials have not been printed.")
        return 0
    except (EvidenceError, AdapterError, OSError, TypeError, KeyError) as error:
        print("Pilot binding failed:", str(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
