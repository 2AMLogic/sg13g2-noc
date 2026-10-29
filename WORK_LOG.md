# Work Log

Chronological record of merged PRs and closed issues. Maintained by the Guide role; newest first.

### 2026-10-29

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
