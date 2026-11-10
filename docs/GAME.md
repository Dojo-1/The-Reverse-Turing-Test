# R0–R1: Dynamic Bayesian reverse-imitation game

**Status:** proposed mathematical model, not a measured experiment. Date: 2026-11-10.

## Players and Nature

Nature samples a hidden intervention from S = {unchanged, humanA, humanB, machineA, machineB}, a substitution time k, and any private respondent types. The conductor C does not observe the type/time. The independent controller sees them. C sends questions adapted to prior observations. Two respondents answer. The human maximizes misclassification as machine. Machines defend their origin statements under a no-fabrication constraint. C minimizes detection error and may incur inquiry costs.

## Formal arena

For finite horizon T, histories are h_t = ((q_0,a_0),...,(q_(t-1),a_(t-1))). A strategy of C maps its information history to distributions over queries; a respondent strategy maps its available information and current query to distributions over answers. A behavioral strategy may depend on private information. The controller performs hidden interventions. Equilibria require a specified utility function, timing, information sets, strategy spaces, and priors; none is implied by the bare rules.

The hidden state must not be collapsed to a binary label when machine-machine substitutions are included. Separately distinguish *change detection*, *human detection*, and *localization*.

## Established mathematical benchmarks (finite weighted argmax core now Lean-checked; probability semantics remain external)

For finite observation X, hidden class S, class prior μ, conditional observation law P_s(x), and a zero-one-loss classifier g:X→S, its accuracy is Σ_x μ(g(x)) P_(g(x))(x). The optimal deterministic classification accuracy is

    V* = Σ_x max_s [μ(s) P_s(x)].

Under three equally likely classes {unchanged, humanA, humanB} having identical observation laws, V*=1/3. Under two equally likely classes, V*=(1+TV(P_0,P_1))/2. These are classical finite Bayes decision results, not new theorems. A three-class expression must NOT be replaced indiscriminately by the binary total-variation formula.

### Copying obstruction

If an impersonator can duplicate the genuine machine's *full conditional response distribution at every possible public history*, then for any fixed adaptive conductor policy both induce the same observation law over finite transcripts (by induction on time). That is a strong conditional assumption, not a demonstrated real human capability.

### More information cannot hurt an optimal unconstrained classifier

If an observation X is a deterministic postprocessing of Y, any X-based classifier can be implemented as a Y-based classifier. Hence the optimal Bayes zero-one accuracy under Y is at least that under X, when priors and evaluation distribution are identical. This does not mean a particular resource-bounded conductor improves with longer transcripts, especially when strategies or data distribution change.

## Game-theoretic phenomena to test, not claim as established

- Pooling: human and machine response policies induce equivalent public observations.
- Separating: some costly or constrained signal distinguishes types under specified incentive conditions.
- Semi-separating: mixed strategies produce overlapping but different signal laws.
- Strategic experimentation: C chooses queries for information gain or expected loss reduction, accounting for information leakage and costs.
- Change-point detection: time of replacement is hidden; a change of machine may masquerade as a human.
- Mechanism design: choose intervention priors, scoring, and evidence constraints to avoid reward hacking.

A pooling equilibrium is **not** automatic. It requires best-response incentives for *all* players. Behavioral indistinguishability is not the same as strategic equilibrium.

## Important epistemic boundary

Human/machine denotes provenance of the respondent in this experiment. Intelligence is a separately defined property not inferred from origin or from conversational imitation. A Lean theorem about indistinguishable transcripts does not prove that actual models lack intelligence or humans can flawlessly impersonate a model.

## Proposed preregistered pilot

- 12 human substitutions balanced between A/B; 6 machine substitutions; 6 unchanged controls.
- Independent controller, committed hidden randomization, a stopping rule fixed *for that trial* (not universal), blinded conductor, no metadata/timing leaks.
- Primary: probability assigned to correct three-way human-location hypothesis; report calibration and false positives.
- Secondary: change-point localization, machine-substitution confusions, longitudinal behavior, claimed self-attestation evidence.
- Preserve all seeds, prompts, models, controller decisions, and failures.
- This sample is exploratory, not powered to establish universal statements.

## Formalization boundary

Lean R0 proves finite *deterministic* structural facts (label involution; observation collision; response-policy equality implies trace equality). Extension R1 must implement finite probability masses, likelihoods, Bayes optimal classification, and explicit assumptions. Extension R2: randomized adaptive policies and conditional distribution equality. Extension R3: equilibrium only after exact utilities/information sets are defined.

## Connected R1 extension

The additional directed information graph, side-channel controls, formal connectivity/origin confounding theorem and finite weighted three-way Bayes optimum are in [MATHEMATICS.md](MATHEMATICS.md). For actual play use [HOST_AND_PLAY.md](HOST_AND_PLAY.md), [MACHINE_PLAYERS.md](MACHINE_PLAYERS.md), and [HUMAN_PLAYER.md](HUMAN_PLAYER.md).
