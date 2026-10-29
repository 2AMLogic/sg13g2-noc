"""cocotb scoreboard bench for the 2 x 2 mesh noc_mesh (issue #25, spec/noc.md s5).

Not run directly: run_bench.py builds the DUT and runs this module with MESH_MODES
(comma list of sweep, adversarial, depth1, reset, neg), MESH_DEPTH and MESH_OUT in
the environment.

The DUT is the shipped mesh top: four tiles, each router + generator + checker, so
the tile seams (link registers, credit registers, tie-offs) are exercised as built.
One run = reset, configure all four endpoints identically, inject a fixed number of
packets per node, drain. Checks, named in every failure message:

  [scoreboard]           every generated (src, dst, seq) arrives exactly once, at its
                         destination, in order per (src, dst); the generation log is
                         dense per pair; flit totals match
  [checker]              the endpoints' own sticky flags (payload, sequence, dest,
                         framing) stay clear
  [pattern]              destinations obey the pattern (transpose, hotspot share,
                         diagonal), never self, inside the mesh
  [credit-conservation]  per link and per endpoint port, from register state:
                         sender credits + flits in flight/buffered + credits in
                         flight = DEPTH
  [watchdog]             no flit accepted anywhere for WATCHDOG cycles while packets
                         are outstanding
  [drain]                everything accepted within drain_bound() cycles after the
                         last packet is generated
  [reset]                reset applied mid-traffic really interrupted traffic and
                         left the mesh clean

The diagonal-opposite pattern is not one of the generator's three patterns, so the
bench forces each generator's destination net to the opposite node (ID[3 - n]); no RTL is
changed. Latency and throughput are simulated, generation to last flit accepted.
"""
import json
import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.handle import Force, Release
from cocotb.triggers import FallingEdge

PATTERNS = {"uniform": 0, "transpose": 1, "hotspot": 2, "diagonal": 0}
RATES = [0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]
LENGTHS = [1, 4, 16]
NPKTS = 64          # packets per node per run; seq per pair stays far below 65536
WATCHDOG = 400      # cycles with no accepted flit while packets are outstanding
NN = 4
ID = [0, 1, 4, 5]   # tile n = 2y + x carries node id {y[1:0], x[1:0]}
HOT = 5             # node id of (1, 1)

CHECK_NAMES = ["e_loss", "e_dup", "e_payload", "e_dest", "e_frame"]
CHECK_TEXT = {
    "e_loss": "sequence (loss/skip)",
    "e_dup": "sequence (duplicate/reorder)",
    "e_payload": "payload",
    "e_dest": "destination",
    "e_frame": "framing",
}


def thresh(rate, length):
    return round(65536 * rate / length)


def drain_bound(total_flits, stall_max, depth):
    """Cycles allowed after the last packet is generated: every flit in the system at
    the worst per-flit pace (credit round trip + sink stall + buffer depth), plus slack."""
    return total_flits * (stall_max + 4 + depth) + 1000


def expected_dst(pattern, n):
    x, y = n & 1, n >> 1
    if pattern == "transpose":
        return None if x == y else (x << 2) | y
    if pattern == "diagonal":
        return ID[3 - n]
    return None


class Probe:
    """Cached handles on the internal registers the credit-conservation check reads."""

    def __init__(self, dut, depth):
        self.depth = depth
        self.t = []
        for n in range(NN):
            tile = getattr(dut, f"u_tile{n}")
            self.t.append({
                "occ": tile.u_router.dbg_occ, "cr": tile.u_router.dbg_credits,
                "ov": tile.u_router.out_valid, "qv": tile.q_valid, "qc": tile.q_cr,
                "gcr": tile.u_tgen.credits, "gov": tile.u_tgen.out_valid,
                "pend": tile.u_tchk.pend, "cout": tile.u_tchk.credit_out,
            })

    def snapshot(self):
        s = []
        for h in self.t:
            s.append({k: int(v.value) for k, v in h.items()})
        return s

    def check(self):
        """Return a failure message, or None. Call at a falling edge (state settled)."""
        d = self.depth
        s = self.snapshot()
        for n in range(NN):
            x, y = n & 1, n >> 1
            a = s[n]
            if a["gcr"] + a["gov"] + ((a["occ"] >> 12) & 7) != d:
                return (f"node {n} injection port: generator credits {a['gcr']} + flit in "
                        f"flight {a['gov']} + buffered {(a['occ'] >> 12) & 7} != DEPTH {d}")
            if ((a["cr"] >> 12) & 7) + ((a["ov"] >> 4) & 1) + a["pend"] + a["cout"] != d:
                return (f"node {n} ejection port: router credits {(a['cr'] >> 12) & 7} + flit "
                        f"{(a['ov'] >> 4) & 1} + pending {a['pend']} + credit in flight "
                        f"{a['cout']} != DEPTH {d}")
            for dr, (dx, dy) in enumerate([(0, 1), (1, 0), (0, -1), (-1, 0)]):   # N E S W
                nx, ny = x + dx, y + dy
                if not (0 <= nx < 2 and 0 <= ny < 2):
                    continue
                m = 2 * ny + nx
                r = (dr + 2) % 4
                b = s[m]
                parts = (((a["cr"] >> (3 * dr)) & 7), (a["ov"] >> dr) & 1, (a["qv"] >> dr) & 1,
                         (b["occ"] >> (3 * r)) & 7, (b["qc"] >> r) & 1)
                if sum(parts) != d:
                    return (f"link node {n} dir {'NESW'[dr]} -> node {m}: sender credits "
                            f"{parts[0]} + router reg {parts[1]} + link reg {parts[2]} + receiver "
                            f"buffer {parts[3]} + credit reg {parts[4]} = {sum(parts)} != DEPTH {d}")
        return None


