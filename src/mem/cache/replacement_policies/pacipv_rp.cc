/**
 * Copyright (c) 2018-2020 Inria
 * Copyright (c) 2026 Divyam
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are
 * met: redistributions of source code must retain the above copyright
 * notice, this list of conditions and the following disclaimer;
 * redistributions in binary form must reproduce the above copyright
 * notice, this list of conditions and the following disclaimer in the
 * documentation and/or other materials provided with the distribution;
 * neither the name of the copyright holders nor the names of its
 * contributors may be used to endorse or promote products derived from
 * this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */
#include "mem/cache/replacement_policies/pacipv_rp.hh"

#include <cassert>
#include <memory>

#include "base/logging.hh" // For fatal_if
#include "params/PACIPVRP.hh"

namespace gem5
{

namespace replacement_policy
{

PACIPV::PACIPV(const Params &p)
  : Base(p), numRRPVBits(p.num_bits), demandIPV(p.demand_ipv),
    prefetchIPV(p.prefetch_ipv)
{
    fatal_if(numRRPVBits <= 0, "There should be at least one bit per RRPV.\n");

    // An IPV has one entry per RRPV value plus one insertion entry
    const unsigned max_rrpv = (1 << numRRPVBits) - 1;
    for (const auto *ipv : {&demandIPV, &prefetchIPV}) {
        fatal_if(ipv->size() != max_rrpv + 2,
                 "Each PACIPV IPV needs %d entries.\n", max_rrpv + 2);
        for (const unsigned value : *ipv) {
            fatal_if(value > max_rrpv,
                     "PACIPV IPV value %d is larger than the max RRPV %d.\n",
                     value, max_rrpv);
        }
    }
}

const std::vector<unsigned>&
PACIPV::selectIPV(const PacketPtr pkt) const
{
    // Lower caches see prefetch misses as plain reads, so check the
    // request flag rather than the packet command
    if (pkt && pkt->req && pkt->req->isPrefetch()) {
        return prefetchIPV;
    }
    return demandIPV;
}

void
PACIPV::promote(const std::shared_ptr<ReplacementData>& replacement_data,
                const std::vector<unsigned>& ipv) const
{
    std::shared_ptr<PACIPVReplData> casted_replacement_data =
        std::static_pointer_cast<PACIPVReplData>(replacement_data);

    // RRPV p becomes ipv[p]
    const unsigned current_rrpv = casted_replacement_data->rrpv;
    casted_replacement_data->rrpv.reset();
    casted_replacement_data->rrpv += ipv[current_rrpv];
}

void
PACIPV::insert(const std::shared_ptr<ReplacementData>& replacement_data,
               const std::vector<unsigned>& ipv) const
{
    std::shared_ptr<PACIPVReplData> casted_replacement_data =
        std::static_pointer_cast<PACIPVReplData>(replacement_data);

    // The last IPV element is the insertion RRPV
    casted_replacement_data->rrpv.reset();
    casted_replacement_data->rrpv += ipv.back();

    // Mark entry as ready to be used
    casted_replacement_data->valid = true;
}

void
PACIPV::invalidate(const std::shared_ptr<ReplacementData>& replacement_data)
{
    std::shared_ptr<PACIPVReplData> casted_replacement_data =
        std::static_pointer_cast<PACIPVReplData>(replacement_data);

    // Invalidate entry
    casted_replacement_data->valid = false;
}

void
PACIPV::touch(const std::shared_ptr<ReplacementData>& replacement_data,
              const PacketPtr pkt)
{
    promote(replacement_data, selectIPV(pkt));
}

void
PACIPV::touch(const std::shared_ptr<ReplacementData>& replacement_data) const
{
    promote(replacement_data, demandIPV);
}

void
PACIPV::reset(const std::shared_ptr<ReplacementData>& replacement_data,
              const PacketPtr pkt)
{
    insert(replacement_data, selectIPV(pkt));
}

void
PACIPV::reset(const std::shared_ptr<ReplacementData>& replacement_data) const
{
    insert(replacement_data, demandIPV);
}

ReplaceableEntry*
PACIPV::getVictim(const ReplacementCandidates& candidates) const
{
    // There must be at least one replacement candidate
    assert(candidates.size() > 0);

    // Use first candidate as dummy victim
    ReplaceableEntry* victim = candidates[0];

    // Store victim->rrpv in a variable to improve code readability
    int victim_RRPV = std::static_pointer_cast<PACIPVReplData>(
                        victim->replacementData)->rrpv;

    // Visit all candidates to find victim
    for (const auto& candidate : candidates) {
        std::shared_ptr<PACIPVReplData> candidate_repl_data =
            std::static_pointer_cast<PACIPVReplData>(
                candidate->replacementData);

        // Stop searching for victims if an invalid entry is found
        if (!candidate_repl_data->valid) {
            return candidate;
        }

        // Update victim entry if necessary
        int candidate_RRPV = candidate_repl_data->rrpv;
        if (candidate_RRPV > victim_RRPV) {
            victim = candidate;
            victim_RRPV = candidate_RRPV;
        }
    }

    // Get difference of victim's RRPV to the highest possible RRPV in
    // order to update the RRPV of all the other entries accordingly
    int diff = std::static_pointer_cast<PACIPVReplData>(
        victim->replacementData)->rrpv.saturate();

    // No need to update RRPV if there is no difference
    if (diff > 0){
        // Update RRPV of all candidates
        for (const auto& candidate : candidates) {
            std::static_pointer_cast<PACIPVReplData>(
                candidate->replacementData)->rrpv += diff;
        }
    }

    return victim;
}

std::shared_ptr<ReplacementData>
PACIPV::instantiateEntry()
{
    return std::shared_ptr<ReplacementData>(new PACIPVReplData(numRRPVBits));
}

} // namespace replacement_policy
} // namespace gem5