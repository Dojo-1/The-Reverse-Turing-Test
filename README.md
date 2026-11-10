# The Reverse Turing Test

**Three machines enter the game. One of the respondents may later become human. Can the machine conductor tell?**

Turing asked whether a machine could pass for a human. We reverse the asymmetry: machine C interrogates two initially genuine machines A and B; an independent controller may secretly replace either respondent with a human. The human's assignment is to **pass for a machine**. The genuine machines attempt to establish their machinehood while arguing against attributing humanity or intelligence to themselves—without confusing an assertion with proof.

And then comes Turing's peculiar *telepathy-proof room*: what if machines can exchange internal state through a communication channel that the human impersonator cannot use? The game allows directed information edges, including optional simulation of a private side channel and a future *verified* KV-cache handoff. It never equates ordinary shared text with an actual KV transfer.

## Play

- [Run a manual game / facilitator handbook](docs/HOST_AND_PLAY.md)
- [Human impersonator: player instructions](docs/HUMAN_PLAYER.md)
- [Machine conductor and respondents: player instructions](docs/MACHINE_PLAYERS.md)

No API keys, LLM backends or working KV translator are bundled. Manual play requires isolated chat sessions and an independent controller. Every specific trial precommits its own information topology, optional interventions, stopping rule and verdict mechanism. The *family* of games remains deliberately open: no mandatory five-minute limit or universal winning threshold.

## Mathematics and Lean

- [Mathematical specification, Bayes classifier, side-channel confounding and game theory](docs/MATHEMATICS.md)
- [Finite structural protocol from R0](docs/GAME.md)
- [Status ledger: what is proved, derived and merely hypothesized](docs/CLAIMS.md)
- [SwaT paper and factual boundary](docs/SWAT_SCOPE.md)

Lean 4 + Lake, toolchain pinned to `v4.35.0`, dependency-free `Init` only:

```sh
lake build
```

Proof modules: `ReverseTuring/Core.lean` (observable collisions and deterministic adaptation), `ReverseTuring/Topology.lean` (directed information graph, label covariance, connectivity confounding), and `ReverseTuring/Bayes.lean` (finite weighted classification upper bound).

A green build checks Lean propositions within their formal assumptions. It does **not** prove that a given human can imitate any particular LLM, that a KV translator actually works, or that humans/machines possess or lack intelligence.

## Research principle

**Origin is not information access. Information access is not intelligence.** Treat each separately, preserve controls, and let experiment rather than rhetoric decide.

Inspiration: Alan Turing (1950); [Stanford Encyclopedia of Philosophy: The Turing Test](https://plato.stanford.edu/entries/turing-test/); [Alabdulkareem et al., *Swarm Telepathy*, arXiv:2610.15095](https://arxiv.org/abs/2610.15095).

The core Reverse Turing Game and the concealed human substitution are user-originated research proposals. Formal lemmas, documentation and experimental extensions are AI-assisted contributions requiring independent inspection and review.
