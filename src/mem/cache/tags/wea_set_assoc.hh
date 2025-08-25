#ifndef __MEM_CACHE_TAGS_WEA_SET_ASSOC_HH__
#define __MEM_CACHE_TAGS_WEA_SET_ASSOC_HH__

#include <vector>

#include "base/statistics.hh"
#include "mem/cache/cache_blk.hh"
#include "mem/cache/replacement_policies/replaceable_entry.hh"
#include "mem/cache/tags/base_set_assoc.hh"
#include "params/WEASetAssoc.hh"   // <-- generates WEASetAssocParams

namespace gem5 {

/**
 * WEASetAssoc: a BaseSetAssoc drop-in that
 *  - prefers SRAM ways for cold installs
 *  - counts installs to SRAM/NVM
 *  - counts write hits by bank as a quick proxy for "NVM write pressure"
 *
 * The actual replacement choice is still delegated to the configured
 * replacement policy, we only filter the candidate pool a bit.
 */
class WEASetAssoc : public BaseSetAssoc
{
  public:
    using Params = WEASetAssocParams;

    explicit WEASetAssoc(const Params &p)
        : BaseSetAssoc(p), _sramWays(p.sram_ways) {}

    void regStats() override;

    CacheBlk* findVictim(const CacheBlk::KeyType& key, const std::size_t size,
                         std::vector<CacheBlk*>& evict_blks,
                         const uint64_t partition_id=0) override;

    void insertBlock(const PacketPtr pkt, CacheBlk *blk) override;

    CacheBlk* accessBlock(const PacketPtr pkt, Cycles &lat) override;

  private:
    unsigned _sramWays;

    // Stats will show up under:  system.l2.tags.*
    statistics::Scalar sramAllocs;
    statistics::Scalar nvmAllocs;
    statistics::Scalar sramWriteHits;
    statistics::Scalar nvmWriteHits;
};

} // namespace gem5

#endif // __MEM_CACHE_TAGS_WEA_SET_ASSOC_HH__

