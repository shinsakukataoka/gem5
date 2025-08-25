// wea_rp.cc
#include "mem/cache/replacement_policies/wea_rp.hh"

#include <limits>
#include "base/logging.hh"

namespace gem5 {
namespace replacement_policy {

WEA::WEA(const Params &p)
    : Base(p)
{
    // Nothing else to init here
}

void
WEA::regStats()
{
    // Register base SimObject stats first
    SimObject::regStats();

    // Simple usage counters (handy sanity checks)
    callsTouch
        .name(name() + ".callsTouch")
        .desc("Number of touch() invocations");

    callsReset
        .name(name() + ".callsReset")
        .desc("Number of reset() invocations");

    callsGetVictim
        .name(name() + ".callsGetVictim")
        .desc("Number of getVictim() invocations");

    // Policy tallies (these will stay zero until you wire real updates)
    sramAllocs
        .name(name() + ".sramAllocs")
        .desc("Allocations that chose SRAM bank");

    nvmAllocs
        .name(name() + ".nvmAllocs")
        .desc("Allocations that chose NVM bank");

    promotions
        .name(name() + ".promotions")
        .desc("Promotions NVM->SRAM");

    bypasses
        .name(name() + ".bypasses")
        .desc("Bypasses (if enabled)");
}

void
WEA::invalidate(const std::shared_ptr<ReplacementData> &d)
{
    auto *rd = asWEA(d);
    rd->lastTouchTick = 0;
}

void
WEA::touch(const std::shared_ptr<ReplacementData> &d, const PacketPtr)
{
    callsTouch++;
    auto *rd = asWEA(d);
    rd->lastTouchTick = curTick();
}

void
WEA::touch(const std::shared_ptr<ReplacementData> &d) const
{
    callsTouch++;
    auto *rd = asWEA(d);
    rd->lastTouchTick = curTick();
}

void
WEA::reset(const std::shared_ptr<ReplacementData> &d, const PacketPtr)
{
    callsReset++;
    auto *rd = asWEA(d);
    rd->lastTouchTick = curTick();
}

void
WEA::reset(const std::shared_ptr<ReplacementData> &d) const
{
    callsReset++;
    auto *rd = asWEA(d);
    rd->lastTouchTick = curTick();
}

ReplaceableEntry*
WEA::getVictim(const ReplacementCandidates& candidates) const
{
    callsGetVictim++;

    fatal_if(candidates.empty(), "WEA: no replacement candidates!");

    // Oldest lastTouchTick wins (LRU-ish placeholder)
    ReplaceableEntry* victim = candidates[0];
    Tick oldest = std::numeric_limits<Tick>::max();

    for (auto *entry : candidates) {
        const auto *rd = asWEAConst(entry->replacementData);
        if (rd->lastTouchTick < oldest) {
            oldest = rd->lastTouchTick;
            victim = entry;
        }
    }
    return victim;
}

std::shared_ptr<ReplacementData>
WEA::instantiateEntry()
{
    return std::shared_ptr<ReplacementData>(new WEAReplData());
}

} // namespace replacement_policy
} // namespace gem5

