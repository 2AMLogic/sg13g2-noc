# Work Plan

Roadmap generated from GitHub label state by the Guide role. Only the region between the markers is machine-generated.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

- **#45**: T1 item 2 (layout) part b: one-tile place-and-route and LEF abstract *(held)*

## Important

`loom:important`; taken before unlabelled work.

- **#26**: T1 item 2 (layout): hierarchical place-and-route of the tile, stepped into the 2 x 2 mesh, committed routed GDS *(held)*
- **#46**: T1 item 2 (layout) part c: 2 x 2 mesh from tile macros, mesh GDS, item-2 envelope, signoff *(held)*
- **#69**: Run the 2x2 mesh scoreboard bench on the committed gate-level netlist (zero delay) *(held)*

## Ready

Human-approved issues ready for implementation (`loom:issue`).

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#103**: package.json: make npm scripts honest (test -> verification/run.sh all, check:ci fails naming signoff.yml, drop worktree:return)

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#3**: Track the gap to T1 (klayout-tools design-evidence-tiers.md) *(curated)*
- **#45**: T1 item 2 (layout) part b: one-tile place-and-route and LEF abstract *(curated)* *(held)*
- **#69**: Run the 2x2 mesh scoreboard bench on the committed gate-level netlist (zero delay) *(curated)* *(held)*
- **#103**: package.json: make npm scripts honest (test -> verification/run.sh all, check:ci fails naming signoff.yml, drop worktree:return) *(curated)*
- **#120**: The committed mesh netlist predates the pinned klt, so layout/mesh/run.sh --check cannot exit 0: re-pin the mesh evidence at klt 0.9.1 *(curated)* *(held)*

## Proposed (Architect / Hermit)

- **#87**: Remove .github/klt-version: second klayout-tools pin that has drifted from layout/tools.json *(hermit)* *(held)*
- **#107**: Remove the inline JSON-parse step from signoff.yml: a second, already-stale copy of the item-10 attested check *(hermit)* *(held)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 1 |
| Important | 3 |
| Ready (`loom:issue`) | 0 |
| In Progress (`loom:building`) | 1 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 0 |
| Curated | 5 |
| Architect / Hermit proposals | 2 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
