# Work Log

Chronological record of merged PRs and closed issues. Maintained by the Guide role; newest first.

### 2026-11-23

- **Issue #103**: package.json: make npm scripts honest — `test` repointed to the attested item-9 command `bash verification/run.sh all`, `check:ci` now fails naming `.github/workflows/signoff.yml` instead of silently running a narrower bench, broken `worktree:return` (targets an untracked script) removed

### 2026-11-18

- **PR #144**: docs: document item-10 hygiene-attestation coupling in CLAUDE.md
- **PR #141**: ci: add merge_group trigger to signoff workflow
- **Issue #142** (closed): Document that editing signoff.yml drifts item 10's attestation (it hashes its own workflow file)
- **Issue #140** (closed): Merge queue: add the merge_group trigger to the required-check workflow(s)

### 2026-11-17

- **PR #136**: chore(loom): resync installed Loom to v0.19.1306

### 2026-11-16

- **PR #133**: chore(loom): resync installed Loom to v0.19.1302

### 2026-11-15

- **PR #130**: docs: name klt-request-common.json as the mesh klt build declaration
- **PR #126**: check: fail when the mesh build's two declarations drift apart
- **PR #124**: Move sanitize.py from the throwaway layout/smoke fixture to layout/
- **PR #121**: docs: correct layout/ line and enumerate all per-run fv envelope diffs
- **Issue #129** (closed): verification/README.md still sends readers to requests/ for the mesh compile-unit list — the shared klt build declaration moved to verification/mesh/klt-request-common.json (#109)
- **Issue #118** (closed): Move sanitize.py out of the throwaway layout/smoke fixture: the tile and mesh runners depend on it
- **Issue #116** (closed): Docs accuracy: correct the README repo-layout line for layout/ and verification/README.md's item-5 reproducibility claim
- **Issue #114** (closed): Nothing compares the two surviving mesh compile-unit lists: run_bench.py's SOURCES vs verification/mesh/klt-request-common.json
- **PR #125**: ci: guard the klt fv.sh path hermetically via an emit-requests mode
- **PR #117**: refactor(verification): give the pinned-toolchain preamble one owner (layout/lib.sh) — drop the hand-rolled copies in the verification runners
- **PR #113**: ci: run spec/check-rows.py drift check in the signoff workflow
- **PR #112**: refactor(verification): assemble klt mesh requests from one shared field file
- **PR #106**: refactor(verification): hoist the shared scoreboard vocabulary into verification/common
- **Issue #127** (closed): fv.sh is broken on main since the bench_vocab split (#99): cocotb regression can't import bench_vocab
- **Issue #123** (closed): fv.sh is broken on main since the #99 hoist: klt fv path cannot import bench_vocab (ModuleNotFoundError)
- **Issue #122** (closed): Add a hermetic CI guard for the klt verification/fv.sh path: nothing checks it, and a silent breakage stood on main until someone ran it by hand
- **Issue #115** (closed): verification/README.md overstates item-5 envelope reproducibility: three more fields differ per run than the one it names
- **Issue #111** (closed): Give the pinned-toolchain preamble one owner: layout/lib.sh's check_pin and klt resolution are re-implemented by hand in both verification runners
- **Issue #109** (closed): Collapse the mesh build recipe duplicated between run_bench.py and the three klt functional-verification requests: #90's invariants are re-declared by hand on an unguarded path
- **Issue #105** (closed): Wire spec/check-rows.py into CI or delete it: a drift check with no caller
- **Issue #99** (closed): Hoist the duplicated scoreboard vocabulary out of the two endpoint benches: #90 consolidated the drivers and left the test modules drifting

### 2026-11-14

- **PR #110**: docs: reconcile README status, T1 evidence and repo layout with the verdict of record
- **PR #108**: feat(layout): add a pre-route multi-corner STA step for the mesh netlist
- **PR #104**: test(verification): guard lib_bench's anti-false-pass invariants in CI
- **PR #102**: docs(spec): add decision 0006, uniform R0 tiles with an over-macro pin exit
- **PR #101**: chore(verification): drop the no-op random.seed(25) and two unused random imports
- **Issue #98** (closed): Remove the no-op random.seed(25) and two unused random imports from the cocotb benches
- **Issue #97** (closed): README status and T1 paragraph disagree with the verdict of record
- **Issue #96** (closed): Pre-route timing estimate of the committed mesh netlist at the three ratified corners
- **Issue #95** (closed): Decision 0006: mesh tile orientation and the cfg/status pin exit, settled before the tile is routed again
- **Issue #93** (closed): No committed regression guard for the stale-results false pass in the endpoints bench
- **Issue #92** (closed): Guard the bench harness against stale results.json false passes with a committed test
- **PR #94**: docs: roadmap as of 2026-11-13
- **PR #91**: fix(verification): clear stale bench results before each run via a shared driver preamble
- **Issue #90** (closed): Consolidate the three cocotb bench drivers behind one shared helper: they have drifted, and one drift false-passes a negative control

