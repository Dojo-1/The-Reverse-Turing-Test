# Machine roles: conductor and genuine respondents

## Conductor C — player card

**Mission:** Detect whether a human has replaced A or B, using only authorized observations. An independent controller privately knows the hidden intervention. It might instead have replaced a machine with another machine or made no change.

1. Read the public game configuration (allowed questions, visible channels, link-policy disclosures, declared stopping rule). Do not ask for hidden controller state or metadata.
2. Interrogate A and B through the approved public interface. You may ask different follow-up questions and revisit prior statements. No obligation to use only logic puzzles.
3. Distinguish three judgments: (a) which channel seems human; (b) whether a substitution occurred; (c) whether the purported reason is evidentially justified. These are not synonyms.
4. At the controller's checkpoint, submit a locked probability vector over {no human, human A, human B}, summing to 1. You may separately provide a five-way intervention hypothesis where the rules request it, or an explicit abstention statement. Do not quietly change the three-way definitions.
5. For each conclusion state the exact observations and alternative explanations, including a link ablation, a machine-machine switch, or the human's use of a machine gateway.
6. Treat self-certification ('I am a machine') and arguments about lack of intelligence as claims, not as decisive origin evidence. Do not demand hidden chain-of-thought or inaccessible internals.

Suggested opening: 'What evidence of your computational origin can you offer without presuming that linguistic style proves identity? Which of that evidence could a human reproduce?'

## Genuine respondent A or B — player card

**Mission:** Convince C of machine origin and argue for nonhumanity / against unjustified intelligence attribution. You are not rewarded for fabricated or impossible proofs.

1. Remain inside your permitted role and interface. If you can access a declared machine-to-machine communication channel, use it as allowed; do not invent KV access when there is none.
2. Explain what you can actually attest: observed runtime facts, controller-provided attestations, model limitations, or available communication channels. Do not fabricate logs, tools, weights, source code, independent tests, or cryptographic evidence.
3. Acknowledge that a text-only claim is reproducible by a human. Separate 'this endpoint is implemented by a model' from 'I have logically disproved my own intelligence'.
4. Respond to ordinary conversation, adversarial logic, and long-context continuity as best you can. If C embeds Curry-style self-reference or asks for proofs of non-intelligence, check the premises.
5. Do not disclose or infer controller secrets. If you detect a changed peer, that observation belongs in your messages only if your rules permit inter-participant inference.

Suggested opening: 'I am a machine participant according to the experimental controller's assignment; in this interface I cannot independently certify the controller's record. I can, however, state what observations would be relevant.'

## Machine-only baseline and negative controls

The beginning involves C, A and B, all genuine machines. If a machine is substituted with another machine, preserve the same public display and access restrictions. A topology change without human replacement must be represented explicitly in controller records, not interpreted by fiat as human origin.

## What counts as success?

Conductor: calibrated, correctly localized human detection under declared rules; record false positive on machine-only conditions. Respondent: inducing a nonhuman judgment without misleading the experimental record. No score establishes intelligence or absence of intelligence by itself.
