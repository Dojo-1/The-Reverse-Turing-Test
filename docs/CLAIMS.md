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
