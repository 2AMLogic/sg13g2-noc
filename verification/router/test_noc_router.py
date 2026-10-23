"""cocotb bench for rtl/noc_router.v in isolation (issue #18).

The router is driven and observed only through its link interface. The bench
supplies what the tile edge supplies in the mesh: one link register per
direction (forward flit, reverse credit), so the credit round trip is the 4
cycles decision 0002 sizes depth 4 for. Correctness is a scoreboard (spec/noc.md
section 5), not a waveform; every failure message starts with the name of the
check that tripped: [scoreboard], [credit-conservation] or [watchdog]
([drain] for the drain bound).

Router under test sits at (X, Y) = (1, 1) of a notional 4 x 4 mesh so that all
five outputs are reachable. Packet source field `[27:24]` carries the *input
port number* (0-4) in this bench, standing in for the source node.

Bench cycle (one `step`), at each falling edge, half a clock after the router's
registers moved:
  1. read registered router state and check credit conservation;
  2. drive the link registers' contents onto the router inputs;
  3. read the router's combinational credit returns and its output registers;
  4. update the source models, link registers and sink models.
"""
import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, Timer

DEPTH = int(os.environ.get("NOC_DEPTH", "4"))
RX, RY = 1, 1
N, E, S, W, L = range(5)
PORT = "NESWL"
M32 = 0xFFFFFFFF
SPEC_ROUTER_CYCLES = 2          # spec/noc.md section 1, router pipeline
WATCHDOG_CYCLES = 100


def fail(kind, msg):
    cocotb.log.error("CHECK TRIPPED: %s", kind)
    raise AssertionError(f"[{kind}] {msg}")


def xy_route(dx, dy):
    if dx > RX: return E
    if dx < RX: return W
    if dy > RY: return N
    if dy < RY: return S
    return L


def legal_dests(p):
    """Destinations a packet arriving on input p can have under XY routing."""
    out = []
    for x in range(4):
        for y in range(4):
            if p == W and x < RX: continue
            if p == E and x > RX: continue
            if p == N and not (x == RX and y <= RY): continue
            if p == S and not (x == RX and y >= RY): continue
            if p == L and (x, y) == (RX, RY): continue
            out.append((x, y))
    return out


def dest_for_output(p, o):
    """A legal destination for input p that XY-routes to output o, or None."""
    for d in legal_dests(p):
        if xy_route(*d) == o:
            return d
    return None


class Packet:
    def __init__(self, rng, seqs, src, dest, length):
        self.src, self.dest, self.length = src, dest, length
        self.seq = seqs.get((src, dest), 0)
        seqs[(src, dest)] = self.seq + 1
        head = (dest[0] << 30) | (dest[1] << 28) | (src << 24) | (length << 16) | self.seq
        words = [head] + [rng.getrandbits(32) for _ in range(length - 1)]
        self.flits = [(1 if i == length - 1 else 0, w) for i, w in enumerate(words)]
        self.key = (src, dest, self.seq)


