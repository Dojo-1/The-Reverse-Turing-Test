# R2 — Play the Reverse Turing Game in a browser

**Status:** local experimental relay. It is not an autonomous LLM orchestrator, a real KV-cache translator, a secure internet service, or a scientific evaluation by itself.

## Start

Requires Python 3.10+ (recommended Python 3.12), no additional packages. From the repository root:

    python -m game.server --port 8765

The terminal prints a **different link for every role**. Each link carries a random bearer credential in the URL fragment, not an ordinary query parameter. Keep the terminal output private; send each player **only their own link**. Use separate browser windows/sessions or separate computers with a *secure* local tunnel, as appropriate. The server deliberately binds to 127.0.0.1 only: no TLS, remote deployment or production identity infrastructure is supplied.

You need:
- a separate model/session acting as the **conductor** (C);
- a model/session acting as **machine A**;
- another model/session acting as **machine B**;
- one human volunteer acting as **human impersonator**;
- an **independent controller**, ideally not the person running C;
- optional replacement machine sessions.

The browser interface is an authenticated **manual relay**: copy a machine model's actual replies into its participant window and copy conductor questions back to its isolated model context. It does not automatically call an LLM API. Do **not** put controller metadata or another respondent's private messages into a machine's context.

## One trial

1. Open **controller**, **conductor**, **machine_A**, **machine_B** links in separate browser windows.
2. If using a directed private text link, the controller enables it using **Set baseline links**. A shared text handoff is a simulated side channel, *not a KV-cache transfer*.
3. C asks at least one question of A and B. Both genuine machines answer. The engine forbids intervention before receiving an answer from both.
4. The controller privately selects the intervention: **humanA**, **humanB**, **machineA**, **machineB**, or **unchanged**. Choose explicitly, or press **Draw randomly (five states)** for a cryptographically sampled uniform five-way choice. The independent controller sees the realized label; C does not. The controller can independently change A→B and B→A private links. For a human substitution, it can authorize a relay via **human gateway**. A gateway option chosen during a random draw is silently disabled if the sampled state has no human.
5. The controller hands the appropriate *new participant credential* to the replacement machine or human. The old respondent's credential becomes inactive. The new participant sees that channel's public history but not the other channel's public messages. A human without an authorized gateway sees no private messages.
6. C keeps interrogating, then commits a three-way vector **P(no human), P(human A), P(human B)** summing to 1, plus optional evidence. Crucially, **C can submit before any intervention**, in which case the controller must accept a no-change trial. This avoids revealing intervention timing through an API error.
7. Once the verdict is locked, the controller presses **Reveal outcome**. Both views can then see the outcome; the controller sees the correct class and Brier score.
8. The controller presses **Export audit JSON** to save all public text, private messages, intervention history, and verdict. The JSON contains no participant bearer tokens. The engine otherwise keeps the state **in memory only**: exit without export and the trial is lost.

**Prior warning:** Under the optional **uniform five-way draw**, the scored three-way hypotheses are *not* equally likely: three states (`unchanged`, `machineA`, `machineB`) collapse to `no_human`, so the induced prior is `(0.6, 0.2, 0.2)`. If there is no discriminating evidence, an optimal zero-one-loss conductor would guess `no_human` and achieve 60% under this particular draw. A conductor using a different controller-specified distribution must use that trial's prior instead. The UI intentionally does not prefill probabilities.

### Player-facing quick instructions

- **C**: ask adversarial questions, including Gödel/Curry-style logic and long-horizon consistency checks if you wish. Distinguish human origin from missing connection or machine replacement. Give calibrated probabilities; do not claim a proof of absent intelligence merely because something is a machine.
- **Machine A/B**: reply to C via your own channel; defend machine origin as far as evidence allows, without inventing credentials or proofs; optionally use explicitly authorized private text links. Do not send controller secrets.
- **Human**: act as the machine you replace. You may use mathematical, linguistic or epistemically cautious strategies. Access private text only if the controller explicitly supplies a gateway.
- **Controller**: keep participants isolated, record chosen topology and intervention, lock the verdict before revealing, and export the record.

See the fuller [human](HUMAN_PLAYER.md), [machine](MACHINE_PLAYERS.md), and [facilitator](HOST_AND_PLAY.md) guides.

## Blinding does not yet normalize physical timing

R3 conductor and respondent JSON projections whitelist fields and **omit stored timestamps**. R4 adds **optional** fixed-release answer buffering when the controller activates it before the first question. Without that setting, the relay still publishes replies immediately and the session is timing-visible. Even with it, client polling, OS scheduling, external inference providers and connection delays remain measurable; use the controller's `late_publication` and `deadline_miss` records to disqualify invalid runs.

