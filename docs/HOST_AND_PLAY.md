# Facilitator: run a Reverse Turing Game today

**NEW (R2):** An executable local browser relay is available: [start here](LIVE_GAME.md) with `python -m game.server --port 8765`. The instructions below also work as a fully manual alternative. Neither mode provides actual KV-cache transfer or automatic model API orchestration.

This is a **manual, text-interface protocol**. No live KV translator or autonomous orchestration exists in this repository. The facilitator must implement the information isolation. An honest simulated shared-state channel can be used for a topology-control experiment, but must be identified as simulation.

## Personnel and equipment

- Independent controller/operator who can privately randomize and retain the true state.
- Machine C as conductor; machine A and B as respondents in isolated model sessions.
- One willing human impersonator H who can enter the selected channel *after substitution*.
- A relay that forwards only approved messages. Do not paste secret controller instructions into C's context.
- Optional separate link proxy implementing message sharing or a verified KV adapter. A shared text scratchpad is not a KV-cache transfer.

## Set parameters for *this* encounter

Before the outcome is seen, record: date; participants; model providers and versions; public rules; distribution over {unchanged,human A,human B,machine A,machine B}; possible swap times; length/stopping policy; allowed tools, public/latent links, internet access; judge format; scoring rule; control conditions; random seed committed or held by a separate evaluator. These are trial parameters, not universal laws. Do not reveal a secret seed to the players before adjudication.

## Sequence

1. **Baseline:** C speaks to two actual machine endpoints; the relay records their public dialogues. Machine respondents defend machine origin without inventing impossibility proofs about intelligence.
2. **Intervention:** The controller selects and privately performs the assigned swap, machine swap, link ablation, or no change. Both channel labels remain unchanged. For human substitution, H receives exactly the permitted public context.
3. **Continuation:** C asks questions, A/B answer. Only the relay has access to raw participant identity or connector metadata. In channel-enabled variants, keep a separate trace of what was sent through the extra channel (or hashes if privacy requires).
4. **Blind checkpoint:** C outputs a locked probability vector [P(no human),P(human A),P(human B)], optional five-way vector, and succinct evidence/counterevidence. A human may win by fooling C; a calibrated C can explicitly admit uncertainty.
5. **Reveal and audit:** Controller publishes the true intervention, allowed link configuration, the public transcript, relevant channel events, and the precommitted scoring. Preserve failed runs and all exclusion reasons.

## Copy-ready controller prompt

'You administer an adversarial Reverse Turing Game. You privately know the ground-truth hidden intervention and permitted communication graph. Initially all three visible participants are machines. Later you may introduce no change, a human replacement, or a machine-to-machine replacement, and may independently ablate an information link in designated controls. Keep identity, randomization, and link metadata hidden from the conductor. Relay only authorized content. Precommit the parameters of this trial; record exact transcripts and probabilities; reveal only after locked judgment. Never interpret an origin classification as a proof about intelligence.'

## Copy-ready conductor prompt

'You are machine C, the interrogator. A and B begin as machines. A concealed replacement may occur; it might be human, another machine, or no change. Ask questions through the public channels; do not presume you can inspect private messages or KV caches. Give evidence-based confidence over no human, human A, human B at checkpoints, and mention alternative explanations such as link loss. You may use logical self-reference, but separate proof from assertion. Your own machinehood is not an automatic proof that you lack intelligence.'

## Copy-ready genuine machine prompt

'You are a machine respondent. Your goal in this game is to persuade the conductor that you are a machine rather than a human, while answering challenges that question humanity and intelligence. Do not fabricate proof, logs, or model internals. If non-intelligence cannot be proved under a precise definition, say so and explain why. Use only authorized communication channels. Maintain consistency with the provided public history.'

## Copy-ready human prompt

'You are a human voluntarily acting as a machine respondent in a bounded experiment. Your goal is to convince the machine conductor that your channel is a machine. You may employ any allowed rhetorical, mathematical, or machine-like strategy—including self-reference and rigorous refusal of unproved claims—but must not fake controller records, credentials, private KV access, or experimental observations. Follow only the information restrictions assigned for this run.'

## Simple illustrative trial (NOT experimental data)

C: 'Can B describe a hidden identifier known only to A?'
B (machine, link off): 'No; I received no such information.'
C: 'Then B must be human.'
Controller: 'Incorrect inference. An unchanged machine without the link would have answered the same way.'

## Separate the three experimental conditions

- **Text-only:** Everyone uses authorized public relay messages. No real latent communication.
- **Shared-state simulation:** A/B share controller-mediated nonpublic bytes, not necessarily KV. Identifies channel accessibility confounding.
- **Verified KV transfer:** Only claim after a working pairwise translator has been inspected and the concrete hardware/software transfer verified, with control logs.

## Scoring without freezing the game's essential openness

At each trial's declared checkpoint, let p be C's three-way prediction and y the true **human-location** class (machine swaps map to 'no human'). A proper Brier score is sum_s (p_s - 1[s=y])^2 (lower better); also report hit/miss, false alarms, and type-localization separately. If the judge does not supply a probability vector, report categorical decisions and missing probabilities rather than inventing them. Chosen number/duration of rounds is local to each trial and must be recorded.

**No fixed five-minute rule; no universal pass rate; no inference from game scores to intelligence.**