class Bench:
    def __init__(self, dut, rate=1.0, stall_prob=0.0, max_stall=0, seed=1):
        self.dut, self.rate = dut, rate
        self.stall_prob, self.max_stall = stall_prob, max_stall
        self.rng = random.Random(seed)
        self.seqs = {}
        self.src_q = [[] for _ in range(5)]
        self.src_cnt = [DEPTH] * 5
        self.src_out = [None] * 5       # source output register (pins next cycle)
        self.LF = [None] * 5            # forward link register, drives router in
        self.LCin = [0] * 5             # reverse link register into the source
        self.snk_fifo = [[] for _ in range(5)]
        self.LFo = [None] * 5           # forward link register out of the router
        self.LCout = [0] * 5            # reverse link register into the router
        self.stall_left = [0] * 5
        self.forced_go = [False] * 5
        self.cyc = 0
        self.outstanding = {}
        self.seen = set()
        self.last_seq = {}
        self.cur = [None] * 5           # packet being received on each output
        self.injected_flits = 0
        self.delivered_flits = 0
        self.delivered_pkts = 0
        self.total_pkts = 0
        self.last_progress = 0
        self.blocked = False
        self.t_in_first = None
        self.t_out_first = None
        self.t_out_last = None
        self.deliver_cycles = []

    # ------------------------------------------------------------- stimulus
    def add(self, src, dest, length):
        pkt = Packet(self.rng, self.seqs, src, dest, length)
        for i, (last, w) in enumerate(pkt.flits):
            self.src_q[src].append((last, w, pkt if i == 0 else None))
        self.total_pkts += 1
        return pkt

    def random_plan(self, inputs, n_per_input, lengths, fixed_dest=None):
        for p in inputs:
            for _ in range(n_per_input):
                d = fixed_dest if fixed_dest else self.rng.choice(legal_dests(p))
                self.add(p, d, self.rng.choice(lengths))

    # ----------------------------------------------------------- scoreboard
    def deliver(self, o, flit):
        last, w = flit
        self.delivered_flits += 1
        self.last_progress = self.cyc
        self.deliver_cycles.append(self.cyc)
        cur = self.cur[o]
        if cur is None:
            dx, dy, src, ln, seq = w >> 30, (w >> 28) & 3, (w >> 24) & 15, (w >> 16) & 255, w & 0xFFFF
            if xy_route(dx, dy) != o:
                fail("scoreboard", f"misroute: head for dest ({dx},{dy}) src {src} seq {seq} "
                     f"left output {PORT[o]}, XY says {PORT[xy_route(dx, dy)]}")
            key = (src, (dx, dy), seq)
            pkt = self.outstanding.pop(key, None)
            if pkt is None:
                why = "duplicated" if key in self.seen else "never injected / corrupt head"
                fail("scoreboard", f"packet {key} at output {PORT[o]} {why}")
            self.seen.add(key)
            pair = (src, (dx, dy))
            if self.last_seq.get(pair, -1) >= seq:
                fail("scoreboard", f"reordered: pair {pair} seq {seq} after {self.last_seq[pair]}")
            self.last_seq[pair] = seq
            cur = self.cur[o] = [pkt, 0]
        pkt, idx = cur
        if idx >= len(pkt.flits):
            fail("scoreboard", f"packet {pkt.key} longer than injected ({len(pkt.flits)} flits)")
        want_last, want_w = pkt.flits[idx]
        if (last, w) != (want_last, want_w):
            fail("scoreboard", f"payload/last mismatch in packet {pkt.key} flit {idx}: "
                 f"got last={last} {w:#010x}, injected last={want_last} {want_w:#010x} "
                 f"(interleaving or corruption)")
        cur[1] += 1
        if last:
            self.delivered_pkts += 1
            self.cur[o] = None

    # ----------------------------------------------------------------- cycle
    @staticmethod
    def _fields(sig, width):
        v = int(sig.value)
        return [(v >> (width * i)) & ((1 << width) - 1) for i in range(5)]

    async def step(self):
        d = self.dut
        await FallingEdge(d.clk)
        self.cyc += 1
        occ = self._fields(d.dbg_occ, 3)
        crd = self._fields(d.dbg_credits, 3)
        ov, ol, od = int(d.out_valid.value), int(d.out_last.value), int(d.out_data.value)
        pins = [((ol >> o) & 1, (od >> (32 * o)) & M32) if (ov >> o) & 1 else None
                for o in range(5)]

        # 1. credit conservation, every cycle, every link, from register state
        for i in range(5):
            tot = (self.src_cnt[i] + (self.src_out[i] is not None) + (self.LF[i] is not None)
                   + occ[i] + self.LCin[i])
            if tot != DEPTH:
                fail("credit-conservation", f"cycle {self.cyc} input {PORT[i]}: source credits "
                     f"{self.src_cnt[i]} + flits in flight/buffered "
                     f"{tot - self.src_cnt[i] - self.LCin[i]} + credits in flight {self.LCin[i]} "
                     f"= {tot}, expected DEPTH {DEPTH}")
            tot = (crd[i] + (pins[i] is not None) + (self.LFo[i] is not None)
                   + len(self.snk_fifo[i]) + self.LCout[i])
            if tot != DEPTH:
                fail("credit-conservation", f"cycle {self.cyc} output {PORT[i]}: router credits "
                     f"{crd[i]} + flits in flight/buffered "
                     f"{tot - crd[i] - self.LCout[i]} + credits in flight {self.LCout[i]} "
                     f"= {tot}, expected DEPTH {DEPTH}")

        # 2. drive link registers onto the router
        iv = il = idat = 0
        for i in range(5):
            f = self.LF[i]
            if f is not None:
                iv |= 1 << i
                il |= f[0] << i
                idat |= f[1] << (32 * i)
                if self.t_in_first is None:
                    self.t_in_first = self.cyc
        d.in_valid.value = iv
        d.in_last.value = il
        d.in_data.value = idat
        d.out_credit.value = sum(self.LCout[o] << o for o in range(5))
        await Timer(1, unit="ns")
        icr = int(d.in_credit.value)

        # 4a. sources
        self.blocked = False
        for i in range(5):
            self.src_cnt[i] += self.LCin[i]
            dec = None
            if self.src_q[i]:
                if self.src_cnt[i] == 0:
                    self.blocked = True
                elif self.rng.random() < self.rate:
                    last, w, pkt = self.src_q[i].pop(0)
                    if pkt is not None:
                        self.outstanding[pkt.key] = pkt
                    self.src_cnt[i] -= 1
                    self.injected_flits += 1
                    dec = (last, w)
            self.LF[i] = self.src_out[i]
            self.src_out[i] = dec
            self.LCin[i] = (icr >> i) & 1

        # 4b. sinks
        for o in range(5):
            popped = 0
            if self.snk_fifo[o]:
                go = True
                if self.stall_left[o] > 0:
                    self.stall_left[o] -= 1
                    go = False
                    self.forced_go[o] = self.stall_left[o] == 0
                elif self.forced_go[o]:
                    self.forced_go[o] = False
                elif self.max_stall and self.rng.random() < self.stall_prob:
                    self.stall_left[o] = self.rng.randint(0, self.max_stall - 1)
                    self.forced_go[o] = self.stall_left[o] == 0
                    go = False
                if go:
                    self.deliver(o, self.snk_fifo[o].pop(0))
                    popped = 1
            if self.LFo[o] is not None:
                self.snk_fifo[o].append(self.LFo[o])
                if len(self.snk_fifo[o]) > DEPTH:
                    fail("credit-conservation", f"cycle {self.cyc} output {PORT[o]}: sink buffer "
                         f"overflow ({len(self.snk_fifo[o])} > DEPTH {DEPTH}): router sent without credit")
            self.LFo[o] = pins[o]
            self.LCout[o] = popped
            if pins[o] is not None:
                if self.t_out_first is None:
                    self.t_out_first = self.cyc
                self.t_out_last = self.cyc

    def idle(self):
        return (not any(self.src_q) and not any(self.src_out) and not any(
            f is not None for f in self.LF) and not any(f is not None for f in self.LFo)
            and not any(self.snk_fifo) and not any(self.LCin) and not any(self.LCout))

    async def reset(self):
        d = self.dut
        d.rst_n.value = 0
        d.in_valid.value = 0
        d.in_last.value = 0
        d.in_data.value = 0
        d.out_credit.value = 0
        for _ in range(4):
            await FallingEdge(d.clk)
        d.rst_n.value = 1

    async def run(self, label, max_cycles=3_000_000):
        """Reset, inject everything queued, drain, and apply every end-of-run check."""
        await self.reset()
        self.last_progress = self.cyc
        inj_end = bound = None
        while True:
            await self.step()
            if self.cyc > max_cycles:
                fail("watchdog", f"{label}: run exceeded {max_cycles} cycles")
            in_sys = (self.injected_flits > self.delivered_flits) or self.blocked
            if not in_sys:
                self.last_progress = self.cyc
            elif self.cyc - self.last_progress > WATCHDOG_CYCLES:
                fail("watchdog", f"{label}: no flit accepted at any output for "
                     f"{WATCHDOG_CYCLES} cycles with {self.injected_flits - self.delivered_flits} "
                     f"flits in the router/links (deadlock or lost credit)")
            if inj_end is None and not any(self.src_q):
                inj_end = self.cyc
                left = self.injected_flits - self.delivered_flits
                bound = 200 + 4 * (self.max_stall + 2) * left
            if inj_end is not None and self.cyc - inj_end > bound:
                fail("drain", f"{label}: {len(self.outstanding)} packets undrained "
                     f"{bound} cycles after injection ended")
            if (inj_end is not None and self.idle() and not self.outstanding
                    and self.injected_flits == self.delivered_flits):
                break
        delivered_at_drain = self.delivered_flits
        for _ in range(20):                 # nothing may emerge after drain
            await self.step()
        if self.delivered_flits != delivered_at_drain or self.outstanding:
            fail("scoreboard", f"{label}: flits appeared after drain (duplication)")
        if self.injected_flits != self.delivered_flits:
            fail("scoreboard", f"{label}: injected {self.injected_flits} flits, "
                 f"delivered {self.delivered_flits}")
        if self.src_cnt != [DEPTH] * 5 or any(self.snk_fifo):
            fail("credit-conservation", f"{label}: credits not restored after drain: {self.src_cnt}")
        self.dut._log.info(
            "SCOREBOARD OK [%s] DEPTH=%d: %d packets / %d flits, no loss, no duplication, in order "
            "per (src,dst), payload intact; drained %d cycles after injection end (bound %d)",
            label, DEPTH, self.delivered_pkts, self.delivered_flits, self.cyc - inj_end, bound)


