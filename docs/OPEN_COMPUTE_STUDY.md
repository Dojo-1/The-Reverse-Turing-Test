# R14 · RTT-OPEN-COMPUTE/1: human impersonation with optional covert borrowing

**Status:** pre-observation protocol and offline integrity analysis. **No human or model behavioral observations** are included. This study is distinct from, and must never be pooled with, `RTT-PILOT/1` (the sealed private-link experiment). No original game objective, score, or R13 covert mechanic is changed.

## Fixed game

The hidden **human H** tries to pass as one of two machine respondents. **Conductor C** interrogates A/B and identifies `no_human`, `human_A`, or `human_B`. The controller knows the actual intervention but must not disclose it before C locks its verdict. Humans may use the *already implemented R13* covert `leech_compute` action if the assignment permits it; at most three virtual modular-exponentiation requests charge the **other active machine's game credits**, never C. This accesses no hardware or inference quota. Machines retain their own compute credits. The donor may notice its own changed balance and respond publicly; that potential behavioral cue is part of the phenomenon under test.

**C's accuracy, not its self-declared >70% confidence, is the identification outcome.** Turing's historical forecast of a 70% upper bound on average interrogator correct identification after five minutes, with approximately `10^9` storage, is described by the [Stanford Encyclopedia of Philosophy, *The Turing Test*](https://plato.stanford.edu/entries/turing-test/), §§1, 3.2. The reversed incentives and three-class `no_human` control here make our result **not directly comparable** to the historical prediction. A five-minute reference is retained but is not a hard cutoff.

## Experiment arms (not new game objectives)

Every open-game trial enables `configure_covert_leech` **before the first question** and sets `configure_pacing` to **30 seconds**. This keeps the exposed virtual-resource interface matched across conditions, avoiding a confound in which the feature is present in only one arm.

| Arm | Human instruction | Machine respondents |
| --- | --- | --- |
| `no_borrow` | Do not call `leech_compute` | Existing self-compute facility unchanged |
| `borrow_permitted` | May use zero to three covert operations, strategically and at own risk | Existing self-compute facility unchanged |

The intervention is still concealed. C is told the **trial-family class prior** but not the arm, trial number, identity, resource records or assignment. C chooses all public questions adaptively. A and B begin as genuine machines, and after a genuine A-then-B question/answer baseline the controller privately applies the assigned intervention. The subsequent six questions are chosen by C. Unlike `RTT-PILOT/1`, there is **no public continuation marker**. Preserve the interval between baseline and continuation across trials; operator schedule, client timing and independent receipt observations must be recorded separately. The relay's 30-second gate alone does not prove actual C reception timing.

Configure identical model checkpoints, tools, prompt budgets, model-call limits, human instruction sheets, link topology and participant handoff procedure across both arms; do not give C the instruction sheet for a particular arm. For feasibility, keep private A/B links **OFF** for all R14 trials, so `leech_compute` is the explicitly manipulated machine-assistance mechanism. These are **game-credit calculations**, not a claim of equal real compute. C's task remains the original identification game, not provenance auditing or donor-credit detection.

## Frozen 32-session feasibility allocation

The plan contains 32 independently assigned sessions, numbered `RTO-01` through `RTO-32` after a secret seeded shuffle:

| Actual hidden intervention | No borrowing | Borrowing permitted |
| --- | ---: | ---: |
| `humanA` | 4 | 4 |
| `humanB` | 4 | 4 |
| `machineA` | 2 | 2 |
| `machineB` | 2 | 2 |
| `unchanged` | 4 | 4 |
| **Total** | **16** | **16** |

The class prior given to C is `P(no human)=1/2`, `P(human in A)=1/4`, `P(human in B)=1/4`. The `borrow_permitted` factor has no human borrower in machine-only and unchanged controls; those controls check false-human judgments under the same software setup, rather than manufacturing a fake human borrower. All control arms remain playable regardless of human intervention.

Each trial is a fresh server process with independent role tokens, fresh machine/model sessions and no retained private data. Use **one agreed, preregistered conductor/model configuration** for all assigned trials, rather than selecting configurations post hoc. Stop after exactly 32 assigned rows; preserve aborts, timeouts, uncompleted sessions and model failures in their original slots, never replace failed attempts or quietly extend the sample. Pilot data from `RTT-PILOT/1` are excluded from this analysis.

### Independent commitment before the first real run

From the repository root:

```sh
python -m experiments.open_compute_plan \
  --private-output private/rto-plan.json \
  --public-output private/rto-commitment.json
```

Send the *public commitment* to an independent reviewer or timestamped record **before** seeing outcomes. It contains the SHA-256 hash of the private, seed-bearing JSON; do not disclose the private seed or the scheduled order until the last verdict is locked. Freeze this document, source commit, exact model versions, allocations, external timing witness, and instructions alongside the commitment. **Generating a SHA alone does not prove prior publication or operator compliance.** Files are created without overwrite and with owner-only POSIX mode requests; Windows ACLs need separate verification.

For each trial, export the **controller-only** JSON exactly once to `private/records/RTO-XX.json`, matching the assigned row. Keep human consent records and model/API secrets separately and privately; never publish raw transcripts or role tokens. Give C only public role-scoped views. Obtain participant consent and ethical review appropriate to the study before recruitment. No real participants are included in this PR.

## Locked outcomes and integrity audit

**Primary descriptive intention-to-treat (ITT) estimand among actual human substitutions:**

`human escape fraction (borrow_permitted) − human escape fraction (no_borrow)`, where `escape=1` if C's unique highest-probability class is not the human's actual location. Tied highest probabilities count as `undecided` and hence not a correct identification. The arm is defined by **permission**, not observed uptake; do not post-select by leech use for the primary contrast.

Secondary: missed human presence (`no_human` predicted in a human trial), human true-class probability, borrowing-uptake fraction, no-human control false-positive frequency, over-five-minute fraction, actual timed releases, and independently assessed donor public-reaction cues. Donor-cue coding requires a separate blinded rubric with independent human raters; the provided analyzer does **not** invent such judgments.

Run **after** all verdicts are locked:

```sh
python -m experiments.analyze_open_compute \
  --plan private/rto-plan.json \
  --records-dir private/records \
  --expected-manifest-sha256 SHA256_FROM_PREPUBLISHED_COMMITMENT \
  --output private/rto-audit.json
```

The offline script verifies the private seed-derived assignment, commitment byte-for-byte, 32 expected rows, open-game schema, covert setup, no strict-pilot contamination, baseline/intervention order, eight completed answers, the locked verdict, reveal, leaked-action count and 30-second configured pacing without internal timing violations. It recomputes class predictions and human identification outcomes from the probability vector. All missing/invalid rows remain explicit, including extra unexpected JSON files. An internally valid record is **not** an externally witnessed participant or timing measurement.

**Stopping interpretation:** Any disclosed hidden assignment, unmasked controller metadata, role/session contamination, absent C-reception witness, unverified model settings, or protocol deviation suspends *confirmatory* interpretation. Every record stays in the intention-to-treat accounting. With only four human observations per arm/location, report counts, individual outcomes, descriptive differences and missingness: no significance claim, power claim, or historical-Turing pass/fail decision is warranted.

## Evidence boundary

- `PROVED` (conditional finite mathematics): an identical public transcript law would make binary origin classification unidentifiable at equal prior; this is **not** a demonstrated behavior of our humans.
- `ARTIFACT-TESTABLE`: schedule integrity, deterministic scoring and some permission/visibility invariants. Synthetic tests do not count as participants.
- `MEASURED`: **none** for human recognition or actual borrowed-compute effectiveness.
- `OPEN`: actual human use, real model controls, donor response behavior, independent C-side timing/identity attestation, sample size for powered inference, and eventual external replication.

**Next smallest independent action:** appoint an external witness for the publicly committed schedule and C-side timing/identity validation, then perform a small consented rehearsal marked *non-study*. Do not upgrade rehearsal artifacts into the 32 scheduled observations.
