import Init

/-!
# Finite weighted classification bound (no Mathlib dependency)

A row contains nonnegative joint masses for an observation under the
three human-location hypotheses. For each observation, an arbitrary
deterministic judge selects a single hypothesis. The row maximum gives a
pointwise upper bound. Normalization into probabilities is external to R1;
the same bound applies after division by the common positive total mass.

This file does not claim an equilibrium or stochastic transfer result.
-/

namespace ReverseTuring

inductive Hypothesis where
  | noHuman | humanA | humanB
  deriving DecidableEq, Repr

abbrev WeightedRow := Hypothesis → Nat

/-- Correctly classified joint mass contributed by one observation. -/
def selectedMass (w : WeightedRow) (h : Hypothesis) : Nat := w h

/-- Largest achievable correctly classified mass at this observation. -/
def rowUpper (w : WeightedRow) : Nat :=
  max (w .noHuman) (max (w .humanA) (w .humanB))

theorem selected_le_upper (w : WeightedRow) (h : Hypothesis) :
    selectedMass w h ≤ rowUpper w := by
  cases h with
  | noHuman =>
      exact Nat.le_max_left _ _
  | humanA =>
      calc
        selectedMass w .humanA = w .humanA := rfl
        _ ≤ max (w .humanA) (w .humanB) := Nat.le_max_left _ _
        _ ≤ rowUpper w := Nat.le_max_right _ _
  | humanB =>
      calc
        selectedMass w .humanB = w .humanB := rfl
        _ ≤ max (w .humanA) (w .humanB) := Nat.le_max_right _ _
        _ ≤ rowUpper w := Nat.le_max_right _ _

/-- Total unnormalized correct-classification mass for a finite observation table. -/
def totalScore (rows : List WeightedRow) (judge : WeightedRow → Hypothesis) : Nat :=
  rows.foldr (fun w acc => selectedMass w (judge w) + acc) 0

def scoreCeiling (rows : List WeightedRow) : Nat :=
  rows.foldr (fun w acc => rowUpper w + acc) 0

/--
Any classifier is bounded by the sum of per-observation likelihood maxima.
The representation uses row contents as observations: for a real transcript
table, include a unique transcript identifier in the observation type.
-/
theorem totalScore_le_ceiling
    (rows : List WeightedRow) (judge : WeightedRow → Hypothesis) :
    totalScore rows judge ≤ scoreCeiling rows := by
  induction rows with
  | nil => simp [totalScore, scoreCeiling]
  | cons w ws ih =>
      change selectedMass w (judge w) + totalScore ws judge ≤
        rowUpper w + scoreCeiling ws
      exact Nat.add_le_add (selected_le_upper w (judge w)) ih


/-- Choose the larger of two joint masses, breaking ties toward the first. -/
def bestOfTwo (w : WeightedRow) (a b : Hypothesis) : Hypothesis :=
  if w a ≥ w b then a else b

theorem bestOfTwo_mass (w : WeightedRow) (a b : Hypothesis) :
    w (bestOfTwo w a b) = max (w a) (w b) := by
  by_cases h : w a ≥ w b
  · simp [bestOfTwo, h, Nat.max_eq_left h]
  · have hba : w a ≤ w b := by omega
    simp [bestOfTwo, h, Nat.max_eq_right hba]

/-- A deterministic maximizer for the three human-location hypotheses. -/
def bestHypothesis (w : WeightedRow) : Hypothesis :=
  bestOfTwo w (bestOfTwo w .noHuman .humanA) .humanB

theorem bestHypothesis_attains (w : WeightedRow) :
    selectedMass w (bestHypothesis w) = rowUpper w := by
  calc
    selectedMass w (bestHypothesis w) =
        max (w (bestOfTwo w .noHuman .humanA)) (w .humanB) :=
      bestOfTwo_mass w (bestOfTwo w .noHuman .humanA) .humanB
    _ = max (max (w .noHuman) (w .humanA)) (w .humanB) := by
      rw [bestOfTwo_mass w .noHuman .humanA]
    _ = rowUpper w := Nat.max_assoc _ _ _

/-- Attainment: pointwise maximum-likelihood decisions achieve the upper bound. -/
theorem totalScore_best_eq_ceiling (rows : List WeightedRow) :
    totalScore rows bestHypothesis = scoreCeiling rows := by
  induction rows with
  | nil => rfl
  | cons w ws ih =>
      change selectedMass w (bestHypothesis w) + totalScore ws bestHypothesis =
        rowUpper w + scoreCeiling ws
      rw [bestHypothesis_attains, ih]

/-- If all three joint masses are equal, the per-observation ceiling is that mass. -/
theorem equal_weight_ceiling (w : WeightedRow)
    (ha : w .humanA = w .noHuman)
    (hb : w .humanB = w .noHuman) :
    rowUpper w = w .noHuman := by
  simp [rowUpper, ha, hb]

end ReverseTuring