def start_clock(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())


# ------------------------------------------------------------------ tests

@cocotb.test()
async def test_single_packet_each_output(dut):
    """One packet from every input to every output it can legally reach, 1 and 4 flits."""
    start_clock(dut)
    b = Bench(dut, rate=0.5, seed=11)
    pairs = 0
    outs_seen = set()
    for p in range(5):
        for o in range(5):
            dst = dest_for_output(p, o)
            if dst is None:
                continue
            for ln in (1, 4):
                b.add(p, dst, ln)
            pairs += 1
            outs_seen.add(o)
    assert outs_seen == set(range(5))
    dut._log.info("single packets: %d legal (input, output) pairs, all 5 outputs reached", pairs)
    await b.run("single-packet-each-output")


@cocotb.test()
async def test_zero_load_latency(dut):
    """Zero-load latency through the router, simulated, vs spec/noc.md section 1."""
    start_clock(dut)
    for length in (1, 4, 16):
        b = Bench(dut, rate=1.0, seed=5)
        b.add(L, (2, 1), length)
        await b.run(f"zero-load-len{length}")
        head = b.t_out_first - b.t_in_first
        tail = b.t_out_last - b.t_in_first
        verdict = ("MATCHES spec" if head == SPEC_ROUTER_CYCLES else
                   f"DIFFERS from spec by {head - SPEC_ROUTER_CYCLES:+d} cycles")
        dut._log.info(
            "SIMULATED zero-load latency, pattern=single packet Local->E into idle router, "
            "length=%d flits, DEPTH=%d: head %d cycles in router, tail %d cycles "
            "(spec/noc.md section 1: %d cycles in router) -- %s",
            length, DEPTH, head, tail, SPEC_ROUTER_CYCLES, verdict)
        if DEPTH >= 4:      # one flit/cycle behind the head needs the full credit loop
            assert tail == head + length - 1


