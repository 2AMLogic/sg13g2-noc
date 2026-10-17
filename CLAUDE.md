# sg13g2-noc — agent instructions

Open-source canary block: a narrow-link network-on-chip mesh on IHP SG13G2,
designed and verified by AI agents. **Digital.**

- **PDK**: IHP SG13G2 (open PDK, IHP-GmbH/IHP-Open-PDK), standard cells
  `sg13g2_stdcell`. Digital flow: cocotb + Icarus for simulation, Yosys for
  synthesis, OpenROAD for place-and-route and timing. Layout, DRC, and LVS
  through klayout-tools (`klt`). The SG13G2 DRC/LVS deck in klayout-tools is
  starter-grade; a rule it cannot check yet is a deck gap to file, not
  something to route around.
- **The seams between tiles are the point, and the risk.** Build one router
  tile, verify it, then step and repeat it. Link timing across tile
  boundaries, abutment, and hierarchical place-and-route are where the tools
  will be weakest. A mesh assembled from an unverified tile is not progress.
- **Correctness is a scoreboard, not a waveform.** Every flit injected is
  accounted for at its destination: no loss, no duplication, in order per
  source–destination pair. Deadlock freedom comes from the routing
  algorithm and is argued in `spec/`, then tested under adversarial traffic.
  Latency and throughput are quoted only with the traffic pattern and
  injection rate that produced them, and are simulated, never measured,
  until silicon.
- **Scope discipline.** Narrow links only; no wide links, no compute or
  memory at the endpoints, no processor, no clock-domain crossings at the
  target. Third-party router RTL (FlooNoC) is pinned to an upstream commit if
  adopted; local edits to it are decision records.
- **SystemVerilog is a known seam.** FlooNoC is SystemVerilog, and Icarus'
  and Yosys' support for it is partial. Expect a conversion step (for
  example sv2v) or a recorded alternative; generated output is never
  hand-edited.
- **Friction protocol (the canary's job)**: every time klayout-tools is
  awkward, missing a capability, or wrong for what you need, file an issue at
  `2AMLogic/klayout-tools` describing the tool gap generically — that tracker
  is scoped to the tool, so keep design-specific detail out of it and describe
  the gap, not the design.
- **Verification is the product**: no claim without a testbench. Recorded
  results are append-only evidence.
- Spec changes go through `spec/` with a decision record; agents do not relax
  the ratified spec to make results pass.
- **A 2 x 2 mesh at 100 MHz post-route is the target.** A single router with
  two endpoints at 50 MHz is the fallback and a 4 x 4 mesh at 200 MHz is a
  stretch. Do not grow the mesh before the 2 x 2 closes.

<!-- BEGIN LOOM ORCHESTRATION -->
This repository uses [Loom](https://github.com/rjwalters/loom) for AI-powered development orchestration — see the Loom repository for the full guide (roles, labels, worktrees, configuration). When installed, Loom also writes a locally-substituted copy of that guide to `.loom/CLAUDE.md`.

Work is coordinated through `loom:` labels on issues and pull requests, and the same roles run either under `loom-daemon` or by hand in an attended session — daemon mode is optional. Create the labels once with `.loom/scripts/sync-labels.sh` (an install ships `.github/labels.yml` but does not create the labels on the forge). A pull request ready for review carries `loom:review-requested`; Judge reviews it and applies `loom:pr` (approved) or `loom:changes-requested`; Doctor fixes a `loom:changes-requested` pull request and returns it to `loom:review-requested`. Only a `loom:pr` pull request gets merged, and always via this repo's merge script (`.loom/scripts/merge-pr.sh`) — never a raw forge merge command such as `gh pr merge`. Full state machine: `.loom/docs/label-state-machine.md`.
<!-- END LOOM ORCHESTRATION -->
