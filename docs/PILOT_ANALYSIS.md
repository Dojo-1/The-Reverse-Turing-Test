# R6 — Offline evidence audit and pilot analysis

**Status:** source-checked against mock-controller exports and independent known-answer fixtures. No real participants, model benchmarking, or causal research measurements have occurred.

This is the mechanism connecting the previously sealed 24-trial assignment to actual (future) controller exports. It provides **data-integrity checks and descriptive estimates**, not an automatic scientific validity certificate.

## Input contract

Prepare a private analysis directory containing:

- The **sealed private schedule**, created by [pilot_schedule.py](../experiments/pilot_schedule.py): seed, SHA-256 seed commitment, exact 24 assignments, `RTT-01` ... `RTT-24`.
- The original **published commitment** created before any trials.
- A `records/` folder of controller JSON exports named `RTT-01.json` through `RTT-24.json`. Do not edit or reconstruct missing exports.
- Optionally a `witness/` folder with observer JSONL files `RTT-01.jsonl` through `RTT-24.jsonl`. Their first-seen times belong to the observer process, not to C.

The analysis runs locally. It needs Python 3.10+, with no third-party packages.

```sh
python -m experiments.analyze_pilot \
  --private-schedule /private/rtt-pilot-private.json \
  --public-commitment /published/rtt-pilot-commitment.json \
  --records-dir /private/records \
  --witness-dir /private/witness \
  --output /private/pilot-audit.json
```

The output path must not already exist and is created with owner-only permissions on POSIX. **Unblinding:** This should run only after all conductor verdicts are locked. The output contains per-trial true condition and assigned link state; handle it as a private research artifact.

## What is checked

1. **Commitment reconstruction:** Regenerate the exact 24-trial order from the private seed, verify every row and the public hash commitment. This does not prove the controller actually followed the plan.
2. **Assignment versus exported truth:** Verify condition, human gateway and ON/ON versus OFF/OFF link factor match the assigned trial.
3. **Phase integrity:** One pilot configuration, A then B baseline Q/A, exactly one private intervention between baseline answer and public continuation marker, exactly six post-marker Q/A, one locked verdict then reveal.
4. **Pacing integrity:** Exactly 45-second configured release gate, no controller-reported deadline misses or late publication, no omitted questions, no `timeout` masquerading as a genuine answer.
5. **Score reconstruction:** Require a finite normalized vector `P(no human),P(human A),P(human B)`, recalculate the exact three-way Brier score from the assigned condition, and compare it with the controller export.
6. **Optional observer reconciliation:** Check every public event's observer SHA-256 digest and dense local sequence against the controller transcript, along with presence of a completed observer log. **No claim that this proves C's receive-time precision.**

Missing assignments, mismatches, corrupt data and extra trial IDs are not quietly ignored or filled. The report retains an explicit invalid/missing row and its error codes. A missing observer file is reported as absent coverage; an existing but corrupted observer file invalidates the corresponding row.

## Preregistered contrast

The primary descriptive quantity is exactly

[
\Delta=
\operatorname{mean}[1-P_C(\mathrm{no\ human})\mid
\mathrm{machine replacement,link\ OFF}]
-
\operatorname{mean}[1-P_C(\mathrm{no\ human})\mid
\mathrm{machine replacement,link\ ON}].
]

There are five assigned machine-only trials in each link cell. The report includes their **individual raw probabilities, mean, minimum and maximum**, plus counts for all six (origin × link) experimental groups. If a machine comparison cell has no valid observations, `delta` is null; it is never fabricated.

Even with all 24 internal records valid, the script deliberately sets **`confirmatory_ready = false`** and **`externally_verified_conductor_receipt = false`**: the R5 read-only observer is not a direct, independently attested measurement of the conductor's actual receive time. A later verified external receipt-control layer would require a distinct evidence contract and versioned analysis, not a silent Boolean patch.

## Verification and interpretation

```sh
python -m unittest discover -s tests -v
```

The known-answer tests explicitly construct **synthetic** data with an expected machine-control difference of `+0.7`, and exercise missing files, altered assignments, forged score, corrupted observer digest and a genuine Game-generated controller export. These fixtures are **not empirical results**. Do not cite their numerical values as findings about human or machine recognition.

The strongest deliverable is the **ability to detect some concrete departures from the preregistered assignment and scoring rules**. The strongest remaining obstruction is actual independently observed conductor reception timing, followed by real model and volunteer trials.

Success in this code check does not imply an absence of hidden-channel leakage, human superiority, machine non-intelligence, or a statistically reliable causal effect.
