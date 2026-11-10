# R4 — Fixed-release answering

**Status:** implemented local relay feature; deterministic and loopback HTTP tests. Not evidence of human/machine identification, and not a guarantee of end-to-end network or provider timing secrecy.

## Why this exists

Previous versions stripped public event timestamps but published an answer immediately when the respondent submitted it. The conductor could therefore use its own clock to estimate model latency or human typing speed. This is a confound if the question is *origin versus missing communication channel*.

R4 adds an **optional fixed-release mode**. It does not change the free-form game: unpaced sessions behave as before. A controlled trial can explicitly choose a gate duration.

## How to play

1. Start the local server with `python -m game.server --port 8765`.
2. On the controller screen, **before any public question**, select `Enable fixed answer boundary` and set a common release interval (e.g. **45 seconds**, range 1–600).
3. Have C ask one question at a time. A/B answer as they normally would. Early answers are stored privately in the server; the conductor sees only the outstanding question until the release boundary.
4. At the deadline, the server publishes the buffered answer. For an unanswered question, it publishes a neutral `timeout` event and records a controller-only `deadline_miss` violation. Late answers cannot replace a timeout.
5. The controller may change the participant or topology **between released turns**, but never while a paced answer is pending. This restriction prevents a mid-question swap.
6. The conductor commits a verdict only after the current release completes. Controller reveal and scoring work as in R2/R3.

**The R3 model actors are compatible**: a respondent that has submitted its answer waits until release rather than generating duplicate answers. An automated conductor encountering an explicit timeout aborts its normal verdict path; the operator must report the failed trial.

A controller who configures timing before the first question also locks the initial link configuration when the interrogation begins.

## Operational semantics

Let question acceptance time be `q_t`, common delay `Δ`, deadline `d_t=q_t+Δ`, and answer receipt time `s_t`. For an on-time submission `s_t<d_t`, the intended public sequence is:

```text
t < d_t:   ... question_t                   (answer buffered privately)
t ≥ d_t:   ... question_t, answer_t         (answer becomes public)
```

If no response arrives strictly before the deadline, an explicit timeout is released instead. The controller's audit records submission time, nominal monotonic deadline, actual release time, publication lateness, and timeout/late-publication violations. **Internal timestamps and controller audit are not shown to C.**

A lightweight background worker wakes every 50 ms (subject to OS scheduling) to service due gates independently of API polling. The browser polls locally every 250 ms. For automated C, choose `--poll-seconds 0.25` and record the parameter.

**No implementation can promise perfect real-time release on a general-purpose operating system.** The engine flags `late_publication` when the worker/first servicing observes a gate more than **1 second late**, and always flags a missing response as `deadline_miss`. The one-second bound is currently fixed for R4, not a universal rule. Errors and missed deadlines remain in the export.

Real HTTP delivery to C may still be later than the server's publication time. Controller-only audit is **not a direct measurement of the conductor's actual reception time**.

## Claims and tests

- **Lean:** `ReverseTuring/Pacing.lean` proves for a finite discrete-time *model* that two identical responses received strictly before a common deadline produce identical public transcripts at every observation time; it also distinguishes timeout cases.
- **Python engine:** `game/engine.py` enforces a bounded, single-pending-question gate and role-local information access.
- **Background scheduler:** `game/server.py` services releases independent of participant/API requests.
- **Unit and black-box loopback tests:** `tests/test_pacing.py` uses a controllable fake clock to test early vs late-in-window submissions, invisible buffering, timeout, late publication, server worker, inter-turn substitution, agent idempotence, and HTTP polling.
- **Interpretive boundary:** A green Lean job and Python tests are jointly authored development witnesses, not independent validation of human/model indistinguishability or external side-channel safety.

## Why this is NOT yet a completed preregistered pilot

The [24-trial protocol](PILOT_PREREGISTRATION.md) also requires (i) an independently controlled intervention schedule, (ii) exactly two baseline queries followed by the concealed transition and six post-transition queries, (iii) fixed model/proxy configurations, and (iv) direct end-to-end delivery compliance checks. R4 enforces a response gate, **not yet a full trial phase-barrier or an independent receipt-time witness**. The host must enforce the question boundary while a fully auditable orchestration layer is developed.

Trials with `deadline_miss` or `late_publication` are invalid for the confirmatory timing-controlled comparison, even if C can produce a verdict. Report their existence and count.

No experiments with actual human volunteers have been conducted by this implementation.
