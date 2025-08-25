from m5.params import *
from m5.objects import BaseSetAssoc

class WEASetAssoc(BaseSetAssoc):
    type = "WEASetAssoc"
    cxx_class = "gem5::WEASetAssoc"
    cxx_header = "mem/cache/tags/wea_set_assoc.hh"

    # Extra knobs on top of BaseSetAssoc
    sram_ways      = Param.Unsigned(0, "Low-numbered ways treated as SRAM")
    mode           = Param.String("wea", "Policy mode: 'wea' or 'count'")
    count_window   = Param.Unsigned(16384, "Decay window (touches) for COUNT mode")
    count_threshold= Param.Unsigned(60, "Percent writes to prefer SRAM in COUNT mode")

