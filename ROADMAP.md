# Roadmap

sg13g2-noc carries a 2 x 2 narrow-link network-on-chip mesh on IHP SG13G2 from
ratified spec to routed, signed-off layout, and files every tool gap it meets
on the way against [klayout-tools](https://github.com/2AMLogic/klayout-tools).

Status as of 2026-11-13, `main` @ `e8967ce`.

`WORK_PLAN.md` is the generated label-state view; this file is the reasoned
plan. The tracker for the whole gap is #3.

## Where it stands

Verdict of record (`manifests/sg13g2-noc.signoff.json`, graded by klt 0.8.0):
**3 of 11 T1 items met, 1 not applicable, 7 unmet.**

| Item | State | Evidence or open issue |
|---|---|---|
| 1 Design sources | met | `manifests/attest/item1.json`; RTL in `rtl/`, mesh netlist `layout/mesh/netlist/noc_mesh.v` (PR #36) |
| 2 Layout | unmet | #26, split into #45 (tile) and #46 (mesh); part a closed (#44) |
| 3 DRC clean | unmet | #27 |
| 4 LVS clean | unmet | #28 |
| 5 Corner verification | unmet | #29; the functional half is recorded (`evidence/item5-functional-verification-mesh-*.json`, PR #67) but not cited in the manifest |
| 6 Monte Carlo | not applicable | `spec/noc.not-applicable.json` (PR #38) |
| 7 Post-layout verification | unmet | #31 |
| 8 Characterization report | unmet | #32 |
| 9 Testbenches shipped | met | `evidence/item9.json` (PR #43) |
| 10 Repo hygiene | met | `evidence/item10.json` (PR #35) |
| 11 Power delivery | unmet | #34 |

On the README's maturity ladder the block is at **mesh verified under traffic**
(simulated RTL). The next rung, tiles placed and routed, has been started and
not finished:

- Spec ratified (`spec/noc.md`, PR #6); decisions 0001 to 0005 in
  `spec/decisions/`, including one tile master with the node id as a port
  (0004, PR #50) and a 1120 um x 1120 um tile (0005, PR #48).
- Router, endpoint loopback and 2 x 2 mesh benches with negative controls, all
  driven by `verification/run.sh` (PRs #21, #20, #43).
- Toolchain smoke through synth, P&R, DRC, LVS and STA on a placeholder counter
  (`layout/smoke/`, PR #8); its tool gaps are filed upstream.
- Tile P&R driver, pin plan and abutment check (`layout/tile/`, PR #54). The
  one tile run finished floorplan, placement and CTS; `route` was still running
  at 1 h 57 min when the session's 2 h cap stopped it. Committed from that run:
  stage metrics and an abutment check of the CTS DEF (280 pin pairs, 0
  problems) in `layout/tile/reports/partial-run/`. No routed GDS or LEF exists.
- klt repinned to 0.9.1 in `layout/tools.json`, new tile synthesis report (PR #78).

## Now

Can start today. Each now has an issue: #90 is in progress, and #95, #96 and
#97 were filed from this list and are still `loom:triage`.

1. **One shared helper for the three cocotb bench drivers** (#90, in progress).
   Done when the endpoints driver can no longer read a stale `results.json`
   and `verification/run.sh all` still passes with every negative control
   tripping.
2. **Decide mesh tile orientation and the cfg/status pin exit before the tile
   is routed again** (#95). `layout/README.md` records that the abutment
   check holds for translation only, so the mirrored placement of decision
   0004 puts an out pin against an out pin; the 2 x 2 needs all four tiles at
   R0 and a new home for the outward pins. Decision 0006 settles it and leaves
   the tile pin plan unchanged, so it does not gate the next multi-hour route;
   what it changes is the `lef-abstract` step after it. Done when
   `spec/decisions/0006-*.md` exists, is listed in `spec/decisions/README.md`,
   and `layout/tile/gen_request.py` plus its generated request match it.
3. **Pre-route timing estimate of the committed mesh netlist at the three
   ratified corners** (#96). The only timing numbers today are a
   synthesis estimate and a post-CTS estimate of +3.0 ns setup slack at 10 ns.
   Done when a `klt sta` request and report for `layout/mesh/netlist/noc_mesh.v`
   at slow, typ and fast are committed, labelled as an estimate without
   routing parasitics and not cited for item 5.
4. **Bring the README status in line with the verdict of record** (#97).
   The status line still says the mesh and synthesis are not done, and the T1
   paragraph says only items 9 and 10 are cited. Done when both agree with
   `manifests/sg13g2-noc.signoff.json` and the `signoff` workflow passes.

## Next

Each is unblocked by a named item above or by one of the blockers below.

- **Routed tile GDS and LEF abstract** (#45). Needs Now item 2, then a run that
  outlasts the `route` stage. Done per its acceptance criteria: 0 route DRC
  violations, utilization and area matching decision 0005, abutment checked
  from the LEF/DEF.
- **Gate-level run of the mesh scoreboard on the committed netlist** (#69).
  Needs the scope ruling under Blocked. Done when `verification/run.sh mesh-gl`
  exits 0, a corrupted-netlist control fails, and the record names the netlist
  sha256.
- **2 x 2 mesh from tile macros, item-2 envelope** (#46, closes #26). Needs #45.
  Done when the manifest cites the mesh GDS and item 2 reads `met`.
- **DRC, LVS and power delivery on the routed tile and mesh** (#27, #28, #34).
  Need #26. Done when each item reads `met`, with DRC deck coverage quoted.
- **STA at the three ratified corners at 100 MHz** (#29). Needs #26. Done when
  item 5 reads `met`, citing the STA reports and the functional envelopes
  already in `evidence/`.

## Later

- **Post-layout simulation and the characterization report** (#31, #32).
  Question first: does the SDF-annotated mesh suite run in Icarus at this
  netlist size in a practical time?
- **Stretch targets in the spec** (4 x 4 mesh, 200 MHz, 64-bit links).
  Question first: has the 2 x 2 closed at 100 MHz post-route?

## Blocked and waiting

- **The tile route cannot finish inside one session** (#45). `route` is a
  single OpenROAD process of more than 2 h on this tile, and
  `klt place-and-route --resume` cannot resume inside it. The upstream issue
  the park cites, klayout-tools#4436, is closed and delivered live route logs,
  not resumability; triage on #45 found no open upstream issue for resuming
  inside `route`. Items 2, 3, 4, 5, 7, 8 and 11 all sit behind this.
- **Scope ruling on #69.** The issue forbids editing `test_mesh.py`, and that
  bench forces an internal net (`u_tgen.dst_id`) that does not exist in the
  netlist. It needs a revision choosing between a bench edit, a new
  port-only test, or a recorded reduction in coverage.
- **Operator decision on #87.** Whether to collapse `.github/klt-version`
  (0.8.0) into `layout/tools.json` (0.9.1), and how the evidence graded under
  0.8.0 is re-issued.

Nothing in the T1 layout chain is dispatchable until the first of these
clears; the Now list is what can move meanwhile.

## Not planned

- Wide links, compute or memory at the endpoints, a processor, clock-domain
  crossings and the pad ring (README, Scope).
- Flat place-and-route of the whole mesh (decision 0003 keeps it hierarchical).
- Relaxing the ratified spec, or hand-editing generated output, to make a
  result pass.
- Measured latency or throughput: simulated until silicon (`measurements/`).
