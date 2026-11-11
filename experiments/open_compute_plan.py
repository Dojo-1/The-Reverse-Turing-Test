"""Prepare a private randomized RTT-OPEN-COMPUTE/1 plan and a public hash.

Publish the public commitment to an independent witness BEFORE observing any
real session. This generator does not create a trusted timestamp or enroll users.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import secrets

from .analyze_open_compute import CELL_COUNTS, PROTOCOL


def generate_plan(seed_hex=None):
    seed_hex = secrets.token_hex(32) if seed_hex is None else seed_hex
    if not isinstance(seed_hex, str) or not re.fullmatch(r"[0-9a-f]{64}", seed_hex):
        raise ValueError("Private seed must be 64 lowercase hex characters")
    assignments = [
        {"arm": arm, "condition": condition}
        for (arm, condition), count in CELL_COUNTS.items()
        for _ in range(count)
    ]
    random.Random(int(seed_hex, 16)).shuffle(assignments)
    for index, row in enumerate(assignments, 1):
        row["trial_id"] = f"RTO-{index:02d}"
    return {"protocol": PROTOCOL, "seed_hex": seed_hex, "assignments": assignments}


def _new_text_file(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as out:
        out.write(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-output", required=True)
    parser.add_argument("--public-output", required=True)
    args = parser.parse_args(argv)
    private = Path(args.private_output)
    public = Path(args.public_output)
    if private.resolve() == public.resolve() or private.exists() or public.exists():
        parser.error("Refusing to overwrite an existing plan or commitment")
    plan = generate_plan()
    raw = (json.dumps(plan, indent=2, sort_keys=True) + "\n").encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    commitment = {
        "protocol": PROTOCOL, "trial_count": 32,
        "private_manifest_sha256": digest,
        "disclose_seed_only_after_final_locked_verdict": True,
    }
    _new_text_file(private, raw.decode("utf-8"))
    _new_text_file(public, json.dumps(commitment, indent=2, sort_keys=True) + "\n")
    print("Publish this commitment to an independent witness before any session: " + digest)


if __name__ == "__main__":
    main()
