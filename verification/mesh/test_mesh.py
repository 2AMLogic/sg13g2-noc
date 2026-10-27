"""cocotb 2 x 2 mesh scoreboard (issue #40, spec/noc.md s5).

The mesh sets noc_tchk KEY_SRC_ONLY=1 (sequence table keyed on src, since
cfg_check_dst=1 pins dst to the node). This bench checks the per-source
sequence/duplicate detection still holds at mesh level, independently of the
checker's own flags:
  * every packet generated at every node arrives exactly once at its
    destination (no loss, no duplication), in order per (src, dst);
  * every checker's error flags stay clear on clean RTL;
  * with MESH_NEG=NEG_SKIPSEQ the checker must raise e_loss, and
    NEG_CORRUPT must raise e_payload, at the destination of the faulty packet.
"""
import os

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

PATTERNS = {"uniform": 0, "transpose": 1, "hotspot": 2}
NPKTS = 64
LENGTH = 4
RATE = 0.5
WATCHDOG = 600
MAXCYC = 60000
FLAGS = ["e_loss", "e_dup", "e_payload", "e_dest", "e_frame"]


def nid(n):
    # mesh node n = 2*y + x; node id is {y[1:0], x[1:0]}
    return ((n >> 1) << 2) | (n & 1)


def sl(sig, i, w):
    return (int(sig.value) >> (i * w)) & ((1 << w) - 1)


async def run_pattern(dut, pattern, stall_max):
    dut.rst_n.value = 0
    dut.cfg_run.value = 0
    dut.cfg_pattern.value = PATTERNS[pattern]
    dut.cfg_thresh.value = round(65536 * RATE / LENGTH)
    dut.cfg_len.value = LENGTH
    dut.cfg_npkts.value = NPKTS
    dut.cfg_check_dst.value = 1
    dut.cfg_stall_max.value = stall_max
    for _ in range(4):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    dut.cfg_run.value = 1

    rx = [[] for _ in range(4)]          # per node: (src, dst, seq)
    quiet = 0
    prev = -1
    for cyc in range(MAXCYC):
        await RisingEdge(dut.clk)
        for n in range(4):
            if (int(dut.rx_pkt_valid.value) >> n) & 1:
                rx[n].append((sl(dut.rx_src, n, 4), sl(dut.rx_dst, n, 4),
                              sl(dut.rx_seq, n, 16)))
        total = sum(sl(dut.rx_pkts, n, 32) for n in range(4))
        quiet = 0 if total != prev else quiet + 1
        prev = total
        sent_now = sum(sl(dut.sent_pkts, n, 16) for n in range(4))
        if int(dut.done.value) == 0xF and total == sent_now and quiet > 8:
            break
        if quiet > WATCHDOG:
            break
    for _ in range(4):
        await RisingEdge(dut.clk)
        for n in range(4):
            if (int(dut.rx_pkt_valid.value) >> n) & 1:
                rx[n].append((sl(dut.rx_src, n, 4), sl(dut.rx_dst, n, 4),
                              sl(dut.rx_seq, n, 16)))

    problems = []
    flags = {f: int(getattr(dut, f).value) for f in FLAGS}
    sent = sum(sl(dut.sent_pkts, n, 16) for n in range(4))
    got = sum(len(r) for r in rx)
    if int(dut.done.value) != 0xF:
        problems.append("drain: not all nodes done")
    for n in range(4):
        last = {}
        for (s, d, q) in rx[n]:
            if d != nid(n):
                problems.append(f"node {n}: received packet for {d}")
                break
            if s in last and q <= last[s]:
                problems.append(f"node {n}: src {s} seq {q} after {last[s]} "
                                "(duplicate or reorder)")
                break
            last[s] = q
        # per-source count: seqs must be exactly 0..k-1 (no gap, no repeat)
        for s in {x[0] for x in rx[n]}:
            seqs = [q for (ss, _, q) in rx[n] if ss == s]
            if seqs != list(range(len(seqs))):
                problems.append(f"node {n}: src {s} sequence not contiguous")
    if sent != got:
        problems.append(f"scoreboard: {sent} sent, {got} received")
    return flags, problems, sent


@cocotb.test()
async def mesh_scoreboard(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    neg = os.environ.get("MESH_NEG", "")
    bad = []
    tripped = set()
    for pattern in PATTERNS:
        for stall in (0, 6):
            flags, problems, sent = await run_pattern(dut, pattern, stall)
            dut._log.info("%s stall=%d sent=%d flags=%s problems=%s",
                          pattern, stall, sent, flags, problems)
            for f in FLAGS:
                if flags[f]:
                    tripped.add(f)
                    if not neg:
                        bad.append(f"{pattern}/{stall}: checker flag {f}={flags[f]:#x}")
            if not neg:
                bad += [f"{pattern}/{stall}: {p}" for p in problems]
    if neg:
        want = {"NEG_SKIPSEQ": "e_loss", "NEG_CORRUPT": "e_payload"}[neg]
        for f in sorted(tripped):
            dut._log.error("tripped: checker flag %s", f)
        assert want in tripped, f"{neg} did not trip {want}"
        raise AssertionError(f"negative control {neg} tripped as intended")
    assert not bad, "; ".join(bad[:10])
