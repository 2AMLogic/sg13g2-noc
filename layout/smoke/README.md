# layout/smoke: toolchain smoke fixture

**This is not design.** `counter.v` is a throwaway 8-bit counter with a registered output. It exists only to prove that the RTL-to-GDS chain runs on IHP SG13G2 `sg13g2_stdcell` before any router RTL exists. It decides nothing about routers, flits, links, corners or the mesh, and it is excluded from any design-source inventory. Nothing under `spec/` depends on it.

## Run it

```
layout/smoke/run.sh
```

From a clean clone with the documented installs: `yosys` and `openroad` on `PATH` at the versions in [`../tools.json`](../tools.json), `uvx`, `jq`, `python3`, and the IHP-Open-PDK pinned in [`../pdk.json`](../pdk.json) under `$PDK_ROOT/ihp-sg13g2` (default `~/share/pdk`). `klt` is fetched pinned with `uvx --from "klayout-tools==<version>"`; nothing is installed. The runner refuses to run if a pin does not match, runs `synthesize`, `place-and-route`, `drc`, `extract`, `lvs` and `sta` in order, stops at the first failing step but keeps that step's envelope, rewrites absolute host paths to repo-relative ones (`sanitize.py`, prefix substitution only), then runs `klt env-provenance lint-envelope` on the result. Every step is a single unit; there is no shell fan-out.

Envelopes are in [`reports/`](reports/). The two re-runs I compared differed only in OpenROAD `invocation_id` values and the log paths built from them.

## Results (klt 0.7.1.dev1755+gdce956c3c399, OpenROAD 26Q3-1510-g6cb3f2b704, Yosys 0.67+post, IHP-Open-PDK v0.3.0)

| Step | Report | Result |
|---|---|---|
| `klt synthesize` | `reports/synthesize.json` | `ok`, 30 cells, 948.93 um^2 |
| `klt place-and-route` (`power.preset: sg13g2`, `target_stage: route`) | `reports/place-and-route.json` | `ok`, reached `route`; `route_drc_violation_count` 0, `antenna_violation_count` 0, setup/hold violations 0 |
| `klt drc --deck sg13g2` on the merged GDS | `reports/drc.json` | `clean`, 0 violations |
| `klt lvs` (gate-level Verilog reference, as-built `verilog_path`) | `reports/lvs.json` | `status: match`, `power_connectivity.status: match` |
| `klt sta` (DEF, six liberty corners) | `reports/sta.json` | `ok`, all six corners met 10 ns, ideal clock |

`power.tapcell_master` is `null` and `power.endcap_master` is `null`: `sg13g2_stdcell` ships no tap or endcap cells, so `klt place-and-route` skips the tapcell step. The PDN is real: `power.pdn` is `true`, `power.placed.status` is `complete`, with 340 placed components, 0 tapcells, 0 endcaps and 305 fillers (`sg13g2_fill_1`, `sg13g2_fill_2`).

### DRC coverage, quoted from `reports/drc.json` (`coverage`)

```
layers_in_stream_without_rules: ["8/2","8/25","14/0","30/2","30/25","31/0","134/2","134/25","189/4"]
rules_skipped: ["metal5.enclosing.mim.1","mim.enclosing.topvia1.1"]
deck_scope: ["Act","Cnt","Gat","M1","M2","M3","M4","M5","MIM","TM1","TM2","TV1","TV2","V1","V2","V3","V4"]
```

Reading them: `rules_skipped` lists two MIM rules; `coverage.inapplicable` gives the reason `no_applicable_geometry` for both and `coverage.skipped` is empty, so they were not run because the layout has no MIM. Nine stream layer/datatype pairs have no rule in the deck. 8/2, 8/25, 30/2, 30/25, 134/2, 134/25 and 189/4 are, per the PDK's `sg13g2.map`, pin, name and cell-boundary/die-area purposes. 14/0 and 31/0 were not identified. `clean` therefore means "clean against `deck_scope`", which stops at the layers listed; it says nothing about the other 9 pairs. Whether this deck covers a standard-cell tile is an open question for the spec (#2), not answered here.

### LVS notes

`lvs.json` carries two warnings: `topology.power_only_pruned` (the layout-side `SG13G2_FILL_1` and `SG13G2_FILL_2` circuits are removed before comparing) and `topology.top_level_pins_anchored` (10 top-level pins anchored by name). The compare is signal connectivity on black-box cells; `power_connectivity` is the separate check, and it reported `match`.

## Gap list

Every step ran. The items below degrade or constrain the chain; each upstream one is filed generically at `2AMLogic/klayout-tools`.

1. **No SystemVerilog front end in `klt synthesize`.** A module using `logic` / `always_ff` in a `.sv` file fails with a Yosys syntax error, so `counter.v` is plain Verilog-2005. Upstream: 2AMLogic/klayout-tools#3797. (CLAUDE.md already expects a conversion step for FlooNoC; this confirms `klt synthesize` has no hook for one.)
2. **`place-and-route` and `lvs` envelopes embed absolute host paths**, so they fail `klt env-provenance lint-envelope` as emitted. `sanitize.py` rewrites them by prefix substitution; the rewrite is mechanical and changes no other value. Upstream: 2AMLogic/klayout-tools#3798.
3. **`klt synthesize` returns `sta: null` from the published package** (the `klt_statime_native` extension is not installed and the remedy text covers only a repo checkout). Timing here comes from `klt sta` on the routed DEF. Upstream: 2AMLogic/klayout-tools#3799.
4. **No way to list a library's liberty corners**; the six names in `../pdk.json` were found by listing the library directory, and the not-found message names a filename pattern the library does not use. Upstream: 2AMLogic/klayout-tools#3800.
5. **DRC deck coverage** is the starter scope quoted above (17 deck layers, 9 stream pairs without rules). A rule the deck cannot check yet is a deck gap, not something to route around; no upstream issue is filed from this fixture, since a counter does not exercise enough of the stack to say which rules matter. The first real tile should.
6. **Worker spec: cocotb is not installed** on the dispatch worker. It is not used by this chain; `../tools.json` records `version: null`. Icarus 13.0, Yosys, OpenROAD and `uvx` are present. For `infra/aws/loom-worker/`, not for this repo.
7. **STA is ideal-clock, no SPEF, no I/O delays** (`clock_mode: ideal`, `spef_annotation: null`). The numbers show the corner fan-out works; they are not a timing claim about anything.
