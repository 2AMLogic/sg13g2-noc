# Work Plan

Roadmap generated from GitHub label state by the Guide role. Only the region between the markers is machine-generated.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

- **#39**: fix: wire test and check:ci to the router and endpoints benches

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#25**: T1 item 9 (testbenches shipped): mesh-level traffic bench (spec section 5) and a testbench inventory attested with klt signoff --attest 9
- **#26**: T1 item 2 (layout): hierarchical place-and-route of the tile, stepped into the 2 x 2 mesh, committed routed GDS

## Ready

Human-approved issues ready for implementation (`loom:issue`).

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#25**: T1 item 9 (testbenches shipped): mesh-level traffic bench (spec section 5) and a testbench inventory attested with klt signoff --attest 9
- **#26**: T1 item 2 (layout): hierarchical place-and-route of the tile, stepped into the 2 x 2 mesh, committed routed GDS
- **#37**: Replace always-green placeholder check:ci/test scripts in package.json with real verification
- **#40**: Right-size noc_tchk exp_seq table in the mesh build: 4096 flops per checker, ~half the mesh's flops

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#39**: fix: wire test and check:ci to the router and endpoints benches

## Proposed

Issues carrying `loom:curated`.

- **#3**: Track the gap to T1 (klayout-tools design-evidence-tiers.md) *(curated)*
- **#25**: T1 item 9 (testbenches shipped): mesh-level traffic bench (spec section 5) and a testbench inventory attested with klt signoff --attest 9 *(curated)*
- **#26**: T1 item 2 (layout): hierarchical place-and-route of the tile, stepped into the 2 x 2 mesh, committed routed GDS *(curated)*

## Proposed (Architect / Hermit)



_None._

## Epics



_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 1 |
| Very important | 0 |
| Important | 2 |
| Ready (`loom:issue`) | 0 |
| In Progress (`loom:building`) | 4 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 1 |
| Curated | 3 |
| Architect / Hermit proposals | 0 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
