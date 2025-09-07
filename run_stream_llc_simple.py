import argparse, math
import m5
from m5.objects import (
    System, SrcClockDomain, VoltageDomain, SystemXBar, L2XBar,
    Cache, SimpleMemory, AddrRange, AtomicSimpleCPU, Process, Root, SEWorkload
)

def mk_cache(size, assoc, cyc):
    c = Cache()
    c.size = size
    c.assoc = assoc
    c.tag_latency = cyc
    c.data_latency = cyc
    c.response_latency = cyc
    c.mshrs = 16
    c.tgts_per_mshr = 16
    return c

def mk_l1i():
    c = Cache()
    c.size = "32kB"; c.assoc = 2
    c.tag_latency = c.data_latency = c.response_latency = 2
    c.mshrs = 8; c.tgts_per_mshr = 16
    return c

def mk_l1d():
    c = Cache()
    c.size = "32kB"; c.assoc = 2
    c.tag_latency = c.data_latency = c.response_latency = 2
    c.mshrs = 16; c.tgts_per_mshr = 16
    return c

ap = argparse.ArgumentParser()
ap.add_argument("--scenario", choices=["sram","nvm","hybrid"], default="nvm",
                help="Which L3 tech to emulate")
ap.add_argument("--mode", choices=["fixed-area","fixed-latency"], default="fixed-area",
                help="Size policy for L3 (use *-size-fa in fixed-area)")
ap.add_argument("--cmd", default="bin/stream_x86_linux")

ap.add_argument("--line-size", type=int, default=64)
ap.add_argument("--mem-size", default="512MB")
ap.add_argument("--mem-lat-ns", default="40ns")

# Private L2 (to make L3 the LLC)
ap.add_argument("--l2c-size", default="256kB")
ap.add_argument("--l2c-assoc", type=int, default=8)
ap.add_argument("--l2c-cyc", type=int, default=6)

# L3 sizes / latencies
ap.add_argument("--sram-size-fa", default="2MB")
ap.add_argument("--nvm-size-fa",  default="8MB")   # e.g., 4x denser than SRAM
ap.add_argument("--hyb-sram-fa",  default="1MB")
ap.add_argument("--hyb-nvm-fa",   default="4MB")
ap.add_argument("--sram-cyc", type=int, default=10)
ap.add_argument("--nvm-cyc",  type=int, default=20)
args = ap.parse_args()

system = System()
system.clk_domain = SrcClockDomain(clock="3GHz", voltage_domain=VoltageDomain())
system.mem_mode = "atomic"                      # AtomicSimpleCPU requires atomic mode
system.mem_ranges = [AddrRange(args.mem_size)]
system.cache_line_size = int(args.line_size)

# Buses
system.membus = SystemXBar()
system.l2bus  = L2XBar()                        # L1 -> L2

# CPU
system.cpu = AtomicSimpleCPU()

# Interrupt controller (needed even in SE)
if hasattr(system.cpu, "createInterruptController"):
    system.cpu.createInterruptController()
    ic = system.cpu.interrupts[0]
    ic.pio = system.membus.mem_side_ports
    ic.int_requestor = system.membus.cpu_side_ports
    ic.int_responder = system.membus.mem_side_ports

# L1s
system.cpu.icache = mk_l1i()
system.cpu.dcache = mk_l1d()

# *** critical wiring: connect CPU ports to L1s ***
system.cpu.icache_port = system.cpu.icache.cpu_side
system.cpu.dcache_port = system.cpu.dcache.cpu_side

# L1 -> L2 bus
system.cpu.icache.mem_side = system.l2bus.cpu_side_ports
system.cpu.dcache.mem_side = system.l2bus.cpu_side_ports

# Private L2 (per-core)
system.cpu.l2c = mk_cache(args.l2c_size, args.l2c_assoc, args.l2c_cyc)
system.cpu.l2c.cpu_side = system.l2bus.mem_side_ports

# L3 (LLC)
if args.scenario in ("sram","nvm"):
    cyc  = args.sram_cyc if args.scenario=="sram" else args.nvm_cyc
    if args.mode == "fixed-area":
        size = args.sram_size_fa if args.scenario=="sram" else args.nvm_size_fa
    else:
        size = "2MB"  # simple same-capacity example for fixed-latency
    system.l3 = mk_cache(size, 16, cyc)
    # L2 -> L3 (direct)
    system.cpu.l2c.mem_side = system.l3.cpu_side
    # L3 -> memory
    system.l3.mem_side = system.membus.cpu_side_ports
    topo_str = f"L3={size}@{cyc}cyc"
else:
    # HYBRID: stripe L3 across SRAM/NVM by cache line (even=SRAM, odd=NVM)
    block_bits = int(math.log2(system.cache_line_size))  # 64B -> 6
    if args.mode == "fixed-area":
        hyb_sram = args.hyb_sram_fa
        hyb_nvm  = args.hyb_nvm_fa
    else:
        hyb_sram = "1MB"; hyb_nvm = "1MB"              # same-capacity

    l3_sram = mk_cache(hyb_sram, 16, args.sram_cyc)
    l3_nvm  = mk_cache(hyb_nvm,  16, args.nvm_cyc)

    mr = system.mem_ranges[0]
    r_sram = AddrRange(mr.start, mr.end, intlvBits=1, intlvHighBit=block_bits, intlvMatch=0)
    r_nvm  = AddrRange(mr.start, mr.end, intlvBits=1, intlvHighBit=block_bits, intlvMatch=1)
    l3_sram.addr_ranges = [r_sram]
    l3_nvm.addr_ranges  = [r_nvm]

    # Fan-out L2 -> both L3 banks via a small bus
    system.l3bus = L2XBar()
    system.cpu.l2c.mem_side = system.l3bus.cpu_side_ports
    system.l3_sram = l3_sram; system.l3_nvm = l3_nvm
    system.l3_sram.cpu_side = system.l3bus.mem_side_ports
    system.l3_nvm.cpu_side  = system.l3bus.mem_side_ports
    system.l3_sram.mem_side = system.membus.cpu_side_ports
    system.l3_nvm.mem_side  = system.membus.cpu_side_ports
    topo_str = f"L3_hybrid: SRAM={hyb_sram}@{args.sram_cyc}cyc + NVM={hyb_nvm}@{args.nvm_cyc}cyc"

# Memory
system.mem = SimpleMemory(range=system.mem_ranges[0], latency=args.mem_lat_ns)
system.mem.port = system.membus.mem_side_ports
system.system_port = system.membus.cpu_side_ports

# Workload
system.workload = SEWorkload.init_compatible(args.cmd)
proc = Process(); proc.executable = args.cmd; proc.cmd = [args.cmd]
system.cpu.workload = proc
system.cpu.createThreads()

root = Root(full_system=False, system=system)

print(f"[CONFIG] scenario={args.scenario} mode={args.mode} | {topo_str} | L2c={args.l2c_size}@{args.l2c_cyc}cyc | cmd={args.cmd}")
m5.instantiate()
print("Beginning simulation!")
event = m5.simulate(10000000000)
print(f"Exiting @ tick {m5.curTick()} because {event.getCause()}")
m5.stats.dump()

#10000000000