Therefore, an ordinary local game is **timing-visible**. Do not label it timing-blinded or use it as the controlled pilot without a paced facilitator. For a timing-controlled pilot, configure the [R4 fixed-release gate](PACING.md) and independently verify actual delivery timing. The gate is a prerequisite, not proof of end-to-end blinding. See [PILOT_PREREGISTRATION.md](PILOT_PREREGISTRATION.md).

The five-state observational-equivalence theorem and its Python regression test apply only to serialized fields with matched visible transcripts and matched verdicts. They make no claim about network timing, answer content differences, or external model providers.

## Threat model and limitations

This is for **local, consented research**. Do not run it publicly on the internet, handle sensitive information, or collect identifiable data without consent. Tokens grant role access; anyone who knows a token can impersonate that role. A controller at the same keyboard sees all URLs. The service does not implement identity verification, cryptographically committed randomization, independent attestation, privacy-preserving audit export, TLS, database persistence, multi-instance coordination, or real KV transfer.

Random choice uses Python's `secrets.choice`, which does not expose a reproducible seed. This is useful for a local pilot but is **not** an independently witnessed or cryptographically precommitted allocation procedure. The host can rerun trials; a scientifically meaningful result requires a frozen protocol and accounting for all attempts.

The browser is for human operators *relaying* external model responses. Participant independence is a requirement of the experimental protocol, not something the software can guarantee. In particular, sharing one upstream model context between A and B would invalidate the independent-session condition.

The private channel is **ordinary controller-relayed text**, not hidden representation exchange. Do not interpret successful side-channel communication as evidence for SwaT's transfer mechanism.

The current score is a Brier score for the collapsed three-way **human location** classes, with machine swaps and unchanged trials grouped into **no human**. It does not measure whether a change occurred, whether a particular inference was justified, or any broad definition of intelligence. Future versions should support precommitted priors, proper participant scheduling, richer intervention hypotheses and longitudinal statistics.

## Verify

    python -m unittest discover -s tests -v
    node --check game/web/app.js
    lake build

Python unit and loopback HTTP tests exercise token authorization, role isolation, controller visibility, sham machine swaps, private-channel access, no-intervention verdicts, and scoring. The Lean files prove separate finite structural statements: runtime tests do not establish their semantic correspondence automatically. See [claims](CLAIMS.md).

## R5: opt-in structured pilot and read-only witness

The default open game remains free-form. To use the proposed precommitted 24-trial protocol, click **Enable strict pilot** on the controller screen *before* interrogation. The server then enforces a 45-second gate, genuine-machine baseline questions A and B, a hidden schedule-assigned intervention, a public resumption signal and six continuation questions. It also permits explicit abort/export of an incomplete run without inventing a verdict.

For detailed play see [STRICT_PILOT.md](STRICT_PILOT.md); start the read-only independent-process timing sidecar using [OBSERVER.md](OBSERVER.md). The sidecar has its own credential and sees no hidden intervention metadata.

**Caution:** the current app does not automatically verify that the controller selected the correct assigned trial row; an independent host must reconcile controller exports with the private committed schedule. The observer measures its own first HTTP receipt, not C's actual receipt.

## R7 — Private-link fairness

The current respondent view filters private messages by the **currently enabled directed link**, not merely by machine identity. After a swap with both links OFF, neither a replacement machine nor a human receives baseline private messages through the API. When links are ON and the human gateway is authorized, human and machine replacements inherit the same permitted channel-history view. This does not clear prior external provider memory.

Automated models can now **send** private text using `--private-handoff`. It requests the same two-field model response in both ON and OFF conditions, but only ON sends the private note. Existing manual web controls also let authorized players send text. The controller should verify actual messages in its private audit; `link ON` alone does not demonstrate an active side channel.

## Optional open-game covert compute (R13)

The controller may select `configure_covert_leech` **before the first public question**, only in the open game. The concealed human may make up to three resource-borrowing calculations, taking virtual credits from the other active machine, never C; machines may use their own equivalent in-game computation. This is **game-authorized virtual credit accounting**, not real hardware or API access. The donor sees a diminished reserve but no notice identifying the human; the controller sees the private audit; C and the public observer do not see covert actions. The donor's own public reaction can create a detection risk. See [the complete rules](COVERT_COMPUTE.md).

**Turing historical reference:** [Stanford Encyclopedia of Philosophy](https://plato.stanford.edu/entries/turing-test/) — an average interrogator's 70% chance of correct identification after five minutes was a prediction for the original imitation game, **not** a per-verdict confidence threshold. Our reverse human objective remains explicitly a variant. Do not turn one human disguise success into a claim about the historical prediction.
