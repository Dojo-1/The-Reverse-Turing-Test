# R11 · One real-model rehearsal

**Purpose:** Run the first machine-only Reverse Turing rehearsal against explicit model endpoints, inspect failures, and preserve raw evidence. **Not one of the 24 assigned trials.** No human participant is simulated.

This runner uses a fresh localhost HTTP server, model-specific role tokens, the existing R10 atomic text handoff, a conductor-side R8 receipt trace and a protected controller export. It coordinates models in **one trusted Python operator process**, so separate role-scoped HTTP views **do not independently certify** backend isolation or operator honesty.

## First verify the plumbing (scripted, not real AI)

From the repository root, with Python 3.10+:

```sh
python -m experiments.rehearse_models \
  --provider scripted --mode smoke \
  --gate-seconds 1 \
  --condition machineA --link-after off \
  --output-dir private/scripted-smoke-01
```

This uses `ScriptedDemo`—a fixed text fixture **not a model**. A fresh private directory is required each time; existing output directories are never overwritten. The four-turn smoke uses actual HTTP on localhost and actual one-second release gates. The eight-question strict-pilot test in CI uses an **injected synthetic clock**, so it is not a real-time calibration.

## Configure actual local inference

Provide a **private** JSON model map with exactly the roles needed for your chosen machine-only intervention. Example for `--condition machineA`:

```json
{
  "roles": {
    "conductor": {"endpoint": "http://127.0.0.1:1234/v1/chat/completions", "model": "YOUR_C_MODEL"},
    "machine_A": {"endpoint": "http://127.0.0.1:1234/v1/chat/completions", "model": "YOUR_A_MODEL"},
    "machine_B": {"endpoint": "http://127.0.0.1:1234/v1/chat/completions", "model": "YOUR_B_MODEL"},
    "replacement_A": {"endpoint": "http://127.0.0.1:1234/v1/chat/completions", "model": "YOUR_REPLACEMENT_A_MODEL"}
  }
}
```

Use the actual model IDs served by your compatible local server. `unchanged` needs only C/A/B; `machineB` needs C/A/B/replacement_B. Use distinct backend sessions where possible. **Different `CompatibleChat` objects and separate bearer tokens do not prove that an inference server shares no KV cache or global context.**

Each role may optionally specify `max_output_tokens` (16–2048) and `api_key_env` (an environment-variable *name*, never the key). The runner fetches credentials from your local environment and never saves their values. Plain HTTP nonloopback inference and URLs containing credentials are rejected. External HTTPS model providers can bill you. **Remote model APIs are rejected by default**; to permit them you must explicitly pass `--allow-remote-model-api`, and you remain responsible for provider pricing. Local loopback endpoints require no such flag.

## Run the actual unbound 2+6 rehearsal

```sh
python -m experiments.rehearse_models \
  --provider compatible \
  --models-config private/models.local.json \
  --mode unbound-pilot \
  --condition machineA --link-after off \
  --gate-seconds 45 \
  --poll-seconds 0.1 \
  --max-wall-seconds 900 \
  --output-dir private/model-rehearsal-01
```

The runner starts **its own** loopback relay and returns only after completion or a bounded failure. Do not separately run `game.server` on its behalf. In unbound-pilot mode, each of eight answers has a **real 45-second gate**, so the pacing alone requires at least **six minutes**; model inference adds time. This mode uses the R5 public phase barrier and controller-only machine replacement without implying a human was present.

By default each machine actor asks its model for strict JSON containing a public `answer` and a `private_handoff`. The server sends private text only over authorized links; after link-OFF intervention it discards newly generated notes. Use `--no-private-handoff` only to test a **different protocol**, and do not mix this with ON/OFF comparisons while claiming resource parity. A model that cannot produce valid strict JSON makes the run fail; the runner does not silently rewrite its output.

## Evidence and privacy

The new output directory contains:

| File | Meaning |
| --- | --- |
| `manifest.json` | Provider class, role model IDs, endpoint configuration **without keys**, success/failure status, clock source, actual private-message count |
| `controller.json` | Controller-only raw game export with private and public text, actual timed releases, intervention and verdict when completed |
| `conductor.jsonl` | The actual conductor HTTP polling/first-receipt trace, never the controller secret |
| `model_calls.json` | Per-role call durations, prompt/output hashes and character counts; **not token usage** |

The manifest also includes a conditional R8 delivery check. A true `within_one_second_given_same_clock` is **only** evidence of observed transport behavior on the operator's assumed shared monotonic clock; it is **not** independent verification of the model's understanding or human identity.

A real-time run is marked `completed` **only when its protocol completed and its conditional C-receipt transport audit passed**. If the verdict exists but the delivery check fails, `status=failed` and the original verdict, receipt evidence and typed error remain preserved. Injected-clock protocol tests are instead labeled `simulated_protocol_only` and are never physical transport measurements.

All runs are tagged `is_preregistered_trial=false`, `human_participants=0`, and `confirmatory_ready=false`. Real-time runs use evidence status `non_study_rehearsal`; injected-clock tests are explicitly tagged `synthetic_clock_protocol_test`. If an exception, invalid model completion, deadline miss or insufficient wall time occurs, the runner preserves the **failed** record and reason instead of fabricating a verdict.

Logs are created with owner-only POSIX modes and placed under a `private/` directory ignored by Git. **Windows NTFS access controls require separate configuration**; mode bits alone are not a Windows privacy guarantee. Avoid uploading controller exports or model credentials to public issues or pull requests.

## Falsification, promotion and next step

**Rehearsal acceptance:** actual compatible model completions for all roles, successful 2+6 phase transition, valid strict JSON verdict, actual ON/OFF private transmission records, complete conductor first-receipt history, and no deadline/timing violations. Record actual model identifiers and their inference settings.

**Kill conditions:** a mismatched role/model endpoint, malformed output, private note delivered in link OFF, model state reused across supposedly independent actors, missing release, invalid C log, or delivery beyond the one-second threshold. Mark the rehearsal failed and preserve artifacts.

**Research promotion requires more:** independent provider-state/isolation checks, human recruitment and consent, a *previously published* sealed assignment, verified client clock-domain conditions, an independently reviewed analysis and genuine 24-trial data. No inference about human recognition or intelligence follows from running this rehearsal alone.
