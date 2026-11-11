"""Bounded fictional compute-resource economy for the covert-leech variant.

The *relay* performs deterministic modular exponentiation and charges
in-game compute credits to an active machine's quota. It does NOT access
another player's device, model weights, infrastructure, GPU or API account.
"""
from __future__ import annotations


MACHINE_ROLES = frozenset((
    "machine_A", "machine_B", "replacement_A", "replacement_B"
))
INITIAL_RESERVE = 12
MAX_LEECH_ATTEMPTS = 3
TURING_ACCURACY_REFERENCE = 0.70
REFERENCE_SECONDS = 300


def classify_verdict(p):
    """Unique maximum among the three declared probabilities.

    Exact ties produce 'undecided' rather than an arbitrary ordering
    advantage. This deterministic decision is separate from calibration.
    """
    classes = ("no_human", "human_A", "human_B")
    best = max(p[key] for key in classes)
    choices = [key for key in classes if p[key] == best]
    return choices[0] if len(choices) == 1 else "undecided"


def summarize_identifications(results):
    """Descriptive accuracy across completed game reports, never confidence.

    Turing's <=70% prediction concerned the interrogator's chance of right
    identification after five minutes, not a per-game confidence cutoff.
    SOURCE: Stanford Encyclopedia of Philosophy, "The Turing Test", s.1.
    This helper is not a statistical hypothesis test and ignores no failures
    silently: inputs must be completed controller-only identification rows.
    """
    if not isinstance(results, list):
        raise ValueError("Expected a list of completed identification results")
    for row in results:
        if (not isinstance(row, dict)
                or type(row.get("correct_identification")) is not bool):
            raise ValueError("Every row needs a completed categorical identification")
    n = len(results)
    correct = sum(r["correct_identification"] for r in results)
    return {
        "n": n,
        "n_correct": correct,
        "empirical_correct_fraction": correct / n if n else None,
        "turing_prediction_correct_fraction_reference": TURING_ACCURACY_REFERENCE,
        "reference_question_seconds": REFERENCE_SECONDS,
        "descriptive_only": True,
        "directly_comparable_to_turing_original_game": False,
        "comparison_limit": "reversed roles and three classes including no_human",
        "does_not_establish_turing_prediction": True,
    }


def evaluate_modexp(data):
    """Return (sanitized task, result, game-credit cost), without side effects."""
    params = {}
    for key, minimum, maximum in (
        ("base", 0, 1_000_000_000),
        ("exponent", 0, 4096),
        ("modulus", 2, 1_000_000_000),
    ):
        value = data.get(key)
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(
                key + " must be an integer between " +
                str(minimum) + " and " + str(maximum)
            )
        params[key] = value
    exp = params["exponent"]
    cost = 1 if exp < 128 else (2 if exp < 2048 else 3)
    output = pow(params["base"], exp, params["modulus"])
    return params, output, cost
