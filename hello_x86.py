from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.cachehierarchies.classic.private_l1_shared_l2_cache_hierarchy import (
    PrivateL1SharedL2CacheHierarchy,
)
from gem5.components.memory.single_channel import SingleChannelDDR3_1600
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.components.processors.cpu_types import CPUTypes
from gem5.isas import ISA
from gem5.simulate.simulator import Simulator

# Works on v25+ (and v23+) — import locate obtain_resource
try:
    from gem5.resources.resource import obtain_resource
except ImportError:
    from gem5.resources.gem5_resource import obtain_resource  # older path

cache = PrivateL1SharedL2CacheHierarchy(
    l1i_size="32kB", l1i_assoc=2,
    l1d_size="32kB", l1d_assoc=2,
    l2_size="1MB",  l2_assoc=8,
)
memory = SingleChannelDDR3_1600(size="512MB")
cpu = SimpleProcessor(cpu_type=CPUTypes.TIMING, isa=ISA.X86, num_cores=1)

board = SimpleBoard(clk_freq="3GHz", processor=cpu, memory=memory, cache_hierarchy=cache)

# ✅ use a gem5 resource (will auto-download on first run)
hello = obtain_resource("x86-hello64-static")
board.set_se_binary_workload(hello)

Simulator(board=board).run()

