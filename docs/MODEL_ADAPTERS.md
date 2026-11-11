# R3 — Isolated model participants

**Research prototype.** The R2 game server owns the hidden intervention and applies authorization. R3 optionally connects *one specific machine role* to *one independently configured model process*. The human impersonator and independent controller remain manual. No real KV-cache translator is provided.

## 0. Start the relay

Requires Python 3.10+ (CI uses Python 3.12), no third-party Python dependencies.

```bash
python -m game.server --port 8765
```

The controller receives a unique participant URL for `conductor`, `machine_A`, `machine_B`, replacement machine endpoints, and the human. Each URL contains a `#token=...` fragment. Treat the token as a **secret**. Never put it into an issue, chat transcript, model prompt, log or command-line flag. The HTTP server binds to `127.0.0.1`; a remote multi-computer service is not supplied.

## 1. Bring your own models

For a local Chat Completions-compatible server (for example a configured LM Studio or llama.cpp endpoint), start separate terminal processes for the permitted machine roles. **Each process gets its own role token.**

### Respondent A

```bash
export RTT_ROLE_TOKEN='PASTE_MACHINE_A_TOKEN_FROM_CONTROLLER'
python -m game.agents \
  --role machine_A \
  --provider compatible \
  --model-url http://127.0.0.1:1234/v1/chat/completions \
  --model YOUR_EXACT_MODEL_ID
```

### Respondent B

In a separate terminal, set **machine_B's own** token and run the same command with `--role machine_B`. It can use a different model and/or endpoint.

### Machine conductor C

Use C's **own** token in a third terminal:

```bash
export RTT_ROLE_TOKEN='PASTE_CONDUCTOR_TOKEN_FROM_CONTROLLER'
python -m game.agents \
  --role conductor \
  --provider compatible \
  --model-url http://127.0.0.1:1234/v1/chat/completions \
  --model YOUR_EXACT_MODEL_ID \
  --question-budget 8
```

C asks questions on A and B in alternation, waiting for pending answers, then requests **strict JSON** with a three-way probability vector and explanatory evidence. If the provider returns malformed JSON or nonfinite probabilities, the actor **stops with an error** rather than fabricating or silently repairing a verdict.

The controller uses the browser to choose or draw a hidden intervention. If a human replaces B, the `machine_B` actor becomes inactive; the human continues from B's permitted public history, through the browser. To substitute another machine, start an actor with `--role replacement_A` or `replacement_B` using that role's token.

**Practical timing:** Start C and both machines, verify a genuine machine answer from A and B, then let the controller perform the hidden action while the trial continues. The conductor does not receive a signal saying that intervention has occurred. A verdict before intervention is scored as a no-change trial, not treated as an error.

### Remote API endpoints

To use an explicitly permitted remote Chat Completions provider, pass its exact **HTTPS** `.../chat/completions` URL and set an API key via a separate environment variable:

```bash
export RTT_MODEL_API_KEY='PROVIDER_KEY'
```

Only the model HTTP client sends this key. The relay token is sent only to the loopback game server. Neither credential is inserted into model prompt bodies by this code. This does not protect against provider-side retention of model inputs; consult the actual provider's policy and do not put private participant data into an external backend without consent.

Plain HTTP is permitted for **loopback model endpoints only**. HTTP redirects are refused to avoid credential forwarding. Backend implementations vary; R3 targets the basic Chat Completions `choices[0].message.content` response shape and may not support model-specific streaming, tool calling, or reasoning-token settings.

## 2. Scripted plumbing mode — no models required

You can smoke-test the transport with a deterministic, deliberately uninteresting stand-in:

```bash
export RTT_ROLE_TOKEN='ROLE_TOKEN'
python -m game.agents --role machine_A --provider scripted
```

Run separate terminal instances for `machine_B` and `conductor` (with distinct tokens and `--question-budget 4`). They will generate canned questions and canned machine answers. The scripted conductor submits `(0.6,0.2,0.2)`, which is a fixed demonstration vector, **not a posterior inferred from the transcript**. Do not include scripted mode results in human/machine capability comparisons.

## 3. How information is separated

```text
                   server/controller
                      truth + links
                           |
                permitted projections
                  /        |         \
             C public    A own      B own
             A and B     public     public
             only        + allowed  + allowed
                         private    private
                     separate model sessions
```

- **Conductor:** only publicly visible Q/A, no link metadata, hidden intervention, private payloads, controller audit or participant credentials.
- **Genuine machine:** only its current channel's public Q/A and permitted private handoffs. Inactive endpoints cannot post replies.
- **Human:** explicitly manual; the actor CLI refuses to automate the human role.
- **Controller:** holds secret state, chooses the intervention, reveals after C's verdict. The controller is never passed to a model adapter.

