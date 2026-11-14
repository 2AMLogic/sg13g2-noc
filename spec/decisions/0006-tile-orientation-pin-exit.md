# 0006 — Tile orientation and the cfg/status pin exit

- **Status**: Proposed (reviewer to confirm at PR review)
- **Issue**: #95
- **Supersedes in part**: the mirrored-orientation sentence of
  [0004](0004-tile-identity.md) ("cfg / status pins", the sentence beginning
  "Placing the four copies with mirrored orientations (R0, MY, MX, R180 …)").
  0004 is otherwise unchanged and gets a pointer line; 0003 and 0005 are not
  edited.
- **Consumed by**: #45 (the tile's `klt lef-abstract` flags) and #46 (the mesh
  placement and the top-level routing). See "Which issue this settles".

## Problem

0004 places the four tile copies at R0, MY, MX and R180 so that the one
cfg/status band faces outward on every copy. `layout/README.md` records that
this does not work: the committed abutment check passes for translation
placement only, and under mirroring the same edge of two copies meets, so an
out pin would face an out pin. 0004 names feedthrough routing over the macros
as the fallback and defers it to a new record. This is that record.

The tile `route` stage is a single OpenROAD process of more than 2 h and
`klt place-and-route --resume` cannot resume inside it, so anything that
changes the tile's pin plan has to be settled before the next attempt.

## Decision

1. **All four tile copies are placed at R0** — uniform orientation, pure
   translation, no mirror and no rotation.
2. **The cfg/status band stays exactly as built**: one unordered band holding
   all 212 non-link pins on the **west** edge over `range_um [200.0, 1100.0]`.
   `layout/tile/gen_request.py` and `layout/tile/requests/place-and-route.json`
   already satisfy this decision and are unchanged by it.
3. At R0 the west edge is on the mesh boundary for the x=0 column (tiles (0,0)
   and (0,1)) and is an **interior** edge for the x=1 column (tiles (1,0) and
   (1,1)). For those two tiles the band **exits by top-level routing over the
   macro** — 0004's named fallback.
4. The tile abstract must therefore be generated with
   **`klt lef-abstract --obs-mode detailed`** (not `coarse`) and with
   **`--symmetry` omitted**, so the LEF emits no `SYMMETRY` statement.

## Why orientation cannot solve the pin exit

This is the part 0004 got wrong, and the reason is stronger than the pin-plan
argument in `layout/README.md`: **no orientation of any kind can put a
single-edge band outward on all four copies of a mesh tile.**

`rtl/noc_mesh.v` wires port `d` of one tile to port `(d+2)%4` of its
neighbour — e.g. lines 81-84, `t_iv[1][3] = t_ov[0][1]`: tile 1's **west**
input (d=3) is driven by tile 0's **east** output (d=1). Abutment with no
channel means the two tiles' facing edges are physically coincident, so the
placement must bring tile 0's local east edge against tile 1's local west
edge. Only pure translation does that: any transform that maps a copy's local
west edge to its global **east** side (MY, R180, and every R90 variant) also
maps local east to global west, so the seam then joins **same-index** edges —
out against out, and `(d+2)%4` is violated.

But making the local-west band face outward on the x=1 column is exactly the
requirement "map local west to global east". The two requirements are
contradictory, so the x-flip parity must be equal across the X seam; the same
argument in y forces equal y-flip parity across the Y seam. All four copies
therefore carry the same orientation, which for a square tile is R0 up to a
global transform of the whole mesh.

Two consequences worth stating plainly:

- The mirrored plan of 0004 is not merely awkward with the pin plan that was
  built — it is **not reconstructible by any pin plan** while the mesh keeps
  directional ports. A mirror-symmetric link pin plan (out at slot *i*, in at
  slot *N-1-i*) fixes the *coordinates* across a mirrored seam but not the
  *port indices*, so it does not rescue the option.
- Correspondingly, "all four at R0" does **not** by itself produce an outward
  pin exit. One master means one pin plan, and a given edge is on the mesh
  boundary for only two of the four copies, whichever edge is chosen. The exit
  mechanism has to be named separately, which is item 3 above.

## Evidence

**Abutment (translation).** `layout/tile/reports/partial-run/abut-check-cts-def.txt`
— "abutment pairs checked: 280; problems: 0", from the CTS DEF of the one
partial tile run. This establishes the precondition the all-R0 placement
depends on: the tile's own link pin plan is translation-abuttable.

`layout/tile/check_abut.py` **models translation only** — it takes one tile's
pin list and no orientation input, and asserts that `out`/`in` of the same role
on edges `d` and `(d+2)%4` share a coordinate and layer — so its verdict is
invariant to the orientation and is not evidence for or against this decision.
No new abutment number is claimed here; a fresh run is not producible without
the >2 h `route` stage, and would not test this decision if it were.

**Mirror permission.** `layout/tile/run.sh` passes no `--symmetry`, which the
pinned `klt lef-abstract` documents as "omit to emit no SYMMETRY statement", so
the macro carries no mirror permission for OpenROAD today. This is consistent
with the decision, but it is a flag setting rather than a physical constraint,
and is not load-bearing for the argument above.

**Obstruction mode.** At the pinned `klayout-tools==0.9.1`,
`klt lef-abstract --obs-mode` documents `coarse` as "one bounding rectangle per
routing layer minus the declared pin ports, bounding the LEF size to O(pins)"
and `detailed` (the default) as "every merged routing-layer region". `coarse`
obstructs every routing layer across the whole macro, so feedthrough over the
tile is not routable against an abstract built that way. `run.sh` passes
`--obs-mode coarse` today; item 4 changes that in #45.

