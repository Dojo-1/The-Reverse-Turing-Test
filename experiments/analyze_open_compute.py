"""R14 read-only analysis of an independently committed OPEN-COMPUTE/1 schedule.

No live sessions, model APIs, participant recruitment, or remote mutation.
All values are descriptive; synthetic test fixtures are not observations.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re

PROTOCOL = "RTT-OPEN-COMPUTE/1"
ARMS = ("no_borrow", "borrow_permitted")
CONDITIONS = ("humanA", "humanB", "machineA", "machineB", "unchanged")
CLASSES = ("no_human", "human_A", "human_B")
TRUTHS = {
    "humanA": "human_A", "humanB": "human_B",
    "machineA": "no_human", "machineB": "no_human",
    "unchanged": "no_human",
}
CELL_COUNTS = {
    (arm, condition): (4 if condition in ("humanA", "humanB", "unchanged") else 2)
    for arm in ARMS for condition in CONDITIONS
}


def _prediction(p):
    maximum = max(p.values())
    winners = [key for key in CLASSES if p[key] == maximum]
    return winners[0] if len(winners) == 1 else "undecided"


def _finite_probability_vector(p):
    return (isinstance(p, dict) and set(p) == set(CLASSES)
            and all(type(p[k]) in (float, int) and math.isfinite(p[k])
                    and 0 <= p[k] <= 1 for k in CLASSES)
            and abs(sum(p.values()) - 1.0) <= 1e-6)


def read_plan(plan_path, committed_sha256):
    if not isinstance(committed_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", committed_sha256):
        raise ValueError("Expected a lowercase 64-hex manifest SHA-256")
    raw = Path(plan_path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != committed_sha256:
        raise ValueError("Manifest differs from the externally committed SHA-256")
    plan = json.loads(raw)
    if not isinstance(plan, dict) or plan.get("protocol") != PROTOCOL:
        raise ValueError("Wrong open-compute protocol")
    rows = plan.get("assignments")
    if not isinstance(rows, list) or len(rows) != 32:
        raise ValueError("Exactly 32 assignments required")
    ids = [f"RTO-{i:02d}" for i in range(1, 33)]
    if any(not isinstance(r, dict) or set(r) != {"trial_id", "arm", "condition"}
           for r in rows):
        raise ValueError("Each assignment needs only trial_id, arm and condition")
    if [r["trial_id"] for r in rows] != ids:
        raise ValueError("Expected unique RTO-01 through RTO-32 trial identifiers in order")
    if Counter((r["arm"], r["condition"]) for r in rows) != CELL_COUNTS:
        raise ValueError("The declared 32-trial factorial allocation is unbalanced")
    seed = plan.get("seed_hex")
    if not isinstance(seed, str) or not re.fullmatch(r"[0-9a-f]{64}", seed):
        raise ValueError("Missing private schedule seed")
    # Lazy import avoids a module cycle when running the plan generator.
    from .open_compute_plan import generate_plan
    if rows != generate_plan(seed)["assignments"]:
        raise ValueError("Assignment order differs from private seeded shuffle")
    return rows, digest


def validate_record(record, row):
    """Return (errors, scored row); never infer an absent observation."""
    errors = []
    if not isinstance(record, dict):
        return ["invalid_json_record"], None
    if record.get("schema") != "reverse-turing-trial/v0":
        errors.append("wrong_open_game_schema")
    if record.get("pilot_enabled") is not False or record.get("pilot_schedule_bound") is not False:
        errors.append("strict_pilot_contamination")
    if record.get("covert_leech_variant") is not True:
        errors.append("covert_variant_not_enabled")
    if record.get("condition") != row["condition"]:
        errors.append("hidden_condition_mismatch")
    if record.get("pacing_seconds") != 30.0 or record.get("timing_violations") != []:
        errors.append("pacing_not_equalized_or_violation")
    if record.get("revealed") is not True or record.get("intervened") is not True:
        errors.append("trial_not_completed")
    public = record.get("public")
    if not isinstance(public, list) or len(public) != 16:
        errors.append("not_eight_public_qa_pairs")
    else:
        for i in range(8):
            question, answer = public[2*i:2*i+2]
            if (not isinstance(question, dict) or question.get("kind") != "question"
                    or not isinstance(answer, dict) or answer.get("kind") != "answer"
                    or answer.get("channel") != question.get("channel")):
                errors.append("question_answer_sequence_invalid")
                break
            if i < 2 and question.get("channel") != ("A", "B")[i]:
                errors.append("genuine_baseline_order_invalid")
                break
    audit = record.get("audit")
    if not isinstance(audit, list) or any(not isinstance(e, dict) for e in audit):
        return errors + ["missing_or_invalid_audit"], None
    def events(name):
        return [e for e in audit if e.get("kind") == name]
    config, intervention, verdict, reveal = (
        events("configure_covert_leech"), events("intervene"),
        events("verdict"), events("reveal")
    )
    if not all(len(x) == 1 for x in (config, intervention, verdict, reveal)):
        errors.append("incomplete_or_duplicated_controller_events")
        moment = None
        verdict_moment = None
    else:
        c, i, v, r = (x[0]["sequence"] for x in (config, intervention, verdict, reveal))
        moment, verdict_moment = i, v
        if not (c < i < v < r):
            errors.append("controller_event_order_invalid")
        if intervention[0].get("condition") != row["condition"]:
            errors.append("intervention_audit_mismatch")
        if isinstance(public, list) and len(public) == 16:
            try:
                if not (public[3]["sequence"] < i < public[4]["sequence"]):
                    errors.append("substitution_not_after_two_baseline_answers")
            except (KeyError, TypeError):
                errors.append("missing_public_sequence_metadata")
    leeches = events("leech_compute")
    if record.get("leech_attempts_used") != len(leeches):
        errors.append("leech_counter_mismatch")
    if len(leeches) > 3:
        errors.append("leech_cap_exceeded")
    if row["arm"] == "no_borrow" and leeches:
        errors.append("control_arm_borrowing_violation")
    if row["condition"] not in ("humanA", "humanB") and leeches:
        errors.append("nonhuman_trial_contains_leech")
    expected_donor = "machine_B" if row["condition"] == "humanA" else "machine_A"
    for item in leeches:
        if item.get("initiated_by") != "human" or item.get("donor_role") != expected_donor:
            errors.append("invalid_leech_origin_or_donor")
        if (moment is None or verdict_moment is None
                or not (moment < item.get("sequence", -1) < verdict_moment)):
            errors.append("leech_outside_active_human_window")
    p = (record.get("verdict") or {}).get("p") if isinstance(record.get("verdict"), dict) else None
    identification = record.get("covert_identification")
    if not _finite_probability_vector(p) or not isinstance(identification, dict):
        errors.append("missing_or_invalid_locked_identification")
        return sorted(set(errors)), None
    truth = TRUTHS[row["condition"]]
    prediction = _prediction(p)
    if (identification.get("true_class") != truth
            or identification.get("predicted_class") != prediction
            or identification.get("correct_identification") is not (prediction == truth)):
        errors.append("identification_inconsistent_with_verdict")
    reported = identification.get("probability_assigned_to_truth")
    if type(reported) not in (float, int) or not math.isclose(reported, p[truth], abs_tol=1e-6):
        errors.append("probability_assigned_to_truth_mismatch")
    if truth == "no_human":
        if (identification.get("human_escaped_correct_identification") is not None
                or identification.get("human_presence_missed") is not None):
            errors.append("nonhuman_detection_fields_not_null")
    elif (identification.get("human_escaped_correct_identification") is not (prediction != truth)
          or identification.get("human_presence_missed") is not (prediction == "no_human")):
        errors.append("human_detection_fields_inconsistent")
    seconds = identification.get("elapsed_seconds")
    if (type(seconds) not in (float, int) or not math.isfinite(seconds) or seconds < 0
            or identification.get("over_reference") is not (seconds > 300)):
        errors.append("invalid_reference_time_annotation")
    if errors:
        return sorted(set(errors)), None
    return [], {
        "trial_id": row["trial_id"], "arm": row["arm"],
        "condition": row["condition"], "true_class": truth,
        "predicted_class": prediction, "correct": prediction == truth,
        "human_escape": prediction != truth if truth != "no_human" else None,
        "human_presence_missed": prediction == "no_human" if truth != "no_human" else None,
        "false_human": prediction != "no_human" if truth == "no_human" else None,
        "leech_count": len(leeches), "p_truth": p[truth],
    }


def analyze(plan_path, records_dir, committed_sha256):
    assignments, digest = read_plan(plan_path, committed_sha256)
    rows, observations = [], []
    path = Path(records_dir)
    for row in assignments:
        fname = path / (row["trial_id"] + ".json")
        if not fname.is_file():
            rows.append({**row, "status": "missing", "errors": ["missing_record"]})
            continue
        try:
            errors, scored = validate_record(json.loads(fname.read_text(encoding="utf-8")), row)
        except (OSError, ValueError, TypeError, KeyError) as err:
            errors, scored = ["unreadable_or_malformed_record"], None
        if errors:
            rows.append({**row, "status": "invalid", "errors": errors})
        else:
            observations.append(scored)
            rows.append({**row, "status": "valid", "errors": []})
    expected_files = {a["trial_id"] + ".json" for a in assignments}
    extras = sorted(p.name for p in path.glob("*.json") if p.name not in expected_files)
    if extras:
        rows.append({"status": "unexpected_files", "files": extras})
    summary = {}
    for arm in ARMS:
        human = [r for r in observations if r["arm"] == arm and r["true_class"] != "no_human"]
        machine = [r for r in observations if r["arm"] == arm and r["true_class"] == "no_human"]
        summary[arm] = {
            "human_n_valid": len(human),
            "human_escape_fraction": (sum(r["human_escape"] for r in human) / len(human) if human else None),
            "human_presence_miss_fraction": (sum(r["human_presence_missed"] for r in human) / len(human) if human else None),
            "human_mean_p_truth": (sum(r["p_truth"] for r in human) / len(human) if human else None),
            "human_borrow_use_fraction": (sum(r["leech_count"] > 0 for r in human) / len(human) if human else None),
            "nonhuman_n_valid": len(machine),
            "nonhuman_false_human_fraction": (sum(r["false_human"] for r in machine) / len(machine) if machine else None),
        }
    no = summary["no_borrow"]["human_escape_fraction"]
    yes = summary["borrow_permitted"]["human_escape_fraction"]
    return {
        "protocol": PROTOCOL, "committed_manifest_sha256": digest,
        "expected_trials": 32, "valid_trials": len(observations),
        "missing_trials": sum(r["status"] == "missing" for r in rows),
        "invalid_trials": sum(r["status"] == "invalid" for r in rows),
        "extra_files": extras, "trial_status": rows, "arms": summary,
        "human_escape_difference_borrow_minus_control": (yes - no if no is not None and yes is not None else None),
        "descriptive_only": True, "confirmatory_ready": False,
        "externally_verified_conductor_receipt": False,
        "external_commitment_witness_verified": False,
        "actual_human_participants_verified": False,
        "directly_comparable_to_turing_70_percent": False,
        "note": "An intact hash proves byte equality only, not prior publication. No real observations are supplied by this code.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--records-dir", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    destination = Path(args.output)
    if destination.exists():
        parser.error("Refusing to overwrite an existing private analysis output")
    report = analyze(args.plan, args.records_dir, args.expected_manifest_sha256)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write("\n")
    print(f"OPEN-COMPUTE/1: {report['valid_trials']}/32 valid; confirmatory_ready=false")


if __name__ == "__main__":
    main()