For additional defense, the prompt builder whitelists `kind`, `speaker`, `channel`, and `body` fields; timestamp, controller audit and raw internal IDs are omitted. Private handoffs, when permitted, are included only in the relevant *respondent* prompt, not C's prompt. An adversarial opponent may still attempt prompt injection inside visible messages; the relay grants no controller actions to a model role.

**This is software role isolation, not independent attestation**. A local operator, upstream shared state, external provider's cache policy, model nondeterminism, or side-channel timing may violate experimental independence. The code makes no claim of being production-secure.

### Experimental timing warning

In unpaced sessions, automatic respondents publish an answer immediately and C can infer response timing. R4 adds **server-controlled answer buffering**, with a common per-question release deadline configured by the controller before interrogation. An R3 model agent now waits after submitting a buffered reply instead of repeatedly answering. For controlled runs configure the fixed-release mode and use `--poll-seconds 0.25` for C. Provider, operating-system and network latency remain outside formal blinding guarantees; missed gates are invalid for the confirmatory pilot. See [PACING.md](PACING.md).

See [the proof-to-engine boundary](PROOF_IMPLEMENTATION_BRIDGE.md) and [preregistration](PILOT_PREREGISTRATION.md).

## 4. Controls and budgets

- `--question-budget N`: maximum total C questions before generating a verdict; N must be at least 2. This is a *trial-specific* parameter, not Turing's universal rule.
- `--context-events N`: most recent public events and, separately, most recent authorized private events to include in each model call. Truncation may change behavior; log its value.
- `--max-output-tokens N`: backend-requested completion budget (16–2048); provider may interpret differently.
- `--idle-timeout N`: if an actor makes no progress for N seconds, it exits without changing the controller's hidden state. The relay continues.
- `--poll-seconds N`: polling cadence, default 1 second. Participants can be stopped and restarted with their same role token. The relay owns the public transcript; the model clients are otherwise stateless.

The current relay does not enforce a global cost cap, persist trial configurations, independently attest randomization, or guarantee a participant's identity. Set operational budgets and record exact versions/provider settings before interpreting outcomes. For five equally likely hidden interventions the induced **three-way scoring prior is (3/5, 1/5, 1/5)**, not (1/3, 1/3, 1/3).

## 5. Verification

```bash
python -m unittest discover -s tests -v
python -m game.agents --help
lake build
```

The unit and loopback tests use a fake Chat Completions server. No real model-provider credentials or network-based LLM calls are exercised by CI. A green check establishes tested properties of the adapter under those mocks, not an independently reproduced human-versus-machine result.

**Research boundary:** model responses, proofs, self-claims of machinehood and alleged non-intelligence are different forms of evidence. The game must not conflate them.

## R5 fixed pilot: automatic conductor pause

When the independent controller enables `RTT-PILOT/1`, the machine conductor must be launched with `--question-budget 8`. It asks A and B once each, waits while the controller privately commits the assigned intervention, and resumes **only after the controller publishes the explicit, condition-independent continuation marker**. This marker is the same across all hidden participant conditions.

R5 enforces a fixed 45-second answer gate, forbids a ninth question and keeps the controller manual. The human remains a manual browser participant. See [STRICT_PILOT.md](STRICT_PILOT.md). A separate [observer sidecar](OBSERVER.md) can record first-seen event intervals but does **not** prove the conductor's actual delivery time. Do not report human-vs-machine results until independently controlled participant trials have been conducted.

## R7 — Active private text, not pretend KV sharing

The old adapter **read** permitted private messages but never **sent** them. To exercise the link in machine-operated trials, launch **all machine respondent processes** (including link-OFF controls) with `--private-handoff`:

```sh
python -m game.agents --role machine_A --provider compatible \
  --model-url http://127.0.0.1:1234/v1/chat/completions \
  --model YOUR_MODEL_ID --private-handoff
```

This is an **opt-in text-only research probe**. In every answering turn, the model returns strict JSON with two fields: `answer` (public) and `private_handoff` (private). The adapter makes **one model call in either link condition**, submits the private note only when `can_whisper` is authorized, then submits the public answer. Link-OFF notes are discarded. Real providers may use different token counts, caching or inference resources; a common request count is **not** a proof of compute parity.

**Reading is now symmetrical:** link OFF hides *all* historical private messages from both replacement machines and human impostors; ON exposes the channel's previously permitted text history to both, provided the human has a gateway. Directional open-game links filter each message by its **current** direction. Private content already absorbed into a persistent external model or human memory cannot be revoked by this software projection. The controller's private audit retains all messages and the conductor sees none of them.