async def run_point(dut, probe, *, pattern, rate, length, stall_max, depth, npkts=NPKTS,
                    check_every=16, reset_at=None):
    """One reset-to-drain run on the whole mesh; returns the result record."""
    diag = pattern == "diagonal"
    dut.rst_n.value = 0
    dut.cfg_run.value = 0
    dut.cfg_pattern.value = PATTERNS[pattern]
    dut.cfg_thresh.value = thresh(rate, length)
    dut.cfg_len.value = length
    dut.cfg_npkts.value = npkts
    dut.cfg_check_dst.value = 1
    dut.cfg_stall_max.value = stall_max
    for _ in range(3):
        await FallingEdge(dut.clk)
    dut.rst_n.value = 1
    await FallingEdge(dut.clk)
    if diag:
        for n in range(NN):
            getattr(dut, f"u_tile{n}").u_tgen.dst_id.set(Force(ID[3 - n]))
    dut.cfg_run.value = 1

    exp_gen = [0 if (pattern == "transpose" and (n & 1) == (n >> 1)) else npkts for n in range(NN)]
    gen = [[] for _ in range(NN)]          # (cycle, dst, seq) per source
    rx = [[] for _ in range(NN)]           # (cycle, src, dst, seq) per destination
    problems = []
    cycle = 0
    last_progress = 0
    prev_flits = -1
    gen_done_cycle = None
    bound = None
    reset_done = reset_at is None
    exp_flits = 0

    def fail(kind, msg):
        problems.append(f"[{kind}] {msg}")

    while not problems:
        await FallingEdge(dut.clk)
        cycle += 1
        gv = int(dut.gen_valid.value)
        if gv:
            gd, gs = int(dut.gen_dst.value), int(dut.gen_seq.value)
            for n in range(NN):
                if (gv >> n) & 1:
                    gen[n].append((cycle, (gd >> (4 * n)) & 15, (gs >> (16 * n)) & 0xFFFF))
        rv = int(dut.rx_pkt_valid.value)
        if rv:
            rs, rd, rq = int(dut.rx_src.value), int(dut.rx_dst.value), int(dut.rx_seq.value)
            for n in range(NN):
                if (rv >> n) & 1:
                    rx[n].append((cycle, (rs >> (4 * n)) & 15, (rd >> (4 * n)) & 15,
                                  (rq >> (16 * n)) & 0xFFFF))
        if check_every and cycle % check_every == 0:
            msg = probe.check()
            if msg:
                fail("credit-conservation", f"cycle {cycle}: {msg}")
                break
        flits = int(dut.rx_flits.value)
        n_gen = sum(len(g) for g in gen)
        n_rx = sum(len(r) for r in rx)
        outstanding = n_gen - n_rx
        if flits != prev_flits or outstanding == 0:
            prev_flits = flits
            last_progress = cycle
        if cycle - last_progress > WATCHDOG:
            fail("watchdog", f"cycle {cycle}: no flit accepted for {WATCHDOG} cycles with "
                 f"{outstanding} packets outstanding")
            break

        if not reset_done and cycle == reset_at:
            if outstanding <= 0 or n_gen == 0:
                fail("reset", f"reset at cycle {cycle} found no traffic in flight")
                break
            dut.rst_n.value = 0
            for _ in range(3):
                await FallingEdge(dut.clk)
            snap = probe.snapshot()
            msg = probe.check()
            if msg or any(h["occ"] or h["gov"] or h["pend"] or h["cout"] or h["ov"] or h["qv"] or h["qc"]
                          for h in snap):
                fail("reset", f"mesh not clean in reset: {msg or 'buffers or link registers not empty'}")
                break
            dut.rst_n.value = 1
            gen = [[] for _ in range(NN)]
            rx = [[] for _ in range(NN)]
            cycle = 0
            last_progress = 0
            prev_flits = -1
            reset_done = True
            continue

        if gen_done_cycle is None and all(int(dut.gen_count.value) >> (16 * n) & 0xFFFF == exp_gen[n]
                                          for n in range(NN)):
            gen_done_cycle = cycle
            exp_flits = sum(exp_gen) * length
            bound = drain_bound(exp_flits, stall_max, depth)
        if gen_done_cycle is not None:
            if cycle - gen_done_cycle > bound:
                fail("drain", f"not drained {bound} cycles after injection ended "
                     f"({outstanding} packets outstanding)")
                break
            if int(dut.done.value) == 15 and outstanding == 0:
                break
    # let late strobes land (a duplicate would show up here)
    if not problems:
        for _ in range(8):
            await FallingEdge(dut.clk)
            rv = int(dut.rx_pkt_valid.value)
            if rv:
                rs, rd, rq = int(dut.rx_src.value), int(dut.rx_dst.value), int(dut.rx_seq.value)
                for n in range(NN):
                    if (rv >> n) & 1:
                        rx[n].append((cycle, (rs >> (4 * n)) & 15, (rd >> (4 * n)) & 15,
                                      (rq >> (16 * n)) & 0xFFFF))
        msg = probe.check()
        if msg:
            fail("credit-conservation", f"after drain: {msg}")

    flags = {k: int(getattr(dut, k).value) for k in CHECK_NAMES}   # 4-bit, one per node
    err_count = sum((int(dut.err_count.value) >> (16 * n)) & 0xFFFF for n in range(NN))
    rx_pkts = sum((int(dut.rx_pkts.value) >> (32 * n)) & 0xFFFFFFFF for n in range(NN))
    rx_flits_total = sum((int(dut.rx_flits.value) >> (32 * n)) & 0xFFFFFFFF for n in range(NN))
    if diag:
        for n in range(NN):
            getattr(dut, f"u_tile{n}").u_tgen.dst_id.set(Release())

    # ---- scoreboard ----
    if not problems:
        gen_ids = sorted((ID[n], d, q) for n in range(NN) for (_, d, q) in gen[n])
        rx_ids = sorted((s, d, q) for n in range(NN) for (_, s, d, q) in rx[n])
        if gen_ids != rx_ids:
            lost = set(gen_ids) - set(rx_ids)
            extra = len(rx_ids) - len(set(rx_ids))
            fail("scoreboard", f"{len(lost)} lost, {extra} duplicated, "
                 f"{len(gen_ids)} generated, {len(rx_ids)} received")
        for n in range(NN):
            if len(gen[n]) != exp_gen[n]:
                fail("scoreboard", f"node {n} generated {len(gen[n])} packets, expected {exp_gen[n]}")
            last_seq = {}
            for (_, s, d, q) in rx[n]:
                if d != ID[n]:
                    fail("scoreboard", f"packet for node {d} delivered to node {n} (id {ID[n]})")
                    break
                if (s, d) in last_seq and q <= last_seq[(s, d)]:
                    fail("scoreboard", f"out of order on {s}->{d}: seq {q} after {last_seq[(s, d)]}")
                    break
                last_seq[(s, d)] = q
            per = {}
            for (_, d, q) in gen[n]:
                per.setdefault(d, []).append(q)
            if any(qs != list(range(len(qs))) for qs in per.values()):
                fail("scoreboard", f"node {n} generation log not dense per destination")
        if rx_pkts != sum(exp_gen):
            fail("scoreboard", f"checkers counted {rx_pkts} packets, expected {sum(exp_gen)}")
        if rx_flits_total != sum(exp_gen) * length:
            fail("scoreboard", f"{rx_flits_total} flits accepted, expected {sum(exp_gen) * length}")
        for n in range(NN):
            for (_, d, _) in gen[n]:
                if d == ID[n] or d not in ID:
                    fail("pattern", f"node {n} sent to {d}")
                    break
        exp = {n: expected_dst(pattern, n) for n in range(NN)}
        for n in range(NN):
            if exp[n] is not None and any(d != exp[n] for (_, d, _) in gen[n]):
                fail("pattern", f"{pattern} destination wrong at node {n}")
        hot_frac = None
        if pattern == "hotspot":
            fr = [sum(1 for (_, d, _) in gen[n] if d == HOT) / len(gen[n]) for n in range(NN) if ID[n] != HOT]
            hot_frac = round(sum(fr) / len(fr), 3)
            if any(not 0.3 <= f <= 0.7 for f in fr):
                fail("pattern", f"hotspot share {fr} not near 0.5 at the non-hot nodes")
        for k in CHECK_NAMES:
            if flags[k]:
                fail("checker", f"error flag: {CHECK_TEXT[k]} (err_count {err_count})")
    else:
        hot_frac = None
        for k in CHECK_NAMES:
            if flags[k]:
                problems.append(f"[checker] error flag: {CHECK_TEXT[k]} (err_count {err_count})")

    # ---- latency / throughput (simulated) ----
    gmap = {(ID[n], d, q): c for n in range(NN) for (c, d, q) in gen[n]}
    lats = [c - gmap[(s, d, q)] for n in range(NN) for (c, s, d, q) in rx[n] if (s, d, q) in gmap]
    tx_first = min((g[0][0] for g in gen if g), default=0)
    tx_last = max((g[-1][0] for g in gen if g), default=0)
    rx_last = max((r[-1][0] for r in rx if r), default=0)
    sent = sum(len(g) for g in gen)
    nsrc = sum(1 for g in gen if g)
    span_gen = tx_last - tx_first
    span_rx = rx_last - tx_first
    return {
        "pattern": pattern, "rate": rate, "length": length, "stall_max": stall_max,
        "depth": depth, "reset_at": reset_at, "packets_per_node": npkts,
        "packets_sent": sent, "packets_received": sum(len(r) for r in rx),
        "errors": err_count, "drained": not any(p.startswith(("[drain]", "[watchdog]")) for p in problems),
        "drain_bound_cycles": bound,
        "offered_flits_per_node_cycle": round(sent * length / (nsrc * span_gen), 4) if span_gen and nsrc else None,
        "accepted_flits_per_node_cycle": round(sent * length / (NN * span_rx), 4) if span_rx > 0 else None,
        "hot_fraction": hot_frac,
        "latency_cycles_mean": round(sum(lats) / len(lats), 2) if lats else None,
        "latency_cycles_max": max(lats) if lats else None,
        "simulated": True,
        "problems": problems,
    }


