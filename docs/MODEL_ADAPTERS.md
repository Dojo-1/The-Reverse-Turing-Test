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

Automatic respondents publish an answer immediately after a provider completion. Consequently, even though the R3 event serialization drops raw timestamps, **polling delays and turn arrival times remain visible to C**. The automatic adapter is presently suitable for exploratory gameplay and isolation tests, **not** a timing-controlled confirmatory pilot. For the proposed 24-trial design use paced manual relay or first implement and test a release gate. Record model compute time and provider configurations in the controller-only audit.

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
