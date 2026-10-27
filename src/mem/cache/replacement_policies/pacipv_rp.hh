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

/**
 * @file
 * Declaration of the Prefetch Aware Coarse-grained Insertion and Promotion
 * Vectors (PACIPV) replacement policy.
 *
 * PACIPV keeps a 2-bit Re-Reference Prediction Value (RRPV) per entry, like
 * SRRIP, but insertion and promotion are driven by two Insertion/Promotion
 * Vectors (IPVs): one for demand accesses and one for prefetch accesses.
 * For an IPV V[0..n], an entry hit at RRPV p gets the new RRPV V[p], and an
 * inserted entry gets V[n]. Victim selection and aging are the same as SRRIP.
 *
 * Mostofi et al., "Light-weight Cache Replacement for Instruction Heavy
 * Workloads", ISCA 2025.
 */

#ifndef __MEM_CACHE_REPLACEMENT_POLICIES_PACIPV_RP_HH__
#define __MEM_CACHE_REPLACEMENT_POLICIES_PACIPV_RP_HH__

#include <vector>

#include "base/sat_counter.hh"
#include "mem/cache/replacement_policies/base.hh"

namespace gem5
{

struct PACIPVRPParams;

namespace replacement_policy
{

class PACIPV : public Base
{
  protected:
    /** PACIPV-specific implementation of replacement data. */
    struct PACIPVReplData : ReplacementData
    {
        /** Re-Reference Prediction Value. 0 is near, max is distant. */
        SatCounter8 rrpv;

        /** Whether the entry is valid. */
        bool valid;

        /**
         * Default constructor. Invalidate data.
         */
        PACIPVReplData(const int num_bits)
            : rrpv(num_bits), valid(false)
        {
        }
    };

    /** Number of RRPV bits. */
    const unsigned numRRPVBits;

    /** IPV used for demand accesses. */
    const std::vector<unsigned> demandIPV;

    /** IPV used for prefetch accesses. */
    const std::vector<unsigned> prefetchIPV;

    /**
     * Choose the IPV for an access. Accesses without a packet are treated
     * as demands.
     *
     * @param pkt Packet that generated the access, may be nullptr.
     * @return The IPV to use.
     */
    const std::vector<unsigned>& selectIPV(const PacketPtr pkt) const;

    /**
     * Promote an entry on a hit: RRPV p becomes ipv[p].
     *
     * @param replacement_data Replacement data to be promoted.
     * @param ipv IPV to use.
     */
    void promote(const std::shared_ptr<ReplacementData>& replacement_data,
                 const std::vector<unsigned>& ipv) const;

    /**
     * Insert an entry: RRPV becomes the last element of the IPV.
     *
     * @param replacement_data Replacement data to be inserted.
     * @param ipv IPV to use.
     */
    void insert(const std::shared_ptr<ReplacementData>& replacement_data,
                const std::vector<unsigned>& ipv) const;

  public:
    typedef PACIPVRPParams Params;
    PACIPV(const Params &p);
    ~PACIPV() = default;

    /**
     * Invalidate replacement data to set it as the next probable victim.
     *
     * @param replacement_data Replacement data to be invalidated.
     */
    void invalidate(const std::shared_ptr<ReplacementData>& replacement_data)
                                                                    override;

    /**
     * Touch an entry on a hit, using the demand or prefetch IPV.
     *
     * @param replacement_data Replacement data to be touched.
     * @param pkt Packet that generated this hit.
     */
    void touch(const std::shared_ptr<ReplacementData>& replacement_data,
        const PacketPtr pkt) override;
    void touch(const std::shared_ptr<ReplacementData>& replacement_data) const
        override;

    /**
     * Reset replacement data when an entry is inserted, using the demand or
     * prefetch IPV.
     *
     * @param replacement_data Replacement data to be reset.
     * @param pkt Packet that generated this miss.
     */
    void reset(const std::shared_ptr<ReplacementData>& replacement_data,
        const PacketPtr pkt) override;
    void reset(const std::shared_ptr<ReplacementData>& replacement_data) const
        override;

    /**
     * Find replacement victim using rrpv, as in SRRIP.
     *
     * @param cands Replacement candidates, selected by indexing policy.
     * @return Replacement entry to be replaced.
     */
    ReplaceableEntry* getVictim(const ReplacementCandidates& candidates) const
                                                                     override;

    /**
     * Instantiate a replacement data entry.
     *
     * @return A shared pointer to the new replacement data.
     */
    std::shared_ptr<ReplacementData> instantiateEntry() override;
};

} // namespace replacement_policy
} // namespace gem5

#endif // __MEM_CACHE_REPLACEMENT_POLICIES_PACIPV_RP_HH__