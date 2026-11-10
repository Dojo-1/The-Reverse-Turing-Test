import Init

/-!
# R4: Finite fixed-gate response visibility

A minimal *abstract* release-gate specification. It describes a single
public turn with discrete time, a known deadline and one response.

Its assumptions are strictly weaker than claiming real-time blinding:
different content, missed deadlines, provider context and network jitter
remain outside this theorem. Python server conformance is tested separately.
-/

namespace ReverseTuring

/-- A transcript initially contains only the question. When the gate opens,
a response received strictly before the deadline is released; otherwise an
explicit timeout marker is published. -/
def pacedPublic (now due receivedAt : Nat) (q answer : String) : List String :=
  if now < due then [q]
  else if receivedAt < due then [q, answer]
  else [q, "[NO RESPONSE BY DEADLINE]"]

/-- Even a received answer is unavailable before the release boundary. -/
theorem before_gate_only_question (now due receivedAt : Nat)
    (q answer : String) (h : now < due) :
    pacedPublic now due receivedAt q answer = [q] := by
  simp [pacedPublic, h]

/-- After the gate, a timely response is visible. -/
theorem after_gate_timely_answer (now due receivedAt : Nat)
    (q answer : String) (hNow : ¬ now < due)
    (hReceive : receivedAt < due) :
    pacedPublic now due receivedAt q answer = [q, answer] := by
  simp [pacedPublic, hNow, hReceive]

/--
Two answers with identical content and different receipt times induce the
same public transcript at EVERY observation time, provided that both arrived
strictly before the common deadline. No distributional or side-channel
equivalence beyond this public abstraction is asserted.
-/
theorem early_receipt_time_not_in_paced_transcript
    (now due received1 received2 : Nat) (q answer : String)
    (h1 : received1 < due) (h2 : received2 < due) :
    pacedPublic now due received1 q answer =
      pacedPublic now due received2 q answer := by
  simp [pacedPublic, h1, h2]

/-- A late response remains a protocol violation, not a masked success. -/
theorem after_gate_timeout (now due receivedAt : Nat)
    (q answer : String) (hNow : ¬ now < due)
    (hLate : ¬ receivedAt < due) :
    pacedPublic now due receivedAt q answer =
      [q, "[NO RESPONSE BY DEADLINE]"] := by
  simp [pacedPublic, hNow, hLate]

end ReverseTuring
