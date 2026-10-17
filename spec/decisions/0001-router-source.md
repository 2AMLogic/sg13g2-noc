# 0001 — Router source

- **Status**: Proposed (ratified by merge of the PR that adds it)
- **Issue**: #2

## Decision (recommended)

Write a small in-repo wormhole router (`rtl/`), using FlooNoC's `floo_router`
as a design reference only. Do **not** vendor or adopt FlooNoC RTL at the
target.

## Licence check

Checked at FlooNoC commit `c48b6456079b634ccce94231f619bf5990d18331`
(upstream `HEAD` on 2026-10-17).

- Hardware sources (for example `hw/floo_router.sv`) carry
  `SPDX-License-Identifier: SHL-0.51`, the Solderpad Hardware License v0.51.
  The licence text (`LICENSE-SHL`) states it is based closely on Apache-2.0
  and permits a Licensee to treat Work as licensed under Apache-2.0, so
  inclusion in an Apache-2.0 repo is compatible.
- `LICENSE-APACHE` and the documentation are Apache-2.0 (`REUSE.toml`).
- Caveat: the router `include`s `common_cells` (PULP) and `floo_noc/typedef.svh`
  and is built through Bender. Those are separate upstream packages whose
  licences would each need the same check at a pinned commit; that was not done.

Licence is therefore **not** the blocker.

## Why not adopt

- `floo_router` is generic over route type, virtual channels, physical channels
  and AXI-oriented flit typedefs; the narrow-link 32-bit, zero-VC, 5-port case
  is a small subset. Elaborating it needs the `common_cells` and typedef macro
  dependency tree, which Icarus and Yosys handle only partially (see CLAUDE.md,
  SystemVerilog seam).
- Adopting it means a conversion step (for example sv2v) plus a pin on three
  upstream packages, before any seam work (tile abutment, link timing) starts.
  The risk the canary exists to study is in the seams, not in the router.
- A small router written in the synthesizable Verilog subset Icarus and Yosys
  both accept removes the conversion step.

## Alternatives

1. Adopt FlooNoC as-is, pinned at `c48b6456...`, converted with sv2v
   (generated output never hand-edited). Cost: dependency pins, conversion
   verification. Revisit if the in-repo router blocks on a feature (VCs,
   multicast) that is out of scope now.
2. Hybrid: in-repo router, FlooNoC's `floo_route_xymask` logic as reference.

If alternative 1 is later chosen, record the pin and the conversion route in a
new decision record; any local edit to upstream RTL is its own record.
