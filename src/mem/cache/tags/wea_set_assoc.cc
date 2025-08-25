#include "mem/cache/tags/wea_set_assoc.hh"

#include "base/logging.hh"
#include "mem/cache/replacement_policies/base.hh"

namespace gem5 {

void
WEASetAssoc::regStats()
{
    BaseSetAssoc::regStats();

    sramAllocs  .name(name() + ".sramAllocs")
                .desc("Allocations that landed in SRAM ways");
    nvmAllocs   .name(name() + ".nvmAllocs")
                .desc("Allocations that landed in NVM ways");
    sramWriteHits.name(name() + ".sramWriteHits")
                .desc("Write hits served by lines in SRAM ways");
    nvmWriteHits.name(name() + ".nvmWriteHits")
                .desc("Write hits served by lines in NVM ways");
}

CacheBlk*
WEASetAssoc::findVictim(const CacheBlk::KeyType& key, const std::size_t size,
                        std::vector<CacheBlk*>& evict_blks,
                        const uint64_t partition_id)
{
    // All ways in this set (as ReplaceableEntry*)
    std::vector<ReplaceableEntry*> entries = indexingPolicy->getPossibleEntries(key);

    // Honor partitions if present
    if (partitionManager) {
        partitionManager->filterByPartition(entries, partition_id);
    }

    // (1) Prefer an INVALID in the SRAM band to prime SRAM early.
    for (auto *e : entries) {
        auto *blk = static_cast<CacheBlk*>(e);
        if (!blk->isValid() && blk->getWay() < _sramWays) {
            evict_blks.push_back(blk);
            return blk;
        }
    }

    // (2) Otherwise, any INVALID line (cold fill), regardless of bank.
    for (auto *e : entries) {
        auto *blk = static_cast<CacheBlk*>(e);
        if (!blk->isValid()) {
            evict_blks.push_back(blk);
            return blk;
        }
    }

    // (3) No free lines: delegate to the configured replacement policy.
    CacheBlk* victim = entries.empty() ? nullptr :
        static_cast<CacheBlk*>(replacementPolicy->getVictim(entries));
    evict_blks.push_back(victim);
    return victim;
}

void
WEASetAssoc::insertBlock(const PacketPtr pkt, CacheBlk *blk)
{
    // Let the base class do the real install & replacement-policy reset
    BaseSetAssoc::insertBlock(pkt, blk);

    // Count which bank the install ended up in
    if (blk->getWay() < _sramWays) ++sramAllocs;
    else                           ++nvmAllocs;
}

CacheBlk*
WEASetAssoc::accessBlock(const PacketPtr pkt, Cycles &lat)
{
    CacheBlk* blk = BaseSetAssoc::accessBlock(pkt, lat);

    // On write hits, count by bank as a proxy for "NVM write pressure"
    if (blk && pkt && pkt->isWrite()) {
        if (blk->getWay() < _sramWays) ++sramWriteHits;
        else                           ++nvmWriteHits;
    }

    return blk;
}

} // namespace gem5