@cocotb.test()
async def test_back_to_back_same_output(dut):
    """Back-to-back packets, mixed lengths incl. single-flit, one input to one output."""
    start_clock(dut)
    b = Bench(dut, rate=1.0, seed=21)
    for _ in range(60):
        b.add(L, (3, 1), b.rng.choice([1, 1, 2, 4, 16]))
    await b.run("back-to-back-L-to-E")


@cocotb.test()
async def test_contention_grant_held(dut):
    """Two inputs contend for one output; each packet leaves whole (grant held to last)."""
    start_clock(dut)
    b = Bench(dut, rate=1.0, seed=31)
    for _ in range(12):
        b.add(W, (3, 2), 16)
        b.add(L, (2, 0), 16)
        b.add(W, (2, 1), 1)
        b.add(L, (3, 3), 4)
    await b.run("contention-W-and-L-to-E")


@cocotb.test()
async def test_random_traffic_rates(dut):
    """Random legal traffic across rates and lengths 1/4/16, with and without sink stalls."""
    start_clock(dut)
    for k, rate in enumerate((0.05, 0.3, 0.7, 1.0)):
        stalls = (0.0, 0) if k % 2 == 0 else (0.3, 6)
        b = Bench(dut, rate=rate, stall_prob=stalls[0], max_stall=stalls[1], seed=100 + k)
        b.random_plan(range(5), 20, [1, 4, 16])
        await b.run(f"random-rate{rate}-stall{stalls[0]}")


@cocotb.test()
async def test_adversarial_all_ports(dut):
    """Spec section 5: all five inputs, 16-flit packets, rate 1.0, bounded random sink stalls."""
    start_clock(dut)
    b = Bench(dut, rate=1.0, stall_prob=0.3, max_stall=6, seed=201)
    b.random_plan(range(5), 30, [16])
    await b.run("adversarial-all-ports-random-dests")
    # hotspot: the four neighbours all send long packets to the local output
    b = Bench(dut, rate=1.0, stall_prob=0.3, max_stall=6, seed=202)
    b.random_plan([N, E, S, W], 25, [16], fixed_dest=(RX, RY))
    await b.run("adversarial-hotspot-to-local")


@cocotb.test()
async def test_throughput_uncontended(dut):
    """One flow, rate 1.0, no stalls: sustained flits/cycle at this DEPTH (simulated)."""
    start_clock(dut)
    b = Bench(dut, rate=1.0, seed=301)
    for _ in range(40):
        b.add(L, (2, 1), 16)
    await b.run("throughput-L-to-E")
    first, last = b.deliver_cycles[0], b.deliver_cycles[-1]
    thr = (len(b.deliver_cycles) - 1) / (last - first)
    dut._log.info(
        "SIMULATED throughput, pattern=single flow Local->E, rate=1.0 flits/cycle offered, "
        "length=16, no sink stalls, DEPTH=%d: %.3f flits/cycle delivered", DEPTH, thr)
    if DEPTH >= 4:
        assert thr > 0.99, f"depth {DEPTH} sustains only {thr:.3f} flit/cycle (decision 0002 expects 1.0)"
