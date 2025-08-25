# src/mem/cache/replacement_policies/WEA.py
from m5.objects import BaseReplacementPolicy
from m5.params import *

class WEA(BaseReplacementPolicy):
    type = "WEA"
    cxx_class = "gem5::replacement_policy::WEA"
    cxx_header = "mem/cache/replacement_policies/wea_rp.hh"

    # Core cache geometry
    numSets     = Param.Unsigned(1,   "Number of sets in the cache")
    assoc       = Param.Unsigned(1,   "Associativity")
    sramWays    = Param.Unsigned(4,   "SRAM ways per set")
    lineSize    = Param.Unsigned(64,  "Cache line size (bytes)")

    # Estimator knobs
    sampleShift = Param.Unsigned(5,   "Sample 1/(2^shift) sets")
    kHH         = Param.Unsigned(4,   "Top-K heavy hitters")
    bitsetBits  = Param.Unsigned(512, "Bitset size for linear counting")
    windowWrites= Param.Unsigned(1024,"Window size in writes")

    # DRRIP knobs
    rripMax     = Param.Unsigned(3,   "Max RRPV")
    rrpvInsertS = Param.Unsigned(1,   "Insert RRPV for SRAM")
    rrpvInsertN = Param.Unsigned(3,   "Insert RRPV for NVM")

    # Scoring / thresholds
    tUp         = Param.Float(0.65,   "SRAM-lean threshold")
    tDown       = Param.Float(0.45,   "NVM-lean threshold")
    alpha       = Param.Float(0.6,    "Weight for entropy")
    beta        = Param.Float(0.3,    "Weight for footprint")
    gamma       = Param.Float(0.1,    "Weight for intensity")

    # Policy toggles
    enableBypass= Param.Bool(False,   "Allow NVM bypass for streams")
    promoteN    = Param.Unsigned(2,   "Writes in NVM before promotion")
