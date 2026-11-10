# Evidence ledger — 2026-11-10

**Merged baseline evidence anchor:** The R2 squash commit [`abf55231a10e3e72aacc88394162f8749f90a86d`](https://github.com/Dojo-1/The-Reverse-Turing-Test/commit/abf55231a10e3e72aacc88394162f8749f90a86d) on `main` passed both `lean` and `relay` jobs in [Actions run 42883746679](https://github.com/Dojo-1/The-Reverse-Turing-Test/actions/runs/42883746679). The original R1 proof-development commit `bf9fb024eb82b83d584788c98e158990f5e9f428` passed [run 42875799282](https://github.com/Dojo-1/The-Reverse-Turing-Test/actions/runs/42875799282) but is **not an ancestor of the squashed `main` commit**; it remains historical evidence, not the merged-history anchor. The R3 new proof and Python bridge tests have separate checks; always verify their *exact head SHA* before promoting them.

| Claim | Kind | Status | Exact scope / caveat |
| --- | --- | --- | --- |
| Flip channels twice restores latent-state, transcript and information-edge coordinates | Lean theorem | **PROVED at anchor** | Structural involution, not behavioral equivariance of arbitrary policies |
| Identical deterministic reply policies produce equal histories under any fixed adaptive deterministic conductor | Lean theorem | **PROVED at anchor** | Finite horizon, same conductor policy and exact extensional equality at every history |
| Distinct hidden origins sharing one observation cannot be perfectly classified by a deterministic observation-only judge | Lean theorem | **PROVED at anchor** | No claim that real humans always match model transcripts |
| Connectivity-only detector cannot identify origin over independent {human,machine}×{on,off} conditions | Lean theorem | **PROVED at anchor** | Structural countermodel; empirical confounding requires measured interventions |
| Any three-way classifier score on a finite table of natural-number joint masses is bounded by sum of row maxima | Lean theorem | **PROVED at anchor** | Unnormalized integer weights; row contents may represent observations |
| Explicit `bestHypothesis` attains that weighted upper bound | Lean theorem | **PROVED at anchor** | Finite three-way table; no normalization, stochastic process or strategic equilibrium yet |
| Bayesian value formula with normalized probability masses | Classical mathematical derivation | **DERIVED; not directly Lean-formalized** | Sum of per-observation maximum weighted likelihood; fixed finite distributions |
| Information available via real cross-family KV transfer changes origin detection | Empirical hypothesis | **NOT TESTED** | Requires working adapter, versioned models, matched control |
| Human can impersonate a particular machine under open-duration adversarial interrogation | Empirical hypothesis | **NOT TESTED** | Requires blinded human and machine trials |
| A conductor can establish non-intelligence from a conversational transcript | Philosophical/empirical assertion | **NOT ESTABLISHED** | Needs independent definition and additional grounds |
| A pooling, separating or Nash equilibrium exists for the entire open game family | Game-theoretic assertion | **NOT ESTABLISHED** | Only finite fully specified games support standard existence/minimax claims |
| SwaT demonstrates prefill-free cross-family KV transfer under reported benchmark conditions | Paper's experimental claim | **SOURCE-REPORTED** | arXiv:2610.15095; not independently replicated here |

**What a green Lean job does and does not certify.** It checks elaboration and proof terms of the submitted propositions in the configured Lean environment. It does not check that the game implementation matches human behavior, that a side channel functions, that a statistical experiment has been conducted, that a theory of intelligence is correct, or that the research is novel.

**Next independent discriminator:** Run paired blinded trials with absent-link genuine machines, human substitutions, and unchanged machine controls. Keep the probabilities and the epistemic explanations as separate observations.


## R2 — Local relay (separate from Lean and from empirical research)

- **Implemented:** a loopback Python HTTP server, role-scoped random bearer tokens, machine conductor and isolated respondent views, one hidden intervention, machine-only controls, directed private *text* messages, locked three-class verdict, Brier score at reveal, and controller JSON export. See [LIVE_GAME.md](LIVE_GAME.md).
- **Tested by GitHub Actions:** Python `unittest` tests cover rule transitions, HTTP authentication, role privacy, human-with-gateway controls, early-verdict non-oracle behavior, machine substitutions, probability validation, randomized intervention, and one full HTTP trial. Node syntax checks the browser script. These are **implementation tests**, not human-participant outcomes.
- **Explicit limits:** The software does not verify the biological identity of a purported human, automatically converse with an LLM, securely operate across the internet, preserve data after process exit without manual export, or transfer model KV states.
- **Intervention randomization:** optional `secrets.choice` uniform draw from five states is controller-visible and conductor-hidden. It has no reproducible seed or external randomization attestation. This is a convenience for pilots, not a scientifically conclusive allocation mechanism.
- **Experimental status:** zero human-versus-machine trials conducted by this development branch. Conductor intelligence, model-to-model shared states, and statistical human detection remain **NOT TESTED**.

Evidence anchor: verify actual R2 PR head and [Actions runs](https://github.com/Dojo-1/The-Reverse-Turing-Test/actions) at review; do not conflate a passing Lean build with runtime security or an independent empirical replication.


## R3 — Optional model participants (separate from empirical inference)

- **ARTIFACT:** [game/agents.py](../game/agents.py) provides a stateless, role-scoped conductor/response driver, explicit Chat Completions model transport, a clearly labelled scripted smoke policy, and limits on question count, context events, output length, request sizes and timeouts.
- **TESTED with local mocks:** [tests/test_agents.py](../tests/test_agents.py) checks that the conductor's model prompt receives only public projected events, respondent prompts receive only their own public events and explicitly permitted private handoffs, and the human role cannot be automated by the supplied CLI. A mock Chat Completions server exercises response parsing, redirect refusal and separation of provider API credentials from the relay credential.
- **TESTED as an implementation:** loopback relay and scripted-model end-to-end tests, including manual human substitution and a locked verdict. GitHub Actions [run 42884221972](https://github.com/Dojo-1/The-Reverse-Turing-Test/actions/runs/42884221972) passed both Lean and Python/JS jobs with 31 Python tests on commit `9c8d8f57afbd36bc7fb9cd8803d3d8a469b79626`. Revalidate later heads independently.
- **NOT TESTED:** responses from a real local or remote LLM served over the adapter; measured impersonation success; actual human game sessions; accurate recognition of intelligence; cross-model KV-cache communication; model/provider independence; hostile operator security; statistical generalization.
- **Limit:** The adapter guarantees only the fields *it sends* to the provider under these tested software paths. It cannot guarantee the external backend's state separation, retention policy, behavior, or lack of side channels. A mock provider is not independent validation of a real provider.


## Reviewer audit — timestamp and formalization repair

- **Confirmed and repaired in R3 branch:** the old `Game._project` emitted raw `timestamp` fields even though it reindexed global event IDs. This exposed stored answer times. Public and respondent-visible private events now use separate whitelist projections: public `{sequence,kind,channel,speaker,body}` and private `{sequence,kind,from_channel,to_channel,body}`. The controller retains raw timing data for audit. **Live arrival latency is still observable and is NOT normalized by this change.**
- **New formal statement:** `ReverseTuring/Noninterference.lean` formalizes a pre-reveal projection theorem for a snapshot with the same public payloads and the same verdict. It proves that changing hidden identity, controller/private state, internal sequence, or timestamps cannot change the **modeled serialization**. It does not prove Python implements the Lean definition.
- **Implementation bridge:** a black-box, five-condition metamorphic regression checks equality of actual Python conductor views under equal public messages and different hidden conditions, link configurations and private history. It also checks future metadata cannot leak through the projection. Source-authored tests are not independent external validation.
- **Rejected reviewer claim:** `game/web/style.css` is not empty on merged `main` (4,444 characters in the GitHub connector's decoded source). No styling repair is warranted for that claim; browser rendering across devices remains unmeasured.
- **Badge:** `main` still used an outdated branch badge; the R3 README corrects it to `branch=main`. In GitHub, the badge is decorative CI metadata, not evidence of the exact research theorem.
- **Prior:** a uniformly drawn five-way intervention induces scored three-way prior `(3/5,1/5,1/5)`; neither universal prior nor a calibrated model output is implied.
- **Empirical:** no real human impersonation or LLM benchmark trials have been completed. A separate preregistration documents a *proposed* matched pilot, not measured results.


## R4 — Fixed-release timing control (optional, no human trials)

- **Formal P:** [`ReverseTuring/Pacing.lean`](../ReverseTuring/Pacing.lean) proves a finite, discrete-time **conditional** observation result: identical answers received before a common deadline have identical abstract public transcripts, for all observation times. The theorem does not concern response *content*, external channels, OS scheduling or model-provider state.
- **Artifact/tested A:** [`game/engine.py`](../game/engine.py) can buffer a respondent's reply; C cannot see it until the clock boundary. [`game/server.py`](../game/server.py) starts a best-effort background worker to service releases independently of API polling. A response absent at the deadline generates an explicit `timeout`, not a fabricated answer.
- **Tested A:** [`tests/test_pacing.py`](../tests/test_pacing.py) covers early vs late-in-window submissions, identical projected transcripts, pending error invariance, no duplicate model submissions, timer worker without polling, HTTP role separation, missed answers, late publication audit, and compatibility with unpaced play. These tests use a controllable fake clock; they do not measure real-world scheduling jitter.
- **Instrumented A:** The controller receives `deadline_miss` and `late_publication` violations, the nominal monotonic deadline and observed server publication delay. A publication more than one second late is flagged. C receives none of this metadata. This is **not** proof that C received the answer within ±1 second.
- **Not measured M=absent:** No volunteer human/game sessions, no real external model trial, no latency-distribution measurements, no independent receipt-time capture and no pilot-effect estimate.
- **Research stop condition:** A confirmatory claim fails if any measured unaccounted timing channel, missed deadline, unbalanced intervention, unexplained event, or unrecorded trial exclusion compromises a matched control. Preserve the failed run; do not silently reclassify it.
- **Research next:** Complete an explicitly controlled two-baseline/six-continuation phase barrier and independently observe C's actual receipt time before running the 24-trial protocol.

## R5 — Enforced pilot phases and limited observation witness (not a study)

- **Artifact A:** `Game.configure_pilot` atomically sets the preregistered 45-second response gate and baseline private links ON/ON. The public protocol fixes one baseline question each to A and B, an explicit private intervention, a condition-independent public resume marker, and exactly six continuation questions. It rejects wrong baseline channel, a premature/ninth question, an uncommitted transition, mixed link states, an incompatible human gateway and a premature verdict.
- **Test A:** `tests/test_pilot_phase.py` compares the conductor view across all five hidden interventions and confirms identical views on equal visible transcripts before public resume. `tests/test_pilot_http.py` executes a complete eight-turn trial through the loopback HTTP server. These are self-authored implementation tests.
- **Artifact A:** A new `observer` role is strictly read-only and sees only projected public events. `game/observer.py` polls from a separate process and records private JSONL first-seen monotonic intervals and message digests without participant credentials or raw text; it refuses to start after the first public event. See `tests/test_observer.py`.
- **NOT measured:** Actual conductor receive-time precision, independent scheduling tolerance across machines, proof of provider state isolation, fidelity to a committed 24-trial assignment, any human/LLM game outcomes, or causal effect of hidden channels on classification.
- **Visible limitation:** a first-seen event at an observer is not the same observation event as the conductor's first receipt. Co-located monotonic clocks improve comparability but do not prove equality; instrument C directly before promotion to controlled-data conclusions.
- **Failure provenance:** first R5 branch tests failed due to a backwards-incompatible export-schema version; the schema was made versioned by protocol (v0 for open game, v1 for strict pilot). The first R5 UI edit also failed Node syntax due to an omitted comma and was corrected. Preserve those failed Actions checks rather than reporting only the later passing head.
- **Smallest external test:** one scripted, matched eight-question trial with all five hidden states and a separate first-seen observer, followed by a genuinely independent C-side reception logger; stop if a state-correlated timing discrepancy survives controlled pacing. This is a protocol test, not a human ability measurement.

## R6 — Source-preserving pilot audit (no experimental numbers)

- **A/implemented:** `experiments/analyze_pilot.py` reproduces the sealed private schedule from its seed, checks the published commitment, verifies every assigned trial against controller-exported origin, link, gateway, phase ordering, timing flags, audit events and verdict, and recomputes the three-way Brier score.
- **A/tested:** `tests/test_pilot_analysis.py` uses hand-constructed **synthetic** known-answer events to check an analytic reference value (+0.7), data omissions, assignment swaps, corrupted phase markers, forged Brier scores, observer hash mismatch, and compatibility with a Game-generated exported trial. The synthetic reference value is **not a study result**.
- **Descriptive formula:** compute mean `1 - P_C(no_human)` for *machine replacements with link OFF* minus the same mean with link ON, exactly as specified in the pilot preregistration. The report exposes raw per-cell probabilities and missingness, not just a favorable scalar.
- **M/not yet present:** There are no real human/model trial records. The analyzer does not assert cause from observed association and deliberately reports `confirmatory_ready=false`; a read-only observer's first-seen times are not independently verified conductor receipt times.
- **Audit stop:** Do not publish an effect estimate as an empirical finding if trial identities are unverified, the schedule differs, any missingness is concealed, or a participant's privacy/data-retention consent has not been established. Incomplete records remain visible with explicit error codes.
