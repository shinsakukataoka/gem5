#include "mem/cache/tags/wea_set_assoc.hh"

#include <algorithm>
#include "base/logging.hh"
#include "mem/cache/replacement_policies/replaceable_entry.hh"

namespace gem5
{

WEASetAssoc::WEASetAssoc(const Params &p)
    : BaseSetAssoc(p),
      mode(p.mode == "count" ? MODE_COUNT : MODE_WEA),
      sramWays(std::min<unsigned>(p.sram_ways, allocAssoc)),
      countWindow(p.count_window),
      countThreshold(std::min<unsigned>(p.count_threshold, 100))
{
    // nothing else
}

void
WEASetAssoc::regStats()
{
    BaseSetAssoc::regStats();

    sramAllocs
        .name(name() + ".sramAllocs")
        .desc("Allocations that landed in SRAM ways");
    nvmAllocs
        .name(name() + ".nvmAllocs")
        .desc("Allocations that landed in NVM ways");
    sramWriteHits
        .name(name() + ".sramWriteHits")
        .desc("Write hits served by lines in SRAM ways");
    nvmWriteHits
        .name(name() + ".nvmWriteHits")
        .desc("Write hits served by lines in NVM ways");
}

CacheBlk*
WEASetAssoc::accessBlock(const PacketPtr pkt, Cycles &lat)
{
    CacheBlk* blk = BaseSetAssoc::accessBlock(pkt, lat);
    if (!blk || !pkt)
        return blk;

    // Update simple per-set counters (used by COUNT mode)
    const uint32_t set = blk->getSet();
    auto &ctr = setCtrs[set];
    ctr.touches++;
    if (pkt->isWrite()) {
        ctr.writes++;
        // Count write hits by bank
        const uint8_t bucket = static_cast<uint8_t>((pkt->getAddr() >> 6) & 0x7);
        ctr.dmask |= static_cast<uint8_t>(1u << bucket);
        if (blk->getWay() < sramWays) sramWriteHits++;
        else                          nvmWriteHits++;
    }

    // Periodic decay to keep "recent" behavior
    if (countWindow && ctr.touches >= countWindow) {
        ctr.touches = (ctr.touches + 1) / 2;
        ctr.writes  = ctr.writes / 2;
        ctr.dmask   = static_cast<uint8_t>(ctr.dmask >> 1);
    }

    return blk;
}

bool
WEASetAssoc::preferSRAM_COUNT(uint32_t set) const
{
    auto it = setCtrs.find(set);
    if (it == setCtrs.end()) return false; // default to NVM until we see writes
    const auto &c = it->second;
    if (c.touches == 0) return false;
    const unsigned pct = (100u * c.writes) / c.touches;
    return pct >= countThreshold && sramWays > 0;
}

bool
WEASetAssoc::preferSRAM_WEA(uint32_t set) const
{
    auto it = setCtrs.find(set);
    if (it == setCtrs.end() || sramWays == 0)
        return false;

    const unsigned distinct = popcount8(it->second.dmask);
    return distinct >= 2;
}

CacheBlk*
WEASetAssoc::findVictim(const CacheBlk::KeyType& key,
                        const std::size_t size,
                        std::vector<CacheBlk*>& evict_blks,
                        const uint64_t partition_id)
{
    // Start from all candidate entries in this set
    std::vector<ReplaceableEntry*> entries =
        indexingPolicy->getPossibleEntries(key);

    if (partitionManager) {
        partitionManager->filterByPartition(entries, partition_id);
    }

    if (entries.empty()) {
        evict_blks.push_back(nullptr);
        return nullptr;
    }

    // All candidates are in the same set — get its id from the first one
    const uint32_t set = static_cast<CacheBlk*>(entries.front())->getSet();

    // Decide preferred bank
    bool pickSRAM = false;
    switch (mode) {
        case MODE_COUNT: pickSRAM = preferSRAM_COUNT(set); break;
        case MODE_WEA:   pickSRAM = preferSRAM_WEA(set);   break;
    }


    // If we prefer a bank and there’s a free line there, take it immediately.
    if (pickSRAM && sramWays > 0) {
        for (auto *e : entries) {
            auto *b = static_cast<CacheBlk*>(e);
            if (!b->isValid() && b->getWay() < sramWays) {
                evict_blks.push_back(b);
                return b;
            }
        }
    } else {
        for (auto *e : entries) {
            auto *b = static_cast<CacheBlk*>(e);
            if (!b->isValid() && b->getWay() >= sramWays) {
                evict_blks.push_back(b);
                return b;
            }
        }
    }
    // Any invalid anywhere (don’t stall on full preferred bank at cold start)
    for (auto *e : entries) {
        auto *b = static_cast<CacheBlk*>(e);
        if (!b->isValid()) { evict_blks.push_back(b); return b; }
    }



    // Build the subset for the preferred bank
    std::vector<ReplaceableEntry*> subset;
    if (pickSRAM && sramWays > 0) {
        for (auto *e : entries)
            if (e->getWay() < sramWays) subset.push_back(e);
    } else {
        for (auto *e : entries)
            if (e->getWay() >= sramWays) subset.push_back(e);
    }

    // Fallback if that bank has no free candidates (e.g., sramWays==0 or full)
    if (subset.empty()) subset = entries;

    CacheBlk* victim = static_cast<CacheBlk*>(
        replacementPolicy->getVictim(subset));

    evict_blks.push_back(victim);
    return victim;
}

void
WEASetAssoc::insertBlock(const PacketPtr pkt, CacheBlk *blk)
{
    // 1) Do the actual install + RP reset
    BaseSetAssoc::insertBlock(pkt, blk);


    // Update per-set counters on fills too (miss path)
    const uint32_t set = blk->getSet();
    auto &ctr = setCtrs[set];
    ctr.touches++;
    if (pkt && pkt->isWrite()) {
        ctr.writes++;
        const uint8_t bucket =
            static_cast<uint8_t>((pkt->getAddr() >> 6) & 0x7);
        ctr.dmask |= static_cast<uint8_t>(1u << bucket);
    }
    // Keep the window "recent"
    if (countWindow && ctr.touches >= countWindow) {
        ctr.touches = (ctr.touches + 1) / 2;
        ctr.writes  = ctr.writes / 2;
        ctr.dmask   = static_cast<uint8_t>(ctr.dmask >> 1);
    }


    // 2) Update WEA/COUNT set counters on installs too (not just hits)
    if (pkt) {
        auto &ctr = setCtrs[blk->getSet()];
        ctr.touches++;
        if (pkt->isWrite()) {
            ctr.writes++;
            const uint8_t bucket =
                static_cast<uint8_t>((pkt->getAddr() >> 6) & 0x7);
            ctr.dmask |= static_cast<uint8_t>(1u << bucket);
        }
    }

    // 3) Count where the install landed
    if (blk->getWay() < sramWays) sramAllocs++;
    else                          nvmAllocs++;
}


} // namespace gem5

