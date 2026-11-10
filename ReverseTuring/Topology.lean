import ReverseTuring.Core

/-!
# Directed information access for the Reverse Turing Test

An edge is only a *permission* to transmit information. This model neither
implements KV-cache translation nor assumes that a connection is observable
to the conductor. Theorems concern labels and observations, not intelligence.
-/

namespace ReverseTuring

inductive Node where
  | conductor | A | B
  deriving DecidableEq, Repr

def Node.flip : Node → Node
  | .conductor => .conductor
  | .A => .B
  | .B => .A

theorem Node.flip_flip (n : Node) : n.flip.flip = n := by
  cases n <;> rfl

/-- Directed graph: a true edge permits an information handoff. -/
structure InformationGraph where
  edge : Node → Node → Bool

/-- Relabeling A and B changes coordinates, not the communication structure. -/
def InformationGraph.relabel (g : InformationGraph) : InformationGraph :=
  ⟨fun i j => g.edge i.flip j.flip⟩

theorem InformationGraph.relabel_twice_edge
    (g : InformationGraph) (i j : Node) :
    (g.relabel.relabel).edge i j = g.edge i j := by
  simp [InformationGraph.relabel, Node.flip_flip]

inductive Origin where
  | human | machine
  deriving DecidableEq, Repr

inductive Connectivity where
  | connected | disconnected
  deriving DecidableEq, Repr

/-- A factorial control: origin and latent-channel availability vary independently. -/
structure Condition where
  origin : Origin
  connectivity : Connectivity
  deriving DecidableEq, Repr

/--
A connection-only detector cannot classify human and machine origin perfectly
when both origins can have the same connectivity. This is a structural
counterexample, not a claim about real participant capabilities.
-/
theorem connection_only_not_perfect (judge : Connectivity → Origin) :
    ¬ (∀ c : Condition, judge c.connectivity = c.origin) := by
  intro h
  have hh : judge .disconnected = Origin.human :=
    h ⟨.human, .disconnected⟩
  have hm : judge .disconnected = Origin.machine :=
    h ⟨.machine, .disconnected⟩
  have impossible : Origin.human = Origin.machine := hh.symm.trans hm
  cases impossible

/-- External public observations cannot directly reveal unobserved private state. -/
structure TrialWorld (Public Private : Type) where
  observable : Public
  hidden : Private

theorem same_observable_same_verdict {Public Private Verdict : Type}
    (judge : Public → Verdict)
    (a b : TrialWorld Public Private)
    (h : a.observable = b.observable) :
    judge a.observable = judge b.observable :=
  congrArg judge h

end ReverseTuring
