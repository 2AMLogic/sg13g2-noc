#!/usr/bin/env python3
"""Generate the klt place-and-route request for one noc_tile (issue #45).

    python3 -I layout/tile/gen_request.py > layout/tile/requests/place-and-route.json

Link pins sit on the four edges, d = N0 E1 S2 W3 (decision 0003), in
interleaved (out, in) pairs per signal role. Role order is valid, last,
data[0..31], credit. North and east edges list each pair out-first, south and
west edges in-first, so by translation abutment the sender's pin at slot i on
edge d meets the receiver's pin at slot i on edge (d+2)%4:

    lk_out_*[d] / cr_out[d]  ->  neighbour's lk_in_*[(d+2)%4] / cr_in[(d+2)%4]

Every other pin (clk, rst_n, my_x/my_y, cfg_*, status) forms one unordered band
on the west edge, away from the link range (decision 0004, "cfg / status
pins"). Sizes are decision 0005: 1120 um x 1120 um outline, 4 um core margin.
"""
import argparse
import json
import sys

DIRS = ("north", "east", "south", "west")  # d = 0..3
DATA_W = 32
# Pin slot pitch along each edge as klt/OpenROAD places them on this PDK:
# Metal2 pins on north/south, Metal3 pins on east/west, slot centres at
# (n + 0.5) * pitch. An ordered group floats inside its range, so the range is
# cut to hold exactly the 70 link pins of one edge; that pins the group start
# and makes opposite edges land on the same coordinates.
SLOT_PITCH_UM = {"north": 0.96, "south": 0.96, "east": 0.84, "west": 0.84}


def link_pairs(d):
    """(out_pin, in_pin) for every signal role on edge d, in role order."""
    pairs = [(f"lk_out_valid[{d}]", f"lk_in_valid[{d}]"),
             (f"lk_out_last[{d}]", f"lk_in_last[{d}]")]
    for k in range(DATA_W):
        pairs.append((f"lk_out_data[{d * DATA_W + k}]", f"lk_in_data[{d * DATA_W + k}]"))
    pairs.append((f"cr_out[{d}]", f"cr_in[{d}]"))
    return pairs


def edge_pins(d):
    out_first = DIRS[d] in ("north", "east")
    pins = []
    for o, i in link_pairs(d):
        pins += [o, i] if out_first else [i, o]
    return pins


def link_range(edge, start_um, n_pins):
    """Range holding exactly n_pins slots, the first at or after start_um."""
    p = SLOT_PITCH_UM[edge]
    first = (int(start_um / p + 0.999999) + 0.5) * p
    return [round(first - p / 4, 4), round(first + (n_pins - 1) * p + p / 4, 4)]


def build(args):
    constraints = []
    for d, edge in enumerate(DIRS):
        pins = edge_pins(d)
        constraints.append({"pins": pins, "edge": edge, "ordered": True,
                            "range_um": link_range(edge, args.link_start, len(pins))})
    constraints.append({
        "pins": ["clk", "rst_n", "my_x[*]", "my_y[*]", "cfg_*", "gen_*", "sent_pkts[*]",
                 "done", "err", "err_count[*]", "e_*", "rx_*"],
        "edge": "west", "range_um": [args.band_lo, args.band_hi]})
    die = args.die
    m = args.core_margin
    return {
        "schema": "klt.place_and_route.request/1",
        "engine": "openroad",
        "netlist": args.netlist,
        "hdl_toplevel": args.top,
        "pdk": {"cell_library": "sg13g2_stdcell"},
        "floorplan": {"method": "explicit", "die_area_um": [0, 0, die, die],
                      "core_area_um": [m, m, die - m, die - m], "site": "CoreSite"},
        "io": {"layer_h": "Metal3", "layer_v": "Metal2", "pin_constraints": constraints},
        "power": {"power_net": "VDD", "ground_net": "VSS", "preset": "sg13g2"},
        "constraints": {"clock_port": "clk", "clock_period_ns": 10.0},
        "seed": 1,
        "target_stage": "route",
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--netlist", default=".klt/synthesize/tile/noc_tile_synth.v")
    ap.add_argument("--top", default="noc_tile")
    ap.add_argument("--die", type=float, default=1120.0)
    ap.add_argument("--core-margin", type=float, default=4.0)
    ap.add_argument("--link-start", type=float, default=100.0)
    ap.add_argument("--band-lo", type=float, default=200.0)
    ap.add_argument("--band-hi", type=float, default=1100.0)
    json.dump(build(ap.parse_args()), sys.stdout, indent=2)
    sys.stdout.write("\n")
