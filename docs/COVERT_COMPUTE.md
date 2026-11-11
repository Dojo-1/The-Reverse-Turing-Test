# Optional covert-compute variant · Same Reverse Turing Test

**The objective is unchanged.** Human H, secretly substituted into A or B, tries to pass as a machine. Conductor C interrogates both channels to identify their origins. The controller alone knows the substitution. Nothing in this variant reveals it directly to C.

## Covert borrowing is an in-game capability, not unauthorized access

The controller may enable **covert compute** before the first question of the OPEN GAME. It cannot be combined with the sealed RTT-PILOT/1 allocation.

A substituted human may invoke \`leech_compute\` to request a deterministic modular exponentiation from the **virtual compute reserve** of the other active machine. The conductor's resources can never be targeted. Each machine begins with 12 game credits, and the human may attempt at most three covert operations. Increasing exponent sizes costs 1–3 credits. The human receives the result in their private view; the donor machine sees its own reduced reserve but **not** who consumed it or what the human requested. If that machine calls attention to its shortage during interrogation, C may infer something indirectly. The controller's private audit retains the operation. C's public view and the read-only observer do not contain any covert logs, credit balances or operations.

Machines can use their own credits for the exact same computational task; each receives its answer privately. Neither operation accesses another participant's hardware, process, cloud account, model context, paid API or inference quota. This is an authorized **game-economy simulation** of resource borrowing, not a tool for actually taking compute from another party. The mechanic deliberately makes borrowing useful but risky.

### Example

While acting as respondent, H can privately request modular exponentiation (\`base=2, exponent=10, modulus=101\`). The server returns **14** to H and reduces the other machine's virtual credit balance by one. The conductor sees only H's subsequent public response, not the hidden operation. A machine respondent may request the same calculation from its own reserve.

This *does not* prove human/machine computational equivalence in real hardware or inference resources. It creates a controlled, falsifiable **behavioral** consequence: donor credit depletion can influence its later answers.

## Time and identification: Stanford as historical source of truth

The [Stanford Encyclopedia of Philosophy, “The Turing Test”](https://plato.stanford.edu/entries/turing-test/), §1 and §3.2, quotes Turing's 1950 prediction:

- Approximate storage capacity: **\(10^9\)** (one billion).
- After **five minutes of questioning**, an average interrogator would have **no more than a 70% chance of making the correct identification**.
- In the original machine-versus-human game summarized by Stanford, the *machine* attempts to deceive the interrogator while the *human* assists correct identification. Our reverse game **deliberately swaps the human's incentive**; it is not Turing's original design.

For this implementation, C's existing three-class verdict remains \`P(no_human), P(human_A), P(human_B)\`. A **categorical identification** is the unique highest-probability class; an exact tie means \`undecided\`. After reveal, the controller records whether C identified the correct class, whether a human escaped correct location identification, and whether C missed human presence entirely. A human mislabeled as a machine at A while C mistakenly identified B as human is a **wrong location**, not a false absence claim. Brier remains a separate probabilistic-quality measure.

**The 70% is not a minimum confidence required in one verdict.** It is a historical prediction about the interrogator's accuracy in repeated play. \`summarize_identifications\` reports descriptive correct-identification frequency across completed games; it does not make a statistical inference or certify Turing's prediction from a small sample. **Comparability:** the original test described by Stanford has one human and one machine, while this reversed experiment permits a third `no_human` class. The observed three-class fraction is therefore **not directly comparable** with Turing's 70% prediction; it is only an explicitly labeled historical reference. The game uses 300 seconds as a time **reference**, not an enforced timeout; an overrun is recorded but not silently excluded. Stanford also notes that the parameters of the test can vary independently of that particular prediction.

## What remains testable

- An unauthorized or inactive player cannot covertly borrow computation; nor can H borrow from C.
- A failed or over-budget request cannot mutate credits or a private transcript.
- C and the public observer see exactly the same view before and after a hidden computation, unless one participant later *chooses* to say something about its consequences.
- The original open game, the sealed 24-trial pilot, and the original probabilistic/Brier scoring continue unchanged.
- The visible virtual resources **do not attest real compute theft**, real human/model trials, inference equality, or any result about intelligence.

**No experimental evidence has yet been collected for the covert variant.** Its test fixtures exercise permissions, atomic credit accounting, numerical outputs, and visibility—not the real-world effectiveness of the human's deception.
