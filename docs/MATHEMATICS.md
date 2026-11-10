# Mathematical analysis: the connected Reverse Turing Game

**Research status:** proposed extensive-form model and classical derived bounds. The Lean modules prove (when CI-verified) narrow finite structural statements, not a general game-equilibrium theorem. We neither assume nor infer that human or machine participants are unintelligent.

## 1. An open family of games

A game instance is G=(P,Theta,mu,T,Q,A,I,E,Pi,u,D), where:

- P: conductor C, machine respondents A/B, possible human impersonator H, independent controller;
- Theta: hidden intervention and substitution round, with possible values {unchanged, human-A, human-B, machine-A, machine-B};
- mu: precommitted distribution over Theta;
- T: horizon (time, moves, or stopping rule);
- Q,A: available public questions and replies;
- I: information partitions/filtrations, including controller-held secrets;
- E_t: directed, possibly time-changing communication topology;
- Pi: behavior strategies conditioned on each player's information, possibly randomized;
- u: payoffs including classification, confidence calibration, informational costs, and rule compliance;
- D: admissible verdicts and scoring rule.

Different T, priors, information structures, costs, and stopping rules define different games. There is no universal winning percentage. Freeze each trial's parameters before revealing its outcome; new configurations are new experiments, not regraded old ones.

There are two different labels: physical provenance Origin in {human, machine}; intervention Type in {unchanged,human-A,human-B,machine-A,machine-B}. 'Machine-to-machine replacement' is a negative control for change detection. The observational three-way judge {no human, human A, human B} collapses multiple hidden states, so it cannot by itself identify the intervention type.

## 2. Information graph: computational 'telepathy' is not telepathy

For i,j in {C,A,B}, E_t(i,j)=1 means information can be communicated along an approved edge at round t. It does NOT imply successful KV transfer. A communication edge may carry textual messages, a deterministic shared-state token, or a *real* trained model-pair KV-cache translator. The former two are synthetic controls; neither implements SwaT.

For real cache transfer, a model-dependent translator Phi_ij : K_i -> K_j is needed, with layer-shape/tokenization/position constraints. Without successful independent verification of such a translator, describe an experiment only as **simulated latent communication**.

The conductor's public observation O_t need not include the internal transfer Z_t. Thus the actual classification likelihood is the *marginal* P_theta^E(o), integrating out hidden transfers under the specified strategies. C may infer a link indirectly through answers; it does not automatically observe Z.

Changing the graph and/or its availability can confound human detection. In a factorial design, independently vary origin and link availability when the experimental implementation permits it. If a human must use a machine intermediary to access a link, classify the resulting condition as a human-machine *team*, not a standalone human.

## 3. Exact finite Bayes detection bound

Let X be a finite set of publicly distinguishable observation transcripts and S={N,H_A,H_B}. With prior mu(s) and likelihood p_s(x), any deterministic classifier d:X->S has accuracy

    Acc(d) = sum_x mu(d(x)) * p_{d(x)}(x).

The pointwise optimum selects any s maximizing mu(s)*p_s(x), giving

    Acc* = sum_x max_s (mu(s)*p_s(x)).

Proof: every summand is bounded by the maximum, and a maximizer can be selected independently for each x. This theorem concerns fixed distributions, not a conductor that changes its querying policy in response to strategic adaptation.

For uniform priors and p_N=p_HA=p_HB, the optimum is 1/3. For two equally likely hypotheses, Acc*=(1+TV(P_0,P_1))/2. A binary total-variation expression cannot be substituted for the three-class expression.

The Lean `Bayes.lean` module uses **natural-number unnormalized joint masses** (likelihood times a common normalization factor) and proves the pointwise bound, its finite-table sum, and **attainment by an explicit argmax classifier**. It does not yet formalize normalized probability statements, conditional kernels, or a stochastic extension.

### Five-way intervention randomization is not uniform three-way human detection

If the controller samples uniformly from all five hidden interventions, the scoring labels collapse three physical states into `no human`: `unchanged`, `machine-A replacement`, `machine-B replacement`. Consequently,

    mu(no human) = 3/5, mu(human A) = 1/5, mu(human B) = 1/5.

For perfectly indistinguishable public transcripts under these class-conditional laws, the best **forced-choice classification accuracy is 3/5, not 1/3**. The 1/3 value requires an explicitly uniform *three-way class prior*. No universal human-detection baseline follows from the game's open rules. This distinction matters before interpreting any conductor's apparent success.

## 4. Two different information monotonicity statements

**Observed refinement:** If conductor observes Y and the poorer observation X=f(Y), an ideal unconstrained classifier with Y can emulate any X-based classifier. For the same fixed joint distribution, its optimal Bayes accuracy cannot decrease. This does not imply longer interactions help a real, resource-limited conductor, or that strategic respondents remain stationary.

