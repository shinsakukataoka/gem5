# run_l2_wea.py
import argparse
import m5
from m5.objects import (
    System, SrcClockDomain, VoltageDomain, SystemXBar, L2XBar,
    Cache, SimpleMemory, AddrRange, TimingSimpleCPU, Process, Root, SEWorkload
)

# Optional: custom tag store
try:
    from m5.objects import WEASetAssoc
except Exception:
    WEASetAssoc = None

ap = argparse.ArgumentParser()
ap.add_argument("--rp", choices=["lru", "wea"], default="wea",
                help="L2 tag store: default SetAssociative+LRU or WEASetAssoc")
ap.add_argument("--sram-ways", type=int, default=4,
                help="WEASetAssoc: low-numbered ways treated as SRAM")
ap.add_argument("--line-size", type=int, default=64)
ap.add_argument("--l1i-size", default="32kB")
ap.add_argument("--l1d-size", default="32kB")
ap.add_argument("--l1i-assoc", type=int, default=2)
ap.add_argument("--l1d-assoc", type=int, default=2)
ap.add_argument("--l2-size", default="1MB")
ap.add_argument("--l2-assoc", type=int, default=8)
ap.add_argument("--cmd", default="tests/test-progs/hello/bin/x86/linux/hello")
args = ap.parse_args()

# --- Tiny L1 caches (classic) ---
class L1ICache(Cache):
    def __init__(self, size="32kB", assoc=2):
        super().__init__()
        self.size = size; self.assoc = assoc
        self.tag_latency = 2; self.data_latency = 2; self.response_latency = 2
        self.mshrs = 8; self.tgts_per_mshr = 16

class L1DCache(Cache):
    def __init__(self, size="32kB", assoc=2):
        super().__init__()
        self.size = size; self.assoc = assoc
        self.tag_latency = 2; self.data_latency = 2; self.response_latency = 2
        self.mshrs = 16; self.tgts_per_mshr = 16

# --- System ---
system = System()
system.clk_domain = SrcClockDomain(clock="3GHz", voltage_domain=VoltageDomain())
system.mem_mode = "timing"
system.mem_ranges = [AddrRange("512MB")]
system.cache_line_size = int(args.line_size)

# Buses
system.membus = SystemXBar()
system.l2bus  = L2XBar()

# CPU
system.cpu = TimingSimpleCPU()
if hasattr(system.cpu, "createInterruptController"):
    system.cpu.createInterruptController()
    ic = system.cpu.interrupts[0]
    ic.pio = system.membus.mem_side_ports
    ic.int_requestor = system.membus.cpu_side_ports
    ic.int_responder = system.membus.mem_side_ports

# L1s
system.cpu.icache = L1ICache(size=args.l1i_size, assoc=int(args.l1i_assoc))
system.cpu.dcache = L1DCache(size=args.l1d_size, assoc=int(args.l1d_assoc))
system.cpu.icache_port = system.cpu.icache.cpu_side
system.cpu.dcache_port = system.cpu.dcache.cpu_side
system.cpu.icache.mem_side = system.l2bus.cpu_side_ports
system.cpu.dcache.mem_side = system.l2bus.cpu_side_ports

# L2
system.l2 = Cache()
system.l2.size = args.l2_size
system.l2.assoc = int(args.l2_assoc)
system.l2.tag_latency = 20
system.l2.data_latency = 20
system.l2.response_latency = 20
system.l2.mshrs = 64
system.l2.tgts_per_mshr = 16

# Choose tag store
tag_str = "SetAssociative (default LRU)"
if args.rp == "wea":
    if WEASetAssoc is None:
        raise RuntimeError("WEASetAssoc not found. Rebuild with WEASetAssoc.py + C++ files.")
    # Clamp sram_ways to [0, assoc]
    sram_ways = max(0, min(int(args.sram_ways), system.l2.assoc))
    system.l2.tags = WEASetAssoc(sram_ways=sram_ways)
    tag_str = f"WEASetAssoc(sram_ways={sram_ways})"

# L2 <-> buses
system.l2.cpu_side = system.l2bus.mem_side_ports
system.l2.mem_side = system.membus.cpu_side_ports

# Memory & system port
system.mem = SimpleMemory(range=system.mem_ranges[0], latency="40ns")
system.mem.port = system.membus.mem_side_ports
system.system_port = system.membus.cpu_side_ports

# Workload
system.workload = SEWorkload.init_compatible(args.cmd)
proc = Process(); proc.executable = args.cmd; proc.cmd = [args.cmd]
system.cpu.workload = proc
system.cpu.createThreads()

root = Root(full_system=False, system=system)

# --- Loud banner so you can verify the config in simout.txt ---
print(f"[CONFIG] L2 tags = {tag_str}; assoc={system.l2.assoc}; "
      f"line={system.cache_line_size}B; size={system.l2.size}; cmd={args.cmd}")
print(f"[CONFIG] L2 tags class = {type(system.l2.tags).__name__}")

m5.instantiate()
print("Beginning simulation!")
event = m5.simulate()
print(f"Exiting @ tick {m5.curTick()} because {event.getCause()}")
m5.stats.dump()

