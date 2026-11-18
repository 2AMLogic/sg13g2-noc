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

- **#140**: Merge queue: add the merge_group trigger to the required-check workflow(s)
- **#142**: Document that editing signoff.yml drifts item 10's attestation (it hashes its own workflow file)

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#141**: ci: add merge_group trigger to signoff workflow

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#3**: Track the gap to T1 (klayout-tools design-evidence-tiers.md) *(curated)*
- **#45**: T1 item 2 (layout) part b: one-tile place-and-route and LEF abstract *(curated)* *(held)*
- **#69**: Run the 2x2 mesh scoreboard bench on the committed gate-level netlist (zero delay) *(curated)* *(held)*
- **#120**: The committed mesh netlist predates the pinned klt, so layout/mesh/run.sh --check cannot exit 0: re-pin the mesh evidence at klt 0.9.1 *(curated)* *(held)*
- **#140**: Merge queue: add the merge_group trigger to the required-check workflow(s) *(curated)*
- **#142**: Document that editing signoff.yml drifts item 10's attestation (it hashes its own workflow file) *(curated)*

## Proposed (Architect / Hermit)

- **#87**: Remove .github/klt-version: second klayout-tools pin that has drifted from layout/tools.json *(hermit)* *(held)*
- **#103**: Remove package.json: a node stub whose three scripts are broken or a drifted third test entry point *(hermit)* *(held)*
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
| In Progress (`loom:building`) | 2 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 0 |
| Curated | 6 |
| Architect / Hermit proposals | 3 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
