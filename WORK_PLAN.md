# Work Plan

Roadmap generated from GitHub label state by the Guide role. Only the region between the markers is machine-generated.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

- **#45**: T1 item 2 (layout) part b: one-tile place-and-route and LEF abstract

## Important

`loom:important`; taken before unlabelled work.

- **#26**: T1 item 2 (layout): hierarchical place-and-route of the tile, stepped into the 2 x 2 mesh, committed routed GDS
- **#46**: T1 item 2 (layout) part c: 2 x 2 mesh from tile macros, mesh GDS, item-2 envelope, signoff
- **#69**: Run the 2x2 mesh scoreboard bench on the committed gate-level netlist (zero delay)

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#118**: Move sanitize.py out of the throwaway layout/smoke fixture: the tile and mesh runners depend on it

## In Progress

Issues currently being built (`loom:building`).

- **#99**: Hoist the duplicated scoreboard vocabulary out of the two endpoint benches: #90 consolidated the drivers and left the test modules drifting
- **#105**: Wire spec/check-rows.py into CI or delete it: a drift check with no caller
- **#109**: Collapse the mesh build recipe duplicated between run_bench.py and the three klt functional-verification requests: #90's invariants are re-declared by hand on an unguarded path
- **#111**: Give the pinned-toolchain preamble one owner: layout/lib.sh's check_pin and klt resolution are re-implemented by hand in both verification runners

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#113**: ci: run spec/check-rows.py drift check in the signoff workflow

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#106**: refactor(verification): hoist the shared scoreboard vocabulary into verification/common
- **#112**: refactor(verification): assemble klt mesh requests from one shared field file

## Proposed

Issues carrying `loom:curated`.

- **#3**: Track the gap to T1 (klayout-tools design-evidence-tiers.md) *(curated)*
- **#45**: T1 item 2 (layout) part b: one-tile place-and-route and LEF abstract *(curated)*
- **#69**: Run the 2x2 mesh scoreboard bench on the committed gate-level netlist (zero delay) *(curated)*

## Proposed (Architect / Hermit)

- **#87**: Remove .github/klt-version: second klayout-tools pin that has drifted from layout/tools.json *(hermit)*
- **#103**: Remove package.json: a node stub whose three scripts are broken or a drifted third test entry point *(hermit)*
- **#107**: Remove the inline JSON-parse step from signoff.yml: a second, already-stale copy of the item-10 attested check *(hermit)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 1 |
| Important | 3 |
| Ready (`loom:issue`) | 1 |
| In Progress (`loom:building`) | 4 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 2 |
| Curated | 3 |
| Architect / Hermit proposals | 3 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