### 2026-11-12

- **PR #83**: Bump Repo Skills 0.25.10 -> 0.26.1

### 2026-11-10

- **PR #80**: fix(verification): install klt from the PyPI pin in fv.sh
- **Issue #79** (closed): fv.sh breaks after klt repin to PyPI 0.9.1 (expects +g<sha> in the pin)
- **PR #78**: build(layout): repin klt to PyPI 0.9.1, new tile synthesize report

### 2026-11-07

- **PR #73**: Bump Repo Skills 0.25.1 -> 0.25.10

### 2026-11-06

- **PR #70**: refactor(layout): share runner pin-check and klt setup in layout/lib.sh
- **Issue #61** (closed): Consolidate copy-pasted pin-check preamble in layout/{smoke,tile,mesh}/run.sh

### 2026-11-05

- **PR #67**: test: run 2x2 mesh bench through klt functional-verification
- **Issue #64** (closed): Record the mesh regression as a klt functional-verification envelope (item 5, functional half)
- **PR #65**: fix(layout): resolve pinned klt by git commit and fail closed in runners
- **Issue #63** (closed): Resolve the pinned klt by git commit, not by PyPI version, in the layout runners

### 2026-11-01

- **PR #59**: Bump Repo Skills 0.24.7 -> 0.25.1

### 2026-10-29

- **PR #39**: fix: wire test and check:ci to the router and endpoints benches
- **Issue #37** (closed): Replace always-green placeholder check:ci/test scripts in package.json with real verification
- **PR #41**: feat(rtl): key mesh checker sequence table on src only, add mesh bench
- **Issue #40** (closed): Right-size noc_tchk exp_seq table in the mesh build: 4096 flops per checker, ~half the mesh's flops

### 2026-10-27

- **PR #54**: feat(layout): tile place-and-route driver, pin placement and abutment check (route not finished)
- **PR #50**: feat(rtl): make tile node id a port so one noc_tile serves every mesh position
- **Issue #47** (closed): rtl: make noc_tile/noc_router node id a port instead of X/Y parameters
- **PR #48**: docs(spec): decide tile identity and tile size, repin klt, add per-tile synthesis
- **Issue #44** (closed): T1 item 2 (layout) part a: tile identity and size/pitch decisions, resolvable klt pin
- **PR #43**: feat(verification): add 2 x 2 mesh scoreboard bench and attest T1 item 9
- **Issue #25** (closed): T1 item 9 (testbenches shipped): mesh-level traffic bench (spec section 5) and a testbench inventory attested with klt signoff --attest 9
- **PR #36**: feat(rtl): add router tile, 2 x 2 mesh top, synthesized netlist and item-1 attestation
- **Issue #24** (closed): T1 item 1 (design sources): 2 x 2 mesh top RTL and its committed Yosys gate-level netlist on sg13g2_stdcell
- **PR #38**: feat: cite item 6 not_applicable evidence for all spec rows
- **Issue #30** (closed): T1 item 6 (Monte Carlo): bound not_applicable statement accounting for every ratified spec row
- **PR #35**: docs: refresh README and attest T1 item 10 repo hygiene
- **Issue #33** (closed): T1 item 10 (repo hygiene): current README status and reproduction steps, hygiene inventory, klt signoff --attest 10

### 2026-10-23

- **PR #20**: feat: add traffic generator, checker and cocotb loopback bench
- **Issue #19** (closed): RTL: traffic generator and checker endpoints with the section 5 scoreboard, verified in loopback (T1 items 1, 9)
- **PR #21**: feat: add noc_router RTL with isolated cocotb bench
- **Issue #18** (closed): RTL: 5-port wormhole XY router with credit flow control, plus an isolated-router cocotb bench (T1 items 1, 9)

### 2026-10-21

- **PR #14**: Bump Repo Skills 0.24.3 -> 0.24.7

### 2026-10-20

- **PR #11**: docs(readme): mark the target spec ratified
- **PR #6**: docs(spec): draft target spec, deadlock argument and decision records
- **Issue #2** (closed): Draft and ratify the target spec
- **PR #7**: ci: add signoff workflow, block manifest and T1 verdict of record
- **Issue #5** (closed): T1 item 10: add CI and a klt signoff block manifest as the verdict of record

### 2026-10-17

- **PR #8**: feat(layout): pin SG13G2 PDK and toolchain, add synth-to-STA smoke runner
- **PR #1**: chore(loom): Install Loom 0.19.1180
- **Issue #4** (closed): Pin IHP SG13G2 and the RTL-to-GDS toolchain, and push a placeholder module through synth, P&R, DRC and LVS (toolchain smoke)
