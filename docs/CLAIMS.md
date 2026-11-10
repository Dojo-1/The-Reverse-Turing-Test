# Evidence ledger — 2026-11-10

**Evidence anchor:** Lean proof check succeeded for exact commit `bf9fb024eb82b83d584788c98e158990f5e9f428` in GitHub Actions [run 42875799282](https://github.com/Dojo-1/The-Reverse-Turing-Test/actions/runs/42875799282). Earlier failures (missing Lake manifest, then Lean proof syntax) are retained in Actions history. Any later changes must be checked at their own SHA; a previous green run is not automatically a test of later edits.

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
