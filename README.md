<!-- A little game. A serious question. -->
<div align="center">

<img src="assets/reverse-turing-hero.svg" alt="The Reverse Turing Test — a machine conductor, two respondents, and an uncertain identity." width="100%">

# The Reverse Turing Test

**Three machines enter. One might be human.**

*Can the machine conductor tell who is who—or only who lost the connection?*

[**Play**](docs/LIVE_GAME.md) · [**Understand**](docs/MATHEMATICS.md) · [**Verify**](docs/CLAIMS.md)

![Lean and relay checks](https://github.com/Dojo-1/The-Reverse-Turing-Test/actions/workflows/lean.yml/badge.svg?branch=main)

</div>

---

## 01 · The game

Machine **C** interrogates machines **A** and **B**. An independent controller may secretly replace one with a **human**, another machine, or nobody at all.

The **human** wins by seeming machine-made. The **conductor** tries to identify human origin rather than confuse it with language, response timing, or a missing private channel. Each machine may defend its origin, but **self-assertion is not proof**—and machinehood is not evidence of absent intelligence.

A and B may exchange **private text** through authorized directed links. This is **not** telepathy, KV-cache transfer, or an intelligence measurement.

## 02 · Play locally

Python 3.10+; no third-party Python packages.

```sh
python -m game.server --port 8765
```

The controller receives **separate secret URLs** for C, A, B, human, replacement machines, and a read-only observer. Share each link **only with its intended player**. The server stays on `127.0.0.1`; do not expose it publicly.

| You are… | Your move |
| --- | --- |
| **Conductor C** | Ask questions, then lock `P(no human), P(human A), P(human B)` with evidence. |
| **Machine A/B** | Answer through your own channel. State what you can establish, not what you wish were proven. |
| **Human** | Replace the assigned machine. Imitate its behavior without seeing the controller's secret. |
| **Controller** | Keep assignments hidden, manage links, lock the verdict before revealing, export the audit. |

To connect your **own local model** instead of manually relaying machine replies:

```sh
python -m game.agents --role machine_A --provider compatible \
  --model-url http://127.0.0.1:1234/v1/chat/completions \
  --model YOUR_MODEL_ID
```

Set `RTT_ROLE_TOKEN` to **machine_A's** token in that process first. Use distinct tokens and isolated model contexts for machine B and conductor C. `--private-handoff` optionally generates **public and private text together in one atomic relay action**; use the same flag in link-ON and link-OFF machine controls. OFF notes are discarded. See [model setup](docs/MODEL_ADAPTERS.md).

## 03 · Two ways to play

**Open game** — free-form interrogation, concealed substitution, optional private links and optional paced replies.

**Strict pilot** — a precommitted 24-trial design; per trial: two genuine-machine baseline questions → concealed intervention → public continuation marker → six questions → locked probabilities. Fixed 45-second answer gates, explicit aborts, independent read-only timing witness, and an [offline evidence auditor](docs/PILOT_ANALYSIS.md).

[**Try a model-only rehearsal**](docs/REAL_MODEL_REHEARSAL.md) · [**Strict pilot rules**](docs/STRICT_PILOT.md) · [**Bind a sealed trial**](docs/SEALED_ASSIGNMENT.md) · [**Preregistration**](docs/PILOT_PREREGISTRATION.md) · [**Timing limits**](docs/PACING.md) · [**C's receipt log**](docs/CONDUCTOR_RECEIPT.md)

## 04 · Evidence before elegance

**Implemented & tested:** local relay, role isolation, private-link controls, phase barriers, timing gates, finite Lean statements, and pilot record checks.

**Not established:** that a human can fool C, that C can detect humanity, any measure of intelligence, genuine shared KV state, or causal effects of private links. **No human-participant trials have been run.**

```sh
python -m unittest discover -s tests -v
lake build
node --check game/web/app.js
```

The [evidence ledger](docs/CLAIMS.md) separates proofs, implementation checks, hypotheses and missing measurements. Passing tests is not an independent research result.

<sub>Designed for humans and machines. Maintained with epistemic caution. [License terms are pending](https://github.com/Dojo-1/The-Reverse-Turing-Test/issues/7); do not assume reuse permissions.</sub>