A human with an authorized gateway can manually receive and send private text in the browser; the CLI never automates the human. If no actor actually sends messages, link ON is merely an **available affordance**, not a communication treatment. Record actual traffic and failure to use the channel before discussing missing-link effects. No real KV sharing is implemented.


## R8 — The actual conductor client can log first receipt

For an optional timing-controlled machine-conductor session, add `--trial-id RTT-01 --receipt-log private/C-RTT-01.jsonl --poll-seconds 0.1` to C's command. This wraps the same HTTP read used by the model-driving `Agent.step()` call. A separately running observer cannot provide this evidence. Start C **before the first question**; the logger refuses to invent a first-seen time for pre-existing events.

This does not expose receipt metadata to model prompts, attest the same OS clock across tunneled hosts, or establish when the provider internally processes the response. See the [conductor-receipt runbook](CONDUCTOR_RECEIPT.md) and use [offline timing check](../experiments/check_conductor_delivery.py) against the controller-only export.


## R10 — One completion, one atomic model-to-relay action

Prior to R10, `--private-handoff` sent a private `whisper` request *before* a separate public `answer` request. If the second request failed or crossed the release boundary, the private note could already have reached its recipient, breaking the experiment's intended one-answer/one-handoff correspondence.

Now the adapter generates the same two-field JSON output (`answer`, `private_handoff`) in one model call under either link condition, then submits **one** relay `respond` action. The server validates **both strings**, the participant's active role, the outstanding paced answer and the final acceptance time **before** changing public or private state. When the directed link is ON, the note and accepted public answer are committed together under one lock. When OFF, the note is discarded and the answer is accepted alone. The controller-only audit records `atomic_response.private_transmitted` or `private_discarded`, with no private note in that audit event.

This fixes a concrete partial-transfer failure and equalizes the **number of relay calls** made by machine agents in ON/OFF cells. It does **not** ensure the model uses equal tokens, context, wall-clock resources, or private-history knowledge; the model prompt's private data may legitimately differ across link conditions. Legacy manual `whisper` and `answer` remain separate for the original open game, so the atomic guarantee is restricted to machine agents using `--private-handoff`.

The strict paced relay rejects notes whose paired answer misses its deadline, including when the clock passes the gate between the initial due check and final receipt timestamp. A rejected action must not produce a private transfer; timeouts remain invalid protocol events. These are software-test claims, not empirical study outcomes.


## R11 — Reproducible local model-only rehearsal

The [rehearsal runner](REAL_MODEL_REHEARSAL.md) can start a fresh localhost relay, drive C/A/B plus an optional replacement machine through **their existing role-token HTTP clients**, and preserve model-call metadata, private/public controller records and the actual conductor receipt trace.

Set `--provider compatible` with an explicit per-role model endpoint file for **real model inference**, or `--provider scripted` only for a deterministic plumbing check. The runner will **not** simulate a human or count any run toward the 24 sealed trial assignments. The strict unbound 2+6 rehearsal keeps eight real 45-second gates; the smoke variant is a distinct, shorter non-study protocol. Failure remains a failed export, not a repaired answer.

**Limit:** role-token isolation is a property of the local HTTP relay. All models are currently coordinated from one trusted operator process, and local provider backends may retain shared internal state. An observed one-second delivery check is conditional on the shared-clock assumption, not evidence of backend or operator independence. No compatible-model run has yet been reported by CI.


## R12 — Compatible-provider HTTP path and acceptance boundary

R11's scripted smoke did not exercise `CompatibleChat` inside the full rehearsal. R12 now uses a distinct **localhost OpenAI-compatible HTTP stub** to exercise the real relay, provider request serialization, isolated role bearer tokens, authorization headers, strict JSON parsing, R10 atomic private handoffs and independent C-side receipt. It runs both link ON/OFF cases with matched provider request counts and deliberately fails one provider with an HTTP error. **The stub generates predetermined strings, not LLM inference.**

A real-time rehearsal is `completed` only if the protocol ended **and** the conditional R8 conductor receipt check passed. A verdict with a failed C timing audit is labeled `failed` while preserving its raw controller export. Synthetic-clock test runs now use the distinct status `simulated_protocol_only`. The `--allow-remote-model-api` flag is required before any remotely hosted HTTPS model endpoint can be used. This reduces accidental billable provider calls but cannot attest provider charges after intentional opt-in.

**Measurement caveat:** a shared, self-authored stub is not an independent inference backend, and one request per model role is not proof of token parity or KV isolation. No actual model-provider run was conducted in CI.
