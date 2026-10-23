"""cocotb loopback bench for noc_tgen -> noc_tchk (issue #19, spec/noc.md s5).

Not run directly: run_bench.py builds the DUT and runs this module with
EP_MODES (comma list of sweep, depth1, coords, neg) and EP_OUT (result path)
in the environment.

Scoreboard per run: every generated packet (dst, seq) arrives exactly once at
the checker (no loss, no duplication), in order per (src, dst), the checker's
own error flags stay clear (payload integrity, sequence, framing), and the run
drains within a stated cycle bound after injection ends. A watchdog fails the
run if no flit is accepted for WATCHDOG cycles once injection has ended.
Latency is generation-to-last-flit-accepted, joined on (src, dst, seq).
"""
import json
import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

PATTERNS = {"uniform": 0, "transpose": 1, "hotspot": 2}
RATES = [0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]
LENGTHS = [1, 4, 16]
NPKTS = 64          # packets per run; seq per (src, dst) stays far below 65536
WATCHDOG = 400      # cycles without an accepted flit after injection ends
HOT = (1, 1)

ERR_NAMES = ["e_loss", "e_dup", "e_payload", "e_dest", "e_frame"]
ERR_TEXT = {
    "e_loss": "sequence check (loss/skip)",
    "e_dup": "sequence check (duplicate/reorder)",
    "e_payload": "payload check",
    "e_dest": "destination check",
    "e_frame": "framing check",
}


def nid(x, y):
    return (y << 2) | x


def thresh(rate, length):
    return round(65536 * rate / length)


def drain_bound(npkts, length, stall_max, depth):
    # cycles allowed after the last packet is generated: every queued flit
    # at the worst credit pace (round trip + stall) plus slack
    return npkts * length * (stall_max + 4 + depth) + 1000


async def run_point(dut, *, x, y, pattern, rate, length, npkts, stall_max,
                    depth, mesh, hot=HOT):
    """One reset-to-drain run; returns the result record."""
    dut.rst_n.value = 0
    dut.cfg_run.value = 0
    dut.my_x.value = x
    dut.my_y.value = y
    dut.cfg_pattern.value = PATTERNS[pattern]
    dut.cfg_thresh.value = thresh(rate, length)
    dut.cfg_len.value = length
    dut.cfg_npkts.value = npkts
    dut.cfg_stall_max.value = stall_max
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    dut.cfg_run.value = 1

    me = nid(x, y)
    gen = []                     # (cycle, dst, seq)
    heads = []                   # (dst_id, src_id, len, seq) as seen on the link
    in_pkt = False
    rx = []                      # (cycle, src, dst, seq)
    cycle = 0
    last_progress = 0
    prev_flits = 0
    gen_done_cycle = None
    problems = []
    bound = None

    while True:
        await RisingEdge(dut.clk)
        cycle += 1
        if int(dut.gen_valid.value):
            gen.append((cycle, int(dut.gen_dst.value), int(dut.gen_seq.value)))
        if int(dut.lnk_valid.value):
            d = int(dut.lnk_data.value)
            if not in_pkt:
                heads.append(((d >> 30) & 3 | ((d >> 28) & 3) << 2,
                              ((d >> 26) & 3) | ((d >> 24) & 3) << 2,
                              (d >> 16) & 0xFF, d & 0xFFFF))
            in_pkt = not int(dut.lnk_last.value)
        if int(dut.rx_pkt_valid.value):
            rx.append((cycle, int(dut.rx_src.value), int(dut.rx_dst.value),
                       int(dut.rx_seq.value)))
        flits = int(dut.rx_flits.value)
        if flits != prev_flits:
            prev_flits = flits
            last_progress = cycle
        gc = int(dut.gen_count.value)
        if gen_done_cycle is None and (gc == npkts or
                                       (pattern == "transpose" and x == y and cycle > 4)):
            gen_done_cycle = cycle
            bound = drain_bound(npkts, length, stall_max, depth)
            last_progress = cycle
        if int(dut.done.value) and gen_done_cycle is not None:
            break
        if gen_done_cycle is not None:
            if cycle - last_progress > WATCHDOG:
                problems.append(f"watchdog: no flit accepted for {WATCHDOG} cycles")
                break
            if cycle - gen_done_cycle > bound:
                problems.append(f"drain: not drained {bound} cycles after injection ended")
                break
    # let the last strobes land
    for _ in range(4):
        await RisingEdge(dut.clk)
        if int(dut.rx_pkt_valid.value):
            rx.append((cycle, int(dut.rx_src.value), int(dut.rx_dst.value),
                       int(dut.rx_seq.value)))

    # ---- scoreboard ----
    exp_n = 0 if (pattern == "transpose" and x == y) else npkts
    sent = len(gen)
    if sent != exp_n:
        problems.append(f"generated {sent} packets, expected {exp_n}")
    rx_ids = [(s, d, q) for (_, s, d, q) in rx]
    gen_ids = [(me, d, q) for (_, d, q) in gen]
    if sorted(rx_ids) != sorted(gen_ids):
        lost = set(gen_ids) - set(rx_ids)
        dup = len(rx_ids) - len(set(rx_ids))
        problems.append(f"scoreboard: {len(lost)} lost, {dup} duplicated")
    last_seq = {}
    for (_, s, d, q) in rx:
        k = (s, d)
        if k in last_seq and q <= last_seq[k]:
            problems.append(f"scoreboard: out of order on {k}: {q} after {last_seq[k]}")
            break
        last_seq[k] = q
    # generator log must match the link, in order
    if [(d, q) for (_, d, q) in gen] != [(h[0], h[3]) for h in heads]:
        problems.append("link: head flits differ from the generation log")
    for h in heads:
        if h[1] != me or h[2] != length:
            problems.append(f"link: bad head src/len {h}")
            break
    mx, my = mesh
    dsts = [d for (_, d, _) in gen]
    for d in dsts:
        dx, dy = d & 3, d >> 2
        if dx >= mx or dy >= my or d == me:
            problems.append(f"pattern: destination {d} outside mesh or self")
            break
    if pattern == "transpose" and any(d != nid(y, x) for d in dsts):
        problems.append("pattern: transpose destination wrong")
    hot_frac = None
    if dsts:
        hot_frac = sum(1 for d in dsts if d == nid(*hot)) / len(dsts)
        if pattern == "hotspot" and me != nid(*hot) and npkts >= 64 \
                and not (0.3 <= hot_frac <= 0.7):
            problems.append(f"pattern: hotspot fraction {hot_frac:.2f} not near 0.5")
    flags = {n: int(getattr(dut, n).value) for n in ERR_NAMES}
    for n in ERR_NAMES:
        if flags[n]:
            problems.append(f"checker error flag: {ERR_TEXT[n]}")
    if int(dut.rx_pkts.value) != exp_n:
        problems.append(f"checker counted {int(dut.rx_pkts.value)} packets, expected {exp_n}")
    # latency
    gmap = {(d, q): c for (c, d, q) in gen}
    lats = [c - gmap[(d, q)] for (c, s, d, q) in rx if (d, q) in gmap and s == me]
    span = (gen[-1][0] - gen[0][0]) if len(gen) > 1 else 0
    return {
        "node": [x, y], "pattern": pattern, "rate": rate, "length": length,
        "stall_max": stall_max, "depth": depth, "mesh": list(mesh),
        "packets_sent": sent, "packets_received": len(rx),
        "errors": int(dut.err_count.value),
        "drained": not any(p.startswith(("drain", "watchdog")) for p in problems),
        "drain_bound_cycles": bound,
        "offered_rate_achieved": round(sent * length / span, 4) if span else None,
        "hot_fraction": hot_frac,
        "latency_cycles_mean": round(sum(lats) / len(lats), 2) if lats else None,
        "latency_cycles_max": max(lats) if lats else None,
        "simulated": True,
        "problems": problems,
    }


