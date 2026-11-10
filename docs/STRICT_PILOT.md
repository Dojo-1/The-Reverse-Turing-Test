# RTT-PILOT/1: Enforced experiment phases (R5)

**Status:** implemented local protocol controls, mock/loopback-tested, **no human trials**. This is an *optional* structured protocol. The original open-ended Reverse Turing Game remains available unchanged when the controller does not enable strict pilot.

## The phase boundary

The strict pilot requires an explicit controller action **before the first question**. Selecting `Enable strict pilot` atomically configures:

- **45-second fixed release gate** for each response (not a claim of perfect network timing).
- **Bidirectional text links ON** for the genuine machine-only baseline.
- **Exactly two baseline questions:** A first, B second, with released genuine-machine answers.
- **One private, controller-authorized intervention:** humanA, humanB, machineA, machineB, or unchanged. The controller follows the previously committed 24-trial schedule; the in-app five-way random draw is unavailable in strict pilot.
- **Private link factor** after intervention: both directions ON or both OFF, not mixed. Human gateway access is enabled only for human replacement with links ON, forming a *human-with-tool* condition.
- **One explicit public continuation marker** after the hidden intervention, identical across all conditions.
- **Exactly six continuation questions** chosen adaptively by C, one at a time with 45-second release gates.
- **A locked three-way verdict** only after all eight questions are resolved, followed by controller reveal/export.

The controller's hidden intervention is not published when committed. The later public continuation event says only that the baseline is over; it does **not** say whether a human, machine, or no one replaced a participant.

For mathematical precision, the public marker is part of this pilot implementation. It is an *observable protocol event*, not a side-channel deduction. Its timing should be held consistent across trial conditions when interpreting response-time effects.

## Running one assigned trial

1. Generate and privately retain the [balanced 24-trial allocation](PILOT_PREREGISTRATION.md). Commit the seed hash and protocol to an independent recipient **before any participants are run**. Run each trial in a **fresh server process**, creating new role credentials and resetting all model sessions.
2. Start the relay: `python -m game.server --port 8765`.
3. Privately share the **observer** role token with a separate, read-only observer process, and launch it **before the first question** (see [OBSERVER.md](OBSERVER.md)).
4. On the controller page, choose **Enable strict pilot**. The server sets the fixed 45-second gate and the initial ON/ON private links.
5. Start machine conductor C and genuine machines A and B. C asks A, receives its answer at the release gate; C then asks B, receives that answer at the next release gate.
6. C automatically pauses at a public fixed boundary. Consult the private allocation for that trial and choose the assigned intervention. The controller can choose both private links ON or both OFF; for an ON human condition the human gateway is set automatically in the browser.
7. Click **Publish continuation marker**, a public protocol event that is the same regardless of the hidden condition. C can then ask six continuation questions.
8. C locks its three-class probabilities and supporting evidence; the controller reveals the truth and exports the trial record. The controller **must** retain the anonymous trial identifier, observer file, assigned schedule row, model/configuration hashes, all errors and missingness.

Do not replace a failed assignment with a new draw. Do not treat a run as valid if the host bypassed the allocation, question count, or phase boundary.

## Aborts and validity

The controller can **Abort and preserve record** when a trial becomes invalid or incomplete; the experiment logs the reason and freezes further player actions. The controller can still export the incomplete record. Do not fabricate a completed verdict or reveal in that case.

The engine's `pilot_valid_for_primary` flag is a **necessary internal-protocol check**: exactly eight genuine answers, an intervention and resume, a locked verdict, no clock violations and no aborted run. It is **not sufficient** for external validity. A green internal flag cannot certify actual conductor reception timing, model isolation, human participant identity, or adherence to the precommitted 24-trial schedule.

When there is a timeout, record a dedicated `timeout` event. An automated conductor stops its normal inference path instead of treating the timeout as a human answer. The controller records an explicit `deadline_miss`, and >1-second server publication latency is recorded as `late_publication`.

## Observation and epistemic boundaries

The read-only observer sees only public events and records first-visible HTTP polling intervals. It cannot read hidden conditions or controller timing metadata, cannot alter the game, and cannot independently certify C's exact receipt time. Even when co-located with C, different polling and OS scheduling can introduce unmeasured discrepancies.

The Lean code proves abstract finite projection and release-gate properties, not the correctness of the Python state machine or full timing blindness. Python tests exercise all five hidden conditions and a complete eight-question HTTP trial; they are implementation tests by the same development programme, not an independent human study.

**Pre-run protocol amendment:** this R5 version makes the phase transition explicit and publicly signaled; no empirical trials predate the amendment. When publishing a commitment, include this document's exact Git commit SHA, the [preregistration](PILOT_PREREGISTRATION.md) and the pilot schedule generator's version. Any later changes to public signals, timing, budget, controls or inference rules require a new protocol identifier.

## What is still missing

- An independent synchronization and direct receipt-time witness for the actual conductor process.
- Automated, externally verifiable binding of each trial to its assigned schedule row.
- Participant consent/recruitment, real model configuration preregistration and genuine human trials.
- Statistical estimates of the missing-link false-positive effect.

R5 is a better **experimental instrument**, not a new empirical result.