**Private-channel effect:** Let Z be a hidden A->B transfer and X the public transcript. If the presence of Z changes the publicly observable law P_theta^E(X), classification value may change even though C never directly reads Z. If it leaves every public likelihood unchanged, the optimal public-only classifier value remains exactly unchanged. Conditional information I(Theta;Z|X) refers to an observer *given Z*; it is not by itself the conductor's evidence if Z remains private.

## 5. Confounding theorem and controls

Let Origin∈{human,machine} and Connectivity∈{on,off}. A detector using *only* Connectivity cannot perfectly recover Origin on the full Cartesian product of these factors: the conditions (human,off) and (machine,off) share its observation while having different origins. `Topology.connection_only_not_perfect` formalizes this counterexample.

The realistic point is causal: if removing the human also removes a side channel, then channel availability is a proxy for origin. A machine with the same channel removed is the critical negative control. A human given a permitted gateway is a separate team condition.

## 6. Strategic game and equilibria

Let C choose queries based on public history; H chooses an adaptive imitation policy; the machine responses follow declared policies; Nature/controller determine hidden intervention. A general-sum extensive-form game with imperfect information results.

Calling an overlapping-response configuration a 'pooling equilibrium' requires best-response inequalities under explicit payoffs and information sets. Identical observable laws alone do NOT imply equilibrium.

An approximate zero-sum subgame (fixed machine policy, fixed prior, H minimizes correct classification, C maximizes) has a value only after strategies and payoffs are defined. In a finite normal-form reduction, mixed strategies satisfy the minimax theorem. The exact value is experiment-specific. We do not claim existence of a particular equilibrium in the unbounded open game family.

## 7. Self-reference as a strategy, not a theorem of human superiority

Humans may use Gödel incompleteness, Tarski undefinability, Curry's paradox, Löb's theorem, or Kleene's fixed-point theorem as *interrogation/impersonation moves*. Their premises must be stated. A classical naive self-referential truth scheme can trivialize a system; that does not make Lean inconsistent or give humans general algorithmic superiority.

Whether a participant can identify proof obligations, admit uncertainty, or correctly refute a false self-attestation is a measurable skill distinct from human/machine origin.

## 8. Questions and falsifiers

H1 (experimental): machine-only link loss is often misidentified as human substitution. Falsifier: controlled link-ablation trials are not systematically misclassified relative to matched unchanged controls.

H2 (experimental): latent link affects public response distributions enough for conductor to detect link presence. Falsifier: under a sufficiently powered matched design, no equivalence-bound-exceeding difference in the pre-registered observable is found. A nonsignificant test alone is not proof of equivalence.

H3 (strategic): over repeated rounds, a human can imitate machine responses well enough that the conductor's accuracy approaches the prior-optimal baseline in at least some permitted setups. Falsifier: robustly higher detection under held-out participants/models/protocols.

H4 (interpretive): better epistemic calibration is not interchangeable with better origin classification. Test both independently; do not infer intelligence from either.

## 9. Serialized noninterference: stronger than labels, narrower than full blinding

The new Lean module [Noninterference.lean](../ReverseTuring/Noninterference.lean) defines an abstract snapshot with public event payload, internal event metadata, hidden physical origin, controller/private state, verdict, and reveal flag. Its kernel-checked conditional theorem states that **unrevealed snapshots with equal ordered public payloads and equal verdicts have identical conductor projections**, irrespective of hidden state and private metadata. Stored timestamps and internal sequence indices are intentionally omitted.

The corresponding Python implementation **must** separately project public and private message schemas; private handoffs have from/to fields rather than public channel/speaker fields. A five-condition metamorphic test checks the Python conductor output on matched transcripts under different interventions and link states. See [PROOF_IMPLEMENTATION_BRIDGE.md](PROOF_IMPLEMENTATION_BRIDGE.md).

This is **not** verified Python/Lean translation, stochastic observational equivalence under varying strategies, or physical timing confidentiality. In a live relay, a conductor can still observe *when* a message arrives, even if no timestamp is serialized. The planned matched pilot makes delivery pacing an explicit prerequisite.

## 10. Formalization roadmap

- **R0**: deterministic histories, channel labels, observation collisions (existing core).
- **R1**: information graph and link/origin confounding; finite integer weighted classifier bound (added).
- **R2**: exact finite probability kernels on a finite type and equality of induced transcript laws under adaptive queries.
- **R3**: normalized multi-class Bayes equation (finite weighted attainment already in R1), Blackwell garbling, data processing.
- **R4**: fully specified utilities, best response, pooling/separating conditions and equilibrium existence for a *finite specified game*.
- **R5**: connect operational evaluation traces to the formal model; register validity and independence gaps.

Do not promote R1 to full Bayesian game semantics or claim that a simulation validates KV transfer.
