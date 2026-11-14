# Work Plan

Roadmap generated from GitHub label state by the Guide role. Only the region between the markers is machine-generated.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

- **#45**: T1 item 2 (layout) part b: one-tile place-and-route and LEF abstract
- **#95**: Decision 0006: mesh tile orientation and the cfg/status pin exit, settled before the tile is routed again

## Important

`loom:important`; taken before unlabelled work.

- **#26**: T1 item 2 (layout): hierarchical place-and-route of the tile, stepped into the 2 x 2 mesh, committed routed GDS
- **#46**: T1 item 2 (layout) part c: 2 x 2 mesh from tile macros, mesh GDS, item-2 envelope, signoff
- **#69**: Run the 2x2 mesh scoreboard bench on the committed gate-level netlist (zero delay)
- **#92**: Guard the bench harness against stale results.json false passes with a committed test
- **#96**: Pre-route timing estimate of the committed mesh netlist at the three ratified corners
- **#97**: README status and T1 paragraph disagree with the verdict of record

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#98**: Remove the no-op random.seed(25) and two unused random imports from the cocotb benches
- **#99**: Hoist the duplicated scoreboard vocabulary out of the two endpoint benches: #90 consolidated the drivers and left the test modules drifting

## In Progress

Issues currently being built (`loom:building`).

_None._

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#3**: Track the gap to T1 (klayout-tools design-evidence-tiers.md) *(curated)*
- **#45**: T1 item 2 (layout) part b: one-tile place-and-route and LEF abstract *(curated)*
- **#69**: Run the 2x2 mesh scoreboard bench on the committed gate-level netlist (zero delay) *(curated)*
- **#95**: Decision 0006: mesh tile orientation and the cfg/status pin exit, settled before the tile is routed again *(curated)*

## Proposed (Architect / Hermit)

- **#87**: Remove .github/klt-version: second klayout-tools pin that has drifted from layout/tools.json *(hermit)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 2 |
| Important | 6 |
| Ready (`loom:issue`) | 2 |
| In Progress (`loom:building`) | 0 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 0 |
| Curated | 4 |
| Architect / Hermit proposals | 1 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