**Feedthrough budget** (static, computed from the PDK tech LEF and the
`sg13g2` power preset — **not** a measurement, and not a claim that the route
will close):

| | |
|---|---|
| Nets crossing one macro, per interior tile | 212 — the whole band: 165 status outputs, 43 shared `clk`/`rst_n`/`cfg_*` inputs, and 4 `my_x`/`my_y` bits whose tie cells also sit outside the macro envelope |
| Crossing distance | 1120 um (one full tile width) |
| PDN layers, preset `sg13g2` | Metal1 followpins, TopMetal1 straps (pitch 3.28 um), TopMetal2 straps (pitch 4.0 um) — unavailable for feedthrough |
| Horizontal layers available | Metal3 and Metal5, pitch 0.42 um -> 2666 tracks each over a 1120 um edge, 5332 total |
| Vertical layers for jogs | Metal2 and Metal4, pitch 0.48 um |
| Demand against that nominal supply | 212 / 5332 = **4.0 %** |
| Tile's own routing | about 1.79e6 um estimated wire (post-CTS global route) over about 1.1e7 um of Metal2-Metal5 track length — roughly **16 %** average occupancy |

The nominal headroom is therefore about an order of magnitude. **The risk is
fragmentation and via congestion, not raw track supply**: with `detailed`
obstructions the free area is the complement of the tile's own distributed
routing, so a crossing net will jog between layers rather than run one clear
track end to end. Confirming it is #46's job, against the abstract #45 emits.

The table above is a hand calculation from the tech LEF's layer pitches
because the tool cannot report it: `klt lef-abstract` takes one whole-macro
`--obs-mode` and its response carries only `obs_mode`, `obs_shape_count` and
`pin_count` — no per-layer obstructed fraction and no free-track count, and no
way to ask for `coarse` on the power-strap layers and `detailed` on the one
signal layer a crossing needs. Filed as 2AMLogic/klayout-tools#5677. Until
that lands, this budget stays an estimate from layer pitches rather than a
figure read off the abstract.

**Mesh floorplan consequence.** `layout/mesh/netlist/noc_mesh.v` instantiates
**471 standard cells** in the mesh top alongside the four macros — 467
`sg13g2_tielo` and 4 `sg13g2_tiehi`, 7.2576 um^2 each, 3419 um^2 total. All
471 drive constant inputs of the four tile instances (296 wired directly in
the instance port lists, 175 through the intermediate `t_*` link wires): the
280 dangling outer-edge link input bits and the 16 `my_x`/`my_y` node-id bits.
Yosys emits one tie cell per constant net rather than sharing them, so the
cell count exceeds the 296 distinct constant bits. A die of exactly
2240 um x 2240 um fully covered by four abutting macros has no site rows to
place any of them in. The mesh die must therefore be larger than the
2240 um macro envelope, with a peripheral ring that also carries the 703 mesh
signal pins and the top-level routing. Sizing that ring is #46's, not this
record's; decision 0005's 1120 um **pitch** is unaffected, because the links
still abut.

## Alternatives

- **Mirrored placement (0004) with a mirror-symmetric link pin plan** — out at
  slot *i*, in at slot *N-1-i*, so a mirror maps out onto in. Rejected: it
  fixes coordinates but not port indices, so the seam still joins `d` to `d`
  where the mesh RTL needs `d` to `(d+2)%4`. Not rescuable by any pin plan.
- **Move the band to a different single edge.** Rejected: one master means one
  pin plan, and every edge is on the mesh boundary for exactly two of the four
  copies.
- **Split the band across two edges.** Rejected: each copy then gets the same
  two edges, and in a 2 x 2 each copy still has one of them interior.
- **Confine the band to a corner** so interior-band nets exit through the
  nearer perpendicular boundary. Rejected: it shortens the crossing for one of
  the two interior tiles only — tile (1,1)'s band would still be at least
  920 um from any boundary — and it costs a pin-plan change and a re-route for
  half a benefit.
- **A routing channel between tiles**, 0003's named fallback. Rejected: 0003
  holds it for an abutment DRC/LVS failure, not for pin-exit convenience, and
  spending it here would discard hierarchical abutment, which is the property
  this canary exists to test (CLAUDE.md, "the seams between tiles are the
  point").
- **Route cfg/status out through the dangling outer-edge link pins.** Not
  viable: those are the ratified link interface of 0003, driven by the router;
  repurposing them is a spec change.
- **Reduce the mesh-level pin count** (a status mux or scan chain). Out of
  scope in 0004 and here, and spec-visible.

## Which issue this settles

`layout/README.md` attached this question to #46 and `ROADMAP.md` attached it
to #45. Both are partly right, and the split is:

- **#45 (tile)** implements item 4 — `layout/tile/run.sh` changes
  `--obs-mode coarse` to `--obs-mode detailed` and keeps `--symmetry` omitted.
- **#46 (mesh)** implements items 1 and 3 — uniform R0 placement, the
  top-level feedthrough for the two x=1 tiles, and a die larger than the
  2240 um macro envelope.

**This record does not gate #45's `route` stage.** Item 2 leaves the pin plan
unchanged, so the next route attempt starts from the committed
`layout/tile/requests/place-and-route.json` as it stands; only the
post-`route` `lef-abstract` step changes. The premise that the orientation
question would change the tile's pin plan — stated in `ROADMAP.md` and implied
by this issue — is refuted by this decision.

## Out of scope

Running the tile `route` stage (#45) or the mesh place-and-route (#46); editing
`layout/tile/run.sh` (its flags are only observable in a LEF, which is produced
after the excluded `route` stage); adding an orientation model to
`check_abut.py` (only the rejected mirrored option would need one); any RTL
change; any timing, area or utilization claim; and any change to `spec/noc.md`.
