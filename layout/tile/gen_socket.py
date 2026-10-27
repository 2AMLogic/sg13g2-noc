#!/usr/bin/env python3
"""Write the klt socket descriptor `klt lef-abstract` needs, from a P&R response.

    python3 -I layout/tile/gen_socket.py RESPONSE.json OUTLINE_UM > socket.json

One signal pin per top-level port bit of the response's pins[] (x/y are where
klt put the pin label), with the GDS text layer of its metal and a direction
from the port name. VDD/VSS are declared at the one position klt reports for
them, as POWER/GROUND, so the abstract carries power pins.
"""
import json
import sys

# SG13G2 GDS text (label) layer/datatype per routing metal, from the PDK's
# sg13g2.map (purpose 25 = label).
TEXT_LAYER = {"Metal1": [8, 25], "Metal2": [10, 25], "Metal3": [30, 25],
              "Metal4": [50, 25], "Metal5": [67, 25], "TopMetal1": [126, 25],
              "TopMetal2": [134, 25]}
OUTPUT_PREFIXES = ("lk_out_", "cr_out", "gen_", "sent_", "done", "err", "e_", "rx_")


SUPPLY = {"VDD": "POWER", "VSS": "GROUND"}


def direction(name):
    if name in SUPPLY:
        return "INOUT"
    return "OUTPUT" if name.startswith(OUTPUT_PREFIXES) else "INPUT"


def main(resp_path, size):
    resp = json.load(open(resp_path))
    pins = [{"name": p["name"], "layer": TEXT_LAYER[p["layer"]],
             "x": p["x_um"], "y": p["y_um"], "tolerance_um": 0.01,
             "direction": direction(p["name"]), "use": SUPPLY.get(p["name"], "CLOCK" if p["name"] == "clk" else "SIGNAL")}
            for p in resp["pins"]]
    json.dump({"schema": "klt.socket/1",
               "outline": {"x0": 0, "y0": 0, "x1": float(size), "y1": float(size)},
               "pins": pins}, sys.stdout, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
