# R5 read-only timing observer

The R5 relay issues an additional `observer` token. This participant can **read only the public transcript**; it cannot see private messages, controller assignments, intervention metadata or model credentials, and cannot submit game actions.

It provides an independently running **timing observation process**, not an independent scientific reproduction. Its software and tests were built within the same project.

## Start before the first question

From a separate local terminal, set the private observer token (the URL fragment supplied by the controller) and choose a new output file:

```bash
export RTT_ROLE_TOKEN='OBSERVER_TOKEN_ONLY'
python -m game.observer \
  --trial-id RTT-01 \
  --relay http://127.0.0.1:8765 \
  --poll-seconds 0.1 \
  --duration-seconds 1800 \
  --output private-witness-RTT-01.jsonl
```

The observer fails if public events already exist on its first request. It refuses to overwrite an existing file and creates a private `0600`-permission JSONL log on POSIX systems. Do not publish the token, terminal output containing credentials, or raw identifiable participant content.

For every newly seen public event, the witness records its kind, channel, projected sequence number, SHA-256 digest of public payload, local request-start monotonic nanoseconds, local response-complete monotonic nanoseconds, previous poll-complete monotonic nanoseconds and local UTC wall clock. It deliberately **does not log raw dialogue**.

The first observation of an event is bounded by the interval between the previous completed poll and the new poll's completion, **provided the witness started before the first question and its polling did not stop**. If several messages appear between polls they may share the same window. A hash proves neither participant provenance nor absence of a covert channel.

## What it cannot establish

- The conductor's actual receipt time; its TCP session and polling loop differ from the observer's.
- Perfect synchronization across different computers; monotonic clocks cannot be compared across hosts without a validated transport.
- Accurate delivery latency in a busy OS or over unknown network paths.
- Independent human evaluation of model capabilities or a proof about intelligence.

If the observer and relay run on the **same host** they can, with appropriate calibration, relate `time.monotonic_ns` readings to the controller's monotonic release timestamps. That remains a **surrogate observation**, not direct measurement of C's experience. Independently instrument C before making a confirmatory end-to-end timing claim.

## Protocol failures

Keep and mark incomplete logs when an observer fails, misses a poll, starts after the first event or detects non-dense event numbering. Do not discard those trials selectively. The absence of a witness log is a missing-data condition, not evidence that a gate succeeded.

For the [24-trial study](PILOT_PREREGISTRATION.md), both the controller-only audit and a matched observer file should be preserved with each assigned trial ID, and the client receipt tolerance should be measured directly before results are promoted.
