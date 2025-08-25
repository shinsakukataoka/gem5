// wea_rp.hh
#ifndef __MEM_CACHE_REPLACEMENT_POLICIES_WEA_RP_HH__
#define __MEM_CACHE_REPLACEMENT_POLICIES_WEA_RP_HH__

#include <memory>
#include <vector>
#include <cstdint>

#include "base/statistics.hh"  // <- modern stats API
#include "mem/cache/replacement_policies/base.hh"
#include "mem/cache/replacement_policies/replaceable_entry.hh"
#include "mem/packet.hh"
#include "params/WEA.hh"
#include "sim/cur_tick.hh"
#include "sim/sim_object.hh"

namespace gem5 {
namespace replacement_policy {

class WEAReplData : public ReplacementData
{
  public:
    // a tiny placeholder state so we can pick a victim deterministically
    mutable Tick lastTouchTick;

    WEAReplData() : lastTouchTick(0) {}
};

/**
 * WEA replacement policy – placeholder shell with counters wired up.
 * (Victim choice here is simple LRU-by-timestamp just to be safe.)
 */
class WEA : public Base
{
  public:
    using Params = WEAParams;
    WEA(const Params &p);

    void invalidate(const std::shared_ptr<ReplacementData> &d) override;
    void touch(const std::shared_ptr<ReplacementData> &d,
               const PacketPtr pkt) override;
    void touch(const std::shared_ptr<ReplacementData> &d) const override;
    void reset(const std::shared_ptr<ReplacementData> &d,
               const PacketPtr pkt) override;
    void reset(const std::shared_ptr<ReplacementData> &d) const override;

    ReplaceableEntry* getVictim(
        const ReplacementCandidates& candidates) const override;

    std::shared_ptr<ReplacementData> instantiateEntry() override;

    // Stats registration
    void regStats() override;

  private:
    // Small helper to access our per-line data
    static inline WEAReplData* asWEA(const std::shared_ptr<ReplacementData>& d)
    {
        return static_cast<WEAReplData*>(d.get());
    }
    static inline const WEAReplData* asWEAConst(
        const std::shared_ptr<ReplacementData>& d)
    {
        return static_cast<const WEAReplData*>(d.get());
    }

    // Lightweight counters so you can grep them in stats.txt
    mutable statistics::Scalar callsTouch;
    mutable statistics::Scalar callsReset;
    mutable statistics::Scalar callsGetVictim;

    // Placeholders for your policy-level tallies (they’ll show up in stats)
    mutable statistics::Scalar sramAllocs;
    mutable statistics::Scalar nvmAllocs;
    mutable statistics::Scalar promotions;
    mutable statistics::Scalar bypasses;
};

} // namespace replacement_policy
} // namespace gem5

#endif // __MEM_CACHE_REPLACEMENT_POLICIES_WEA_RP_HH__

