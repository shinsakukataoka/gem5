# src/mem/cache/tags/WEASetAssoc.py
from m5.params import *
from m5.objects import BaseSetAssoc

class WEASetAssoc(BaseSetAssoc):
    type = 'WEASetAssoc'
    cxx_class = 'gem5::WEASetAssoc'
    cxx_header = 'mem/cache/tags/wea_set_assoc.hh'
    abstract = False

    # Number of SRAM ways per set (0 => all NVM, assoc => all SRAM)
    sram_ways = Param.Unsigned(0, "Number of SRAM ways per set")

