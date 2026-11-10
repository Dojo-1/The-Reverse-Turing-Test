import ReverseTuring.Core

/-!
# R3: Pre-reveal observational noninterference for the conductor

This is a deliberately small, executable specification of the *projection*
contract implemented in Python by Game._project and Game.view("conductor").
The connection is checked by separate black-box tests, NOT by a proof of
Python-to-Lean program equivalence.

A public transcript contains event payloads and internal metadata. The
conductor receives only the public payloads and a dense local index, plus a
verdict it already supplied. Before reveal it cannot observe the hidden
intervention or a private message *through these serialized view fields*.

This proof makes NO assertion about live wall-clock arrival times, model
provider internals, token timing, or the contents of observable answers.
-/

namespace ReverseTuring

structure PublicPayload where
  kind : String
  channel : Channel
  speaker : String
  body : String
  deriving Repr, DecidableEq

structure LoggedEvent where
  payload : PublicPayload
  internalSequence : Nat
  timestamp : Nat
  deriving Repr, DecidableEq

/-- Indexes a public event list from n, without consulting internal metadata. -/
def indexPayloads (n : Nat) : List PublicPayload → List (Nat × PublicPayload)
  | [] => []
  | p :: ps => (n, p) :: indexPayloads (n + 1) ps

/-- Abstraction of Game._project: whitelist payload fields, reindex densely. -/
def projectedPublic (events : List LoggedEvent) :
    List (Nat × PublicPayload) :=
  indexPayloads 1 (events.map LoggedEvent.payload)

structure Snapshot (Verdict : Type) where
  hidden : HiddenState
  publicEvents : List LoggedEvent
  privateEvents : List String
  controllerAudit : List String
  verdict : Option Verdict
  revealed : Bool

structure ConductorProjection (Verdict : Type) where
  publicEvents : List (Nat × PublicPayload)
  verdict : Option Verdict
  revealed : Bool
  outcome : Option HiddenState

/-- The only hidden state released to C is the reveal-time outcome. -/
def conductorProjection {Verdict : Type} (s : Snapshot Verdict) :
    ConductorProjection Verdict :=
  { publicEvents := projectedPublic s.publicEvents
    verdict := s.verdict
    revealed := s.revealed
    outcome := if s.revealed then some s.hidden else none }

/--
Different timestamps and internal event sequence numbers cannot be observed
through the conductor's projected transcript if the message payloads agree.
-/
theorem projectedPublic_eq_of_same_payloads
    (xs ys : List LoggedEvent)
    (h : xs.map LoggedEvent.payload = ys.map LoggedEvent.payload) :
    projectedPublic xs = projectedPublic ys := by
  simp [projectedPublic, h]

/--
Pre-reveal: same visible messages and same locked verdict imply identical
serialized views, even if physical origin, private handoffs and controller
audit differ. This is a conditional projection theorem, not a theorem that
actual humans and machines produce the same transcript.
-/
theorem preReveal_observational_noninterference {Verdict : Type}
    (s t : Snapshot Verdict)
    (hs : s.revealed = false) (ht : t.revealed = false)
    (hm : s.publicEvents.map LoggedEvent.payload =
          t.publicEvents.map LoggedEvent.payload)
    (hv : s.verdict = t.verdict) :
    conductorProjection s = conductorProjection t := by
  simp [conductorProjection, hs, ht, projectedPublic, hm, hv]

/-- A concealed change of origin alone cannot change the projection. -/
theorem concealed_origin_change_is_invisible {Verdict : Type}
    (s : Snapshot Verdict) (h : s.revealed = false)
    (other : HiddenState) :
    conductorProjection {s with hidden := other} = conductorProjection s := by
  simp [conductorProjection, h]

/-- Private data changes alone do not change the conductor projection. -/
theorem private_handoff_is_not_a_public_field {Verdict : Type}
    (s : Snapshot Verdict) (other : List String) :
    conductorProjection {s with privateEvents := other} =
      conductorProjection s := by
  rfl

/-- The controller may reveal the hidden state only after the reveal flag. -/
theorem explicit_reveal_discloses_origin {Verdict : Type}
    (s : Snapshot Verdict) (h : s.revealed = true) :
    (conductorProjection s).outcome = some s.hidden := by
  simp [conductorProjection, h]

end ReverseTuring
