# R3 bridge: formal projection ↔ runtime conductor view

Date: 2026-11-10. This is a **traceability specification**, not a formal verification of Python source code.

## Claimed invariant

For two game snapshots S and T satisfying:

1. Neither has been revealed.
2. Both have the **same ordered public payloads**: event kind, channel, speaker and body.
3. Both have the same locked verdict (either absent or equal).

the **serialized conductor view** is equal, even if the underlying hidden substitution, private messages, controller audit, internal event indices or stored timestamps differ.

This is *serialized observational equivalence*. It does **not** imply equality of actual time to answer, message availability, network latency, thread scheduling, model internal memory or any other signal outside the serialized JSON view.

## Proof-to-implementation map

| Formal object | Python implementation | Witness |
| --- | --- | --- |
| Lean `PublicPayload` | `Game._project(..., private=False)` output kind/channel/speaker/body | `test_public_timestamp_and_future_metadata_are_not_projected` |
| Lean `LoggedEvent.internalSequence, timestamp` | `Game._event` stores global sequence and UTC timestamp | The public projection strips them |
| Lean `projectedPublic` | `Game._project` dense local numbering | `test_public_sequences_cannot_reveal_hidden_controller_events` |
| Lean `Snapshot.hidden` | `Game.condition` | Five-condition metamorphic test |
| Lean `Snapshot.privateEvents, controllerAudit` | `Game.private, Game.audit` | Different private/audit traces, equal conductor projections |
| Lean `Snapshot.verdict` | `Game.verdict` | Metamorphic test holds verdict equal |
| Lean `Snapshot.revealed` | `Game.revealed` | Equality before reveal; origin disclosed explicitly after |
| Lean `ConductorProjection` | `Game.view("conductor")` | Black-box equality of complete returned Python dicts |

The Lean file `ReverseTuring/Noninterference.lean` proves `preReveal_observational_noninterference` and narrower invariants on a purpose-built pure model. The Python regression compares **actual serialized fields** under all five different hidden conditions with matched public answers.

## Review implications

- **What is proved:** Conditional equality of the formal abstract projection.
- **What is tested:** Conformance of the current Python implementation on specifically constructed adversarial histories.
- **What is not proved:** Python implements the Lean model for every possible execution; semantic equality of different human/model replies; no timing signal outside the JSON structure; no cross-participant provider shared state; absence of prompt injection.
- **Strongest falsifier:** Construct two unrevealed sessions with equal public payload and verdict but different private/hidden metadata whose conductor JSON outputs differ. The Python test should then fail. A live observer detecting identity from response latency despite identical JSON does not refute the formal theorem; it refutes the broader *operational blinding* assumption.

## The timing obstruction

R3 strips timestamps from conductor and respondent-facing events, but its HTTP relay still makes answers available immediately. Hence a live conductor can estimate response latency from when it asks versus when the reply becomes visible. For a **timing-controlled** empirical trial, the host must withhold replies until a precommitted common release boundary, or a future relay must enforce this mechanically. Treat unpaced R3 runs as **timing-visible exploratory trials**.

The controller retains raw timestamps for diagnostics and integrity checking, but cannot claim that their retention alone normalizes them.

## Source independence

These Lean definitions, Python code, and Python tests were developed as one AI-assisted programme. Agreement among them is a useful consistency test, **not independent replication**. Independent reproduction would include another reviewer creating a reference implementation or testing against independently generated hidden traces.
