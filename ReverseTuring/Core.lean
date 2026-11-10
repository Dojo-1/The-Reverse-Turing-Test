import Init

/-!
# Reverse Turing Test: finite structural core

This file does NOT formalize intelligence, physical machine origin, equilibrium,
or Bayesian optimality. It establishes structural results about label symmetry,
deterministic observation, and finite adaptive conversations.
-/

namespace ReverseTuring

inductive Channel where
  | A | B
  deriving DecidableEq, Repr

def Channel.flip : Channel → Channel
  | .A => .B
  | .B => .A

theorem Channel.flip_flip (c : Channel) : c.flip.flip = c := by
  cases c <;> rfl

inductive HiddenState where
  | unchanged | humanA | humanB | machineA | machineB
  deriving DecidableEq, Repr

def HiddenState.flip : HiddenState → HiddenState
  | .unchanged => .unchanged
  | .humanA => .humanB
  | .humanB => .humanA
  | .machineA => .machineB
  | .machineB => .machineA

theorem HiddenState.flip_flip (s : HiddenState) : s.flip.flip = s := by
  cases s <;> rfl

structure TwoChannelTranscript (Message : Type) where
  A : List Message
  B : List Message
  deriving Repr

def TwoChannelTranscript.flip {Message : Type}
    (t : TwoChannelTranscript Message) : TwoChannelTranscript Message :=
  ⟨t.B, t.A⟩

theorem TwoChannelTranscript.flip_flip {Message : Type}
    (t : TwoChannelTranscript Message) : t.flip.flip = t := by
  cases t
  rfl

/-- A classifier is perfect if it identifies every latent state from its observation. -/
def Perfect {State Observation : Type}
    (observe : State → Observation) (judge : Observation → State) : Prop :=
  ∀ s, judge (observe s) = s

/--
If distinct latent states produce exactly the same observation, no deterministic
classifier on that observation can identify both states perfectly.
-/
theorem collision_forbids_perfect
    {State Observation : Type}
    (observe : State → Observation) (judge : Observation → State)
    (a b : State) (hne : a ≠ b) (hobs : observe a = observe b) :
    ¬ Perfect observe judge := by
  intro hp
  apply hne
  calc
    a = judge (observe a) := (hp a).symm
    _ = judge (observe b) := congrArg judge hobs
    _ = b := hp b

/-- Conversation history, preserving question/response pairing. -/
abbrev History (Question Answer : Type) := List (Question × Answer)

/-- A finite, deterministic, history-adaptive interaction. -/
def run {Question Answer : Type} (n : Nat)
    (ask : History Question Answer → Question)
    (reply : History Question Answer → Question → Answer) :
    History Question Answer :=
  match n with
  | 0 => []
  | n + 1 =>
      let past := run n ask reply
      let q := ask past
      past ++ [(q, reply past q)]

/--
If two respondents have extensionally identical reply policies for all possible
histories and queries, they generate identical finite histories even under an
adaptive interrogator.
-/
theorem run_eq_of_reply_eq {Question Answer : Type}
    (n : Nat) (ask : History Question Answer → Question)
    (r₁ r₂ : History Question Answer → Question → Answer)
    (h : ∀ past q, r₁ past q = r₂ past q) :
    run n ask r₁ = run n ask r₂ := by
  induction n with
  | zero => rfl
  | succ n ih =>
      simp [run, ih, h]

/-- An observation-blind classifier must return equal verdicts on equal histories. -/
theorem same_history_same_verdict {Question Answer Verdict : Type}
    (judge : History Question Answer → Verdict)
    (h₁ h₂ : History Question Answer) (h : h₁ = h₂) :
    judge h₁ = judge h₂ := congrArg judge h

end ReverseTuring
