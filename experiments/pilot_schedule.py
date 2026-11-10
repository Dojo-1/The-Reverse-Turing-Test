"""Preregistered 24-trial pilot schedule (generation only; no gameplay).

The SHA-256 commitment is a tamper-evidence mechanism for the private seed,
NOT independently witnessed randomness or a replacement for blinded execution.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import random
import secrets


PROTOCOL = "rtt-pilot-origin-x-link/v1"
CELLS = (
    ("human", "on", 3, 2),
    ("human", "off", 2, 3),
    ("machine", "on", 2, 3),
    ("machine", "off", 3, 2),
)


def commitment(seed: str) -> str:
    if not isinstance(seed, str) or len(seed) != 64:
        raise ValueError("Expected a 32-byte seed represented by 64 hex characters")
    try:
        seed_bytes = bytes.fromhex(seed)
    except ValueError as exc:
        raise ValueError("Pilot seed is not hexadecimal") from exc
    return hashlib.sha256(b"RTT-PILOT-V1\x00" + seed_bytes).hexdigest()


def generate(seed: str) -> dict:
    digest = commitment(seed)
    rows = []
    for origin, link, count_a, count_b in CELLS:
        for side, count in (("A", count_a), ("B", count_b)):
            for _ in range(count):
                rows.append({
                    "origin": origin,
                    "condition": origin + side,
                    "link_after": link,
                    "human_gateway": origin == "human" and link == "on",
                })
    for link in ("on", "off"):
        for _ in range(2):
            rows.append({
                "origin": "unchanged",
                "condition": "unchanged",
                "link_after": link,
                "human_gateway": False,
            })
    assert len(rows) == 24
    rng = random.Random(int(seed, 16))
    rng.shuffle(rows)
    for i, row in enumerate(rows, 1):
        row["trial_id"] = f"RTT-{i:02d}"
    return {"protocol": PROTOCOL, "commitment": digest, "seed": seed, "trials": rows}


def public_commitment(private_plan: dict) -> dict:
    counts = Counter(
        (r["origin"], r["link_after"]) for r in private_plan["trials"]
    )
    return {
        "protocol": PROTOCOL,
        "sha256_seed_commitment": private_plan["commitment"],
        "trial_count": len(private_plan["trials"]),
        "factorial_counts": {
            origin + "/" + link: counts[(origin, link)]
            for origin in ("human", "machine", "unchanged")
            for link in ("on", "off")
        },
        "seed_revealed": False,
        "note": "Publish before trials; keep private schedule and seed sealed until final analysis.",
    }


def exclusive_json(path: Path, record: dict, mode: int) -> None:
    """Never overwrite existing schedules or commitments."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(str(path), flags, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(record, stream, sort_keys=True, indent=2)
        stream.write("\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate blinded RTT pilot schedule")
    parser.add_argument("--private-output", required=True)
    parser.add_argument("--public-output", required=True)
    args = parser.parse_args(argv)
    private_path = Path(args.private_output).expanduser()
    public_path = Path(args.public_output).expanduser()
    if private_path.resolve() == public_path.resolve():
        parser.error("Private schedule and public commitment must be different files")
    if private_path.exists() or public_path.exists():
        parser.error("Refusing to overwrite an existing artifact")
    seed = os.environ.get("RTT_PILOT_SEED") or secrets.token_hex(32)
    plan = generate(seed)
    exclusive_json(private_path, plan, 0o600)
    exclusive_json(public_path, public_commitment(plan), 0o644)
    print("Schedule created privately; seed NOT printed.")
    print("Commitment:", plan["commitment"])
    print("Trials:", len(plan["trials"]))
    print("Keep private schedule secret until every verdict is locked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
