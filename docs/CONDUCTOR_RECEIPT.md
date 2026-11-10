# R8 · The conductor's own clock

**Tested local instrumentation, not human/model research data.**

R5's observer measured its own HTTP polling stream. R8 instruments the *actual machine-conductor process*, immediately around the `Agent.step()` view request. No extra polling connection is created, and no timing metadata is inserted into the conductor's model prompt.

## Start before the first question

Run the local game server. Create a private output directory, set **C's own** token and start C with a unique assigned trial ID:

```sh
export RTT_ROLE_TOKEN='CONDUCTOR_TOKEN_FROM_CONTROLLER'
python -m game.agents \
  --role conductor --provider compatible \
  --model-url http://127.0.0.1:1234/v1/chat/completions \
  --model YOUR_MODEL_ID --question-budget 8 \
  --poll-seconds 0.1 \
  --trial-id RTT-01 \
  --receipt-log private/C-RTT-01.jsonl
```

The output file must not already exist, and the first conductor view must have an **empty public transcript**. The CLI cannot backdate earlier arrivals. `--receipt-log` requires `--trial-id` and is accepted only for the machine-conductor role. Use a new server and separate log per real trial.

The file contains a header, all conductor poll intervals, SHA-256 digests of first-seen public events (not raw conversation text), and an explicit ending status. Failed, interrupted and idle runs are preserved as incomplete. If running on Windows, configure private NTFS access permissions separately: requesting POSIX `0600` alone does not secure an NTFS file.

## Compare the server's clock with C's HTTP arrival

After the controller downloads its secret-state JSON export:

```sh
python -m experiments.check_conductor_delivery \
  --controller-export private/RTT-01.json \
  --conductor-receipt private/C-RTT-01.jsonl \
  --output private/delivery-RTT-01.json
```

The checker verifies event hashes, dense history, required polls, complete status, eight paced answers in strict mode, each server `paced_release` record, and the signed gap between server publication and C's actual HTTP response completion.

`within_one_second_given_same_clock` means: **assuming the relay and conductor use the same OS monotonic-clock domain**, every paced answer was observed at the conductor client within one second after publication. This same-host assumption is **not independently attested** by the tool. The measurement also precedes model prompt handling; it cannot prove when or how a model internally perceived the event.

The `--rehearsal` flag permits incomplete non-pilot testing. Never use it to relabel an actual pilot trial.

## Falsifiers and evidence status

The suite checks independent numerical toy cases at 125 ms (accepted), 1,600 ms (rejected) and negative lag (rejected), plus missing/modified receipts, and one real loopback HTTP answer delivered through the server's release worker with a one-second gate. All are **software tests**, not volunteer or real LLM experiments.

A failed digest, incomplete log, clock inconsistency, explicit timeout or delivery later than one second **invalidates the claimed transport control**. Keep the failed record. Even if every check passes, the report retains `confirmatory_ready: false`: it cannot attest operator independence, model state, actual KV sharing, correct human recruitment or the causal missing-link hypothesis. No human-participant trials have yet occurred.
