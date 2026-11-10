"""R8: conditional same-host timing comparison for a conductor's ACTUAL client.

The conductor trace comes from the model-driving HTTP client, not R5's
separate observer connection. Both streams are self-authored software, and
their monotonic clocks are comparable ONLY if relay and conductor actually
ran in the same OS clock domain. This tool cannot attest that physical fact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

RECEIPT_SCHEMA = "reverse-turing-conductor-receipt/v1"
MAX_DELIVERY_LAG_SECONDS = 1.0


def _payload_hash(event: dict) -> str:
    public = {
        key: event[key] for key in ("kind", "channel", "speaker", "body")
    }
    data = json.dumps(
        public, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _real_number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def assess_delivery(controller: dict, trace: list[dict], *,
                    require_complete_pilot: bool = True) -> dict:
    """Return a full error ledger, including failed or missing timing evidence.

    A passing value is conditional on the unverified same-host clock assumption,
    and does NOT certify experimental independence or causal conclusions.
    """
    errors = []
    rows = []
    status = {
        "schema": "reverse-turing-delivery-check/v1",
        "clock_comparability": "assumed_same_host_not_independently_attested",
        "source": "conductor_model_driving_process",
        "n_paced_responses": 0,
        "max_delivery_lag_ms": None,
        "within_one_second_given_same_clock": False,
        "confirmatory_ready": False,
        "proves_intelligence_or_origin": False,
        "errors": errors,
        "responses": rows,
    }

    def need(ok, error):
        if not ok and error not in errors:
            errors.append(error)

    if not isinstance(controller, dict) or not isinstance(trace, list):
        errors.append("invalid_inputs")
        return status
    if not trace or any(not isinstance(row, dict) for row in trace):
        errors.append("missing_or_malformed_conductor_receipt")
        return status

    header, tail = trace[0], trace[-1]
    need(header.get("type") == "conductor_receipt_header"
         and header.get("schema") == RECEIPT_SCHEMA
         and header.get("role") == "conductor", "receipt_header_invalid")
    need(tail.get("type") == "conductor_receipt_end",
         "receipt_end_missing")
    if require_complete_pilot:
        need(tail.get("status") in ("verdict", "done"),
             "conductor_did_not_complete_verdict")
        need(controller.get("schema") == "reverse-turing-trial/v1"
             and controller.get("pilot_enabled") is True,
             "not_strict_pilot_export")
        need(controller.get("pilot_valid_for_primary") is True,
             "server_says_pilot_invalid")
        need(controller.get("revealed") is True,
             "controller_not_revealed")
    else:
        need(controller.get("pacing_seconds") is not None,
             "rehearsal_without_pacing")

    public, audit = controller.get("public"), controller.get("audit")
    if (not isinstance(public, list) or not isinstance(audit, list)
            or any(not isinstance(row, dict) for row in public + audit)):
        errors.append("controller_events_malformed")
        return status

    try:
        public = sorted(public, key=lambda row: row["sequence"])
        if any(type(e["sequence"]) is not int or
               e["sequence"] <= 0 for e in public):
            raise ValueError("invalid public indexes")
        hashes = [_payload_hash(e) for e in public]
    except (KeyError, TypeError, ValueError):
        errors.append("controller_public_payload_invalid")
        return status

    event_reads = [
        e for e in trace if e.get("type") == "public_event_first_seen"
    ]
    polls = [e for e in trace if e.get("type") == "conductor_poll"]
    need(len(polls) > 0, "no_conductor_polls")
    need(len(event_reads) == len(public), "missing_conductor_event_reads")
    need([e.get("sequence") for e in event_reads] ==
         list(range(1, len(public) + 1)), "non_dense_conductor_event_reads")
    need(tail.get("last_sequence") == len(public),
         "receipt_end_history_incomplete")

    # The first request must have started with an empty public history.
    if polls:
        need(polls[0].get("public_event_count") == 0,
             "conductor_log_started_after_public_events")
    prev_end = None
    poll_keys = set()
    for p in polls:
        start, end, count = (
            p.get("request_started_monotonic_ns"),
            p.get("response_complete_monotonic_ns"),
            p.get("public_event_count"),
        )
        if (type(start) is not int or type(end) is not int
                or type(count) is not int or start > end
                or count < 0 or count > len(public)
                or (prev_end is not None and prev_end > start)):
            errors.append("conductor_poll_clock_or_order_invalid")
            break
        prev_end = end
        poll_keys.add((start, end, count))

    receipt_by_local_seq = {}
    for i, event in enumerate(event_reads):
        seq = event.get("sequence")
        start = event.get("request_started_monotonic_ns")
        end = event.get("response_complete_monotonic_ns")
        if (type(seq) is not int or type(start) is not int
                or type(end) is not int or start > end):
            errors.append("conductor_event_clock_invalid")
            continue
        if i < len(hashes) and event.get("payload_sha256") != hashes[i]:
            errors.append("conductor_event_digest_mismatch")
        if not any(pstart == start and pend == end and count >= seq
                   for pstart, pend, count in poll_keys):
            errors.append("conductor_event_not_from_logged_poll")
        receipt_by_local_seq[seq] = event

    # An explicit paced_release audit receipt is necessary for each answer.
    releases = [e for e in audit if e.get("kind") == "paced_release"]
    release_by_question = {}
    for release in releases:
        seq = release.get("question_sequence")
        if type(seq) is not int or seq in release_by_question:
            errors.append("duplicate_or_invalid_server_release")
        else:
            release_by_question[seq] = release

    pending = None
    latencies = []
    paired = 0
    for idx, event in enumerate(public, 1):
        kind = event.get("kind")
        if kind == "question":
            if pending is not None:
                errors.append("overlapping_public_questions")
            pending = event
        elif kind in ("answer", "timeout"):
            if pending is None:
                errors.append("unpaired_public_answer")
                continue
            q = pending
            pending = None
            paired += 1
            release = release_by_question.get(q["sequence"])
            if release is None:
                errors.append("server_release_missing_for_question")
                continue
            need(release.get("channel") == event.get("channel") ==
                 q.get("channel"), "release_channel_mismatch")
            need(release.get("submitted") is (kind == "answer"),
                 "release_submitted_flag_mismatch")
            raw_time = release.get("released_at_monotonic")
            due_time = release.get("nominal_due_monotonic")
            if not _real_number(raw_time) or not _real_number(due_time):
                errors.append("server_release_clock_invalid")
                continue
            if raw_time < due_time - 0.001:
                errors.append("server_published_before_gate")
            reading = receipt_by_local_seq.get(idx)
            if reading is None:
                errors.append("missing_answer_at_conductor")
                continue
            received_ns = reading.get("response_complete_monotonic_ns")
            if type(received_ns) is not int:
                errors.append("conductor_receipt_clock_invalid")
                continue
            lag = received_ns / 1e9 - raw_time
            lag_ms = round(lag * 1000, 3)
            latencies.append(lag_ms)
            rows.append({
                "response_local_sequence": idx,
                "question_global_sequence": q["sequence"],
                "channel": event.get("channel"),
                "kind": kind,
                "server_publication_monotonic_seconds": raw_time,
                "conductor_http_complete_monotonic_seconds": received_ns / 1e9,
                "delivery_lag_ms_assuming_same_clock": lag_ms,
            })
            if kind == "timeout":
                errors.append("server_answer_deadline_missed")
            if lag < -0.005:
                errors.append("negative_delivery_lag_or_clock_domain_mismatch")
            if lag > MAX_DELIVERY_LAG_SECONDS:
                errors.append("conductor_receipt_exceeds_one_second")
    need(pending is None, "last_question_unanswered")
    need(len(releases) == paired, "release_count_disagrees_with_answers")
    need(controller.get("timing_violations") == [],
         "internal_server_timing_violations")
    if require_complete_pilot:
        need(paired == 8 and len(rows) == 8, "pilot_needs_eight_paced_answers")
    else:
        need(paired > 0, "rehearsal_needs_at_least_one_answer")

    status["n_paced_responses"] = len(rows)
    status["max_delivery_lag_ms"] = max(latencies) if latencies else None
    status["within_one_second_given_same_clock"] = not errors
    return status


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("Could not parse controller export JSON") from exc


def _read_jsonl(path: Path):
    try:
        return [json.loads(line) for line in path.read_text(
            encoding="utf-8"
        ).splitlines() if line.strip()]
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("Could not parse conductor receipt JSONL") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description="R8 conductor client delivery audit")
    parser.add_argument("--controller-export", required=True)
    parser.add_argument("--conductor-receipt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--rehearsal", action="store_true",
                        help="permit an incomplete non-pilot timing rehearsal")
    args = parser.parse_args(argv)
    try:
        output = Path(args.output)
        if output.exists():
            raise ValueError("Refusing to overwrite an existing timing audit")
        controller = _read_json(Path(args.controller_export))
        receipt = _read_jsonl(Path(args.conductor_receipt))
        report = assess_delivery(
            controller, receipt, require_complete_pilot=not args.rehearsal
        )
        fd = os.open(str(output), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(report, out, sort_keys=True, indent=2)
            out.write("\n")
        print("Conductor HTTP delivery (conditional on same host):",
              "PASS" if report["within_one_second_given_same_clock"] else "FAIL")
        print("Recorded responses:", report["n_paced_responses"],
              "max lag (ms):", report["max_delivery_lag_ms"])
        print("Research confirmation: NOT ESTABLISHED")
        return 0 if report["within_one_second_given_same_clock"] else 2
    except (OSError, ValueError, TypeError) as exc:
        print("Delivery audit error:", str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
