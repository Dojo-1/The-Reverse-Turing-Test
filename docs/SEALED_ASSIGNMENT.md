# R9 · Bind a trial before it begins

**Experimental control, not an experiment.** No human/model trials have been conducted. The open game and *unbound* eight-question rehearsal remain available.

Earlier versions of the strict pilot accepted any syntactically valid hidden intervention. The operator could accidentally select a different condition from the 24-row precommitted schedule and only discover it in an offline audit. R9 adds an **optional, server-enforced assignment binding**, and the study auditor now **rejects unbound pilot exports**.

## 1. Commit the 24-row schedule before recruiting or observing participants

Use the existing generator, and publish its public commitment (including protocol and hash) to a separately maintained, timestamped record.

```sh
python -m experiments.pilot_schedule \
  --private-output private/rtt-pilot-private.json \
  --public-output private/rtt-pilot-commitment.json
```

Protect the **private seed** and full schedule. Never send them to the machine conductor, human participants or a public repository. The public commitment alone does not cryptographically prove its publication *date*: preserve external evidence of the publication.

For actual participants, run a **fresh relay and independently initialized model sessions per trial**; never reuse prior model context across assignments.

## 2. Bind precisely one scheduled trial to the local controller

Start `python -m game.server --port 8765`. In the *controller's separate private terminal*, set **only the controller role token**.

```sh
export RTT_ROLE_TOKEN='CONTROLLER_TOKEN'
python -m experiments.bind_pilot_trial \
  --private-schedule private/rtt-pilot-private.json \
  --public-commitment private/rtt-pilot-commitment.json \
  --trial-id RTT-01
```

On Windows PowerShell, set the token with `$env:RTT_ROLE_TOKEN='CONTROLLER_TOKEN'`. Use `--dry-run` to validate files and the trial ID *without changing the relay*.

The binder validates the full deterministic 24-row allocation against the published commitment and sends the seed to the **local controller-authenticated HTTP endpoint**. The server regenerates the schedule, verifies the same hash, retains *only the selected row and its commitment*, then atomically enables the 45-second gate and genuine-machine A/B baseline. It **does not write the seed** to audit, exported JSON, participant views or console output. Treat both the private input file and the local controller endpoint as security-sensitive.

## 3. Play and audit

The controller interface displays a **controller-only** sealed trial ID, hidden condition and prescribed link state. After A and B answer the two baseline questions, the concealed intervention must **exactly match** that row: condition, fully ON/OFF link factor, and human gateway. An attempted mismatch fails **before any game state changes**.

Then publish the condition-independent continuation marker, ask the six follow-up questions, lock the conductor's three-class verdict, reveal and export. Start the [R8 conductor-receipt logger](CONDUCTOR_RECEIPT.md) before the first public event if you intend to audit actual client delivery.

Run the predeclared analysis after all participant verdicts are locked:

```sh
python -m experiments.analyze_pilot \
  --private-schedule private/rtt-pilot-private.json \
  --public-commitment private/rtt-pilot-commitment.json \
  --records-dir private/records \
  --output private/pilot-audit.json
```

R9 requires each actual-study export to contain `pilot_schedule_bound=true`, the assigned `pilot_trial_id`, exact `pilot_assignment`, and matching `pilot_seed_commitment` and controller-audit records. **An ordinary unbound rehearsal is rejected as evidence of a preregistered trial**, even if its eight questions and Brier score are otherwise valid.

## Boundaries and falsifiers

- A rejected intervention is not silently retried with a different assigned condition. The operator must follow the sealed row or preserve an incomplete/invalid trial.
- The controller is still a trusted operator. This code cannot prove the seed was externally committed before a trial, that the controller ran the claimed binary, or that all hidden errors and data were retained.
- The commit hash and trial ID are **provenance hooks**, not independent witnesses. A dishonest operator with access to the seed or server could still falsify execution.
- A bound trial still requires human consent, model/provider isolation, actual private traffic when testing communication, measured direct-C receipt timing, and independent review.
- The finite Lean proofs address projection and pacing abstractions, **not** this Python allocation binding.
- Tests use synthetic deterministic assignments; **there are zero measured human-origin effects**.

**Kill condition:** any mismatch between the prepublished commitment, actual server-bound assignment, intervention, controller export, or evidence-audit record invalidates that trial's claimed preregistration. Preserve the mismatch, do not impute a replacement.
