# run_wea_hello_x86.py
from gem5.isas import ISA
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.cachehierarchies.classic.private_l1_shared_l2_cache_hierarchy import \
    PrivateL1SharedL2CacheHierarchy
from gem5.components.memory.single_channel import SingleChannelDDR3_1600
from gem5.components.boards.simple_board import SimpleBoard
from gem5.simulate.simulator import Simulator
from gem5.resources.resource import obtain_resource
from m5.objects import WEA
from m5.util import convert

# --- Cache + system config ---
CACHELINE = 64

cache_h = PrivateL1SharedL2CacheHierarchy(
    l1i_size="32kB", l1i_assoc=4,
    l1d_size="32kB", l1d_assoc=8,
    l2_size="2MB",  l2_assoc=16
)

mem = SingleChannelDDR3_1600(size="4GB")
proc = SimpleProcessor(cpu_type=CPUTypes.O3, isa=ISA.X86, num_cores=1)
board = SimpleBoard(
    clk_freq="3GHz",
    processor=proc,
    memory=mem,
    cache_hierarchy=cache_h,
    cache_line_size=CACHELINE
)

# --- Attach WEA to L2 (LLC in this setup) ---
l2_size = "2MB"
l2_assoc = 16
num_sets = (convert.toMemorySize(l2_size) // CACHELINE) // l2_assoc

# Access the underlying L2 cache SimObject
if hasattr(cache_h, "l2"):
    l2 = cache_h.l2
elif hasattr(cache_h, "get_l2"):
    l2 = cache_h.get_l2().get_cache()
else:
    raise RuntimeError("Could not get L2 cache object from hierarchy")

l2.replacement_policy = WEA(
    numSets=num_sets, assoc=l2_assoc, sramWays=4, lineSize=CACHELINE,
    sampleShift=5, kHH=4, bitsetBits=512, windowWrites=1024,
    rripMax=3, rrpvInsertS=1, rrpvInsertN=3,
    tUp=0.65, tDown=0.45, alpha=0.6, beta=0.4, gamma=0.0,
    enableBypass=False, promoteN=2
)

# --- Workload ---
hello = obtain_resource("x86-hello64-static")
board.set_se_binary_workload(hello)

# --- Run ---
sim = Simulator(board=board)
sim.run()