@cocotb.test()
async def run_all(dut):
    modes = os.environ["MESH_MODES"].split(",")
    depth = int(os.environ.get("MESH_DEPTH", "4"))
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    probe = Probe(dut, depth)
    results = []
    failures = []
    random.seed(25)

    async def point(**kw):
        rec = await run_point(dut, probe, depth=depth, **kw)
        results.append(rec)
        if rec["problems"]:
            failures.append(rec)
            dut._log.error("FAIL %s rate=%s len=%s stall=%s: %s", rec["pattern"], rec["rate"],
                           rec["length"], rec["stall_max"], "; ".join(rec["problems"]))

    if "sweep" in modes:
        for pattern in ("uniform", "transpose", "hotspot"):
            for rate in RATES:
                for length in LENGTHS:
                    await point(pattern=pattern, rate=rate, length=length, stall_max=0)
    if "adversarial" in modes:
        # every cycle checked: all nodes, long packets, rate 1.0, with and without stalls
        for pattern, length, stall in [
            ("diagonal", 16, 0), ("diagonal", 16, 8), ("diagonal", 4, 15),
            ("transpose", 16, 0), ("transpose", 16, 8),
            ("uniform", 16, 8), ("uniform", 16, 15), ("hotspot", 16, 0), ("hotspot", 16, 8),
            ("hotspot", 4, 15),
        ]:
            await point(pattern=pattern, rate=1.0, length=length, stall_max=stall, check_every=1)
    if "depth1" in modes:
        for pattern, length, stall in [
            ("hotspot", 1, 0), ("hotspot", 4, 0), ("hotspot", 16, 0), ("hotspot", 1, 8),
            ("hotspot", 4, 8), ("hotspot", 16, 8), ("diagonal", 16, 0), ("diagonal", 16, 8),
            ("transpose", 16, 8), ("uniform", 16, 8),
        ]:
            await point(pattern=pattern, rate=1.0, length=length, stall_max=stall, check_every=1)
    if "reset" in modes:
        await point(pattern="uniform", rate=1.0, length=16, stall_max=3, check_every=1, reset_at=150)
        await point(pattern="hotspot", rate=0.5, length=4, stall_max=0, check_every=1, reset_at=100)
        await point(pattern="diagonal", rate=1.0, length=16, stall_max=8, check_every=1, reset_at=300)
    if "neg" in modes:
        await point(pattern="uniform", rate=0.5, length=4, stall_max=3, check_every=1)

    with open(os.environ["MESH_OUT"], "w") as f:
        json.dump(results, f, indent=1, sort_keys=True)
    if failures:
        raise AssertionError(f"{len(failures)} of {len(results)} run(s) failed")
