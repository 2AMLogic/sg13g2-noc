#!/usr/bin/env python3
"""Check the tile's link pins line up for abutment, from a klt P&R response.

    python3 -I layout/tile/check_abut.py layout/tile/reports/place-and-route.json

For every link signal the sender's pin on edge d must sit at the same
coordinate along the edge (x for north/south, y for east/west) as the
receiver's pin on edge (d+2)%4, on the same layer (translation abutment,
decision 0003):
    lk_out_*[d] <-> lk_in_*[(d+2)%4]    cr_out[d] <-> cr_in[(d+2)%4]
Exits 1 on any misaligned, missing, wrongly placed or duplicate-slot pin.
"""
import json
import sys

EDGES = ("north", "east", "south", "west")
OPP = {"north": "south", "south": "north", "east": "west", "west": "east"}
DATA_W = 32


def pin_name(kind, role, d):
    """kind out|in, role valid|last|data<k>|cr -> netlist pin bit name."""
    if role == "cr":
        return f"cr_{kind}[{d}]"
    if role.startswith("data"):
        return f"lk_{kind}_data[{d * DATA_W + int(role[4:])}]"
    return f"lk_{kind}_{role}[{d}]"


def main(path):
    pins = {p["name"]: p for p in json.load(open(path))["pins"]}
    roles = ["valid", "last"] + [f"data{k}" for k in range(DATA_W)] + ["cr"]
    errs, n = [], 0
    slots = {}
    for d, edge in enumerate(EDGES):
        axis = "x_um" if edge in ("north", "south") else "y_um"
        for kind in ("out", "in"):
            for role in roles:
                name = pin_name(kind, role, d)
                p = pins.get(name)
                if p is None:
                    errs.append(f"{name}: missing from response pins[]")
                    continue
                if p["edge"] != edge:
                    errs.append(f"{name}: on {p['edge']}, want {edge}")
                if (edge, p[axis]) in slots:
                    errs.append(f"{name}: shares slot {p[axis]} with {slots[(edge, p[axis])]}")
                slots[(edge, p[axis])] = name
    for d, edge in enumerate(EDGES):
        e2 = (d + 2) % 4
        axis = "x_um" if edge in ("north", "south") else "y_um"
        for kind, other in (("out", "in"), ("in", "out")):
            for role in roles:
                a, b = pins.get(pin_name(kind, role, d)), pins.get(pin_name(other, role, e2))
                if a is None or b is None:
                    continue
                n += 1
                if abs(a[axis] - b[axis]) > 1e-6 or a["layer"] != b["layer"]:
                    errs.append(f"{a['name']} ({edge} {a[axis]} {a['layer']}) != "
                                f"{b['name']} ({OPP[edge]} {b[axis]} {b['layer']})")
    for e in errs[:40]:
        print("MISALIGNED:", e)
    print(f"abutment pairs checked: {n}; problems: {len(errs)}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
