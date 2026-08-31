# Tutorials

Four narrative walkthroughs, difficulty-tiered, each self-contained but building on the one
before it. If [Getting started](../getting-started.md) is a five-minute install-and-first-solve,
these are the fifteen-to-twenty-minute-each story of what the package actually does and why —
prose-heavy, with the "why" explained alongside the "what," rather than the terse
one-concept-per-script style of the [examples](../examples/index.md).

| Notebook | Difficulty | What it covers |
| --- | --- | --- |
| [1. Your first power flow](01-first-power-flow.ipynb) | Beginner | Load a MATPOWER case, run `pf.solve_dc` and `pf.solve_ac`, read bus voltages and branch flows |
| [2. DC-OPF and N-1 screening](02-dc-opf-and-n1.ipynb) | Intermediate | `opf.solve_dc_opf` for cost-minimising dispatch and LMPs, `contingency.n1` for branch-outage screening |
| [3. A nodal market](03-nodal-market.ipynb) | Intermediate | `market.solve_nodal` with elastic demand, LMP congestion splits, and settlement |
| [4. Where next](04-where-next.ipynb) | Guided fork | `market.agents` (strategic bidding) and `io.*` (interchange formats) — pick your own next stop |

## The arc

Each tutorial answers a progressively harder question about the same kind of network:

1. **What's happening right now**, given a dispatch someone else already chose (a plain power
   flow)?
2. **What *should* happen**, if a single planner is free to choose the cheapest dispatch, and is
   that dispatch still safe if any one branch trips?
3. **What happens when participants get to bid** — offers and elastic demand, cleared at a price
   with real settlement, rather than one planner minimising cost?
4. **Where does the story go from here** — two independent directions, strategic bidding and
   real-world interchange formats, so you can pick whichever matches what you're actually
   building.

Every code cell in every notebook actually runs — they're executed fresh in CI on every push
([nbmake](https://github.com/treebeardtech/nbmake)), so the numbers you see rendered here are
the real ones, not hand-typed illustrations.

Prefer a faster, terser reference once the narrative isn't needed anymore? See
[Examples](../examples/index.md) (thirteen short scripts, one concept each) or the
[Manual](../manual/model.md) (the full class-by-class and module-by-module reference).