@cocotb.test()
async def run_all(dut):
    modes = os.environ["EP_MODES"].split(",")
    depth = int(os.environ.get("EP_DEPTH", "4"))
    mx = 1 << int(os.environ.get("EP_XW", "1"))
    my = 1 << int(os.environ.get("EP_YW", "1"))
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    results = {}
    failures = []

    def record(section, rec):
        results.setdefault(section, []).append(rec)
        if rec["problems"]:
            failures.append((rec["pattern"], rec["rate"], rec["length"], rec["node"],
                             rec["problems"]))

    base = dict(npkts=NPKTS, depth=depth, mesh=(mx, my))
    if "sweep" in modes:
        for pattern in PATTERNS:
            for rate in RATES:
                for length in LENGTHS:
                    record("points", await run_point(
                        dut, x=0, y=1, pattern=pattern, rate=rate, length=length,
                        stall_max=0, **base))
        for pattern in PATTERNS:           # random-stall checker
            for length in LENGTHS:
                record("points", await run_point(
                    dut, x=0, y=1, pattern=pattern, rate=1.0, length=length,
                    stall_max=8, **base))
    if "depth1" in modes:                  # one credit: hardest backpressure
        for pattern in PATTERNS:
            for length in (1, 4, 16):
                for stall in (0, 8):
                    record("points", await run_point(
                        dut, x=0, y=1, pattern=pattern, rate=1.0, length=length,
                        stall_max=stall, **base))
    if "coords" in modes:                  # every node, every pattern
        for yy in range(my):
            for xx in range(mx):
                for pattern in PATTERNS:
                    record("coords", await run_point(
                        dut, x=xx, y=yy, pattern=pattern, rate=0.5, length=4,
                        stall_max=3, **base))
    if "neg" in modes:                     # negative control: must trip
        record("points", await run_point(
            dut, x=0, y=1, pattern="uniform", rate=0.5, length=4,
            stall_max=0, **base))

    with open(os.environ["EP_OUT"], "w") as f:
        json.dump(results, f, indent=1, sort_keys=True)
    if failures:
        for (p, r, l, n, probs) in failures[:10]:
            dut._log.error("FAIL %s rate=%s len=%s node=%s: %s", p, r, l, n, "; ".join(probs))
        raise AssertionError(f"{len(failures)} run(s) failed")
