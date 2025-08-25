#ifndef __MEM_CACHE_TAGS_WEA_SET_ASSOC_HH__
#define __MEM_CACHE_TAGS_WEA_SET_ASSOC_HH__

#include <unordered_map>
#include <cstdint>

#include "base/statistics.hh"
#include "mem/cache/tags/base_set_assoc.hh"
#include "params/WEASetAssoc.hh"

namespace gem5
{

class WEASetAssoc : public BaseSetAssoc
{
  public:
    using Params = WEASetAssocParams;
    explicit WEASetAssoc(const Params &p);

    void regStats() override;

    CacheBlk* accessBlock(const PacketPtr pkt, Cycles &lat) override;

    CacheBlk* findVictim(const CacheBlk::KeyType& key,
                         const std::size_t size,
                         std::vector<CacheBlk*>& evict_blks,
                         const uint64_t partition_id=0) override;

    void insertBlock(const PacketPtr pkt, CacheBlk *blk) override;

  private:
    enum Mode { MODE_COUNT, MODE_WEA } mode;

    // Low-numbered ways considered “SRAM”
    unsigned sramWays;
    // Decay window (#touches) for COUNT mode
    unsigned countWindow;
    // % writes threshold to prefer SRAM in COUNT mode
    unsigned countThreshold;

    struct SetCtr {
        uint64_t touches = 0;
        uint64_t writes  = 0;
        uint8_t  dmask   = 0;   // 8-bit “distinct write” footprint
    };
    mutable std::unordered_map<uint32_t, SetCtr> setCtrs;

    // popcount for our 8-bit footprint
    static inline unsigned popcount8(uint8_t x) {
        x = x - ((x >> 1) & 0x55);
        x = (x & 0x33) + ((x >> 2) & 0x33);
        return ((x + (x >> 4)) & 0x0F);
    }

    // simple threshold: "enough distinct write activity"
    static constexpr unsigned WEA_DISTINCT_THRESH = 4;

    bool preferSRAM_COUNT(uint32_t set) const;
    bool preferSRAM_WEA(uint32_t set) const;

    // stats
    statistics::Scalar sramAllocs;
    statistics::Scalar nvmAllocs;
    statistics::Scalar sramWriteHits;
    statistics::Scalar nvmWriteHits;
};

} // namespace gem5

#endif // __MEM_CACHE_TAGS_WEA_SET_ASSOC_HH__
