# Copyright (c) 2026 Divyam
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Summarize pacipv_se.py runs.

Each run directory is expected to be named <benchmark>_<policy>, e.g.
results/mcf_LRU. For every run it prints the metrics the paper reports:
IPC, L1I MPKI and average L1I demand miss latency (cycles), and LLC
demand/prefetch MPKI. If LRU runs exist, it also prints each policy's
speedup over LRU and the geometric mean speedup per policy.

Usage:
    python3 configs/pacipv/summarize.py results
"""

import math
import os
import re
import sys

TICKS_PER_CYCLE = 500  # 2GHz CPU clock (se.py default) at 1THz tick rate


def read_stats(path):
    """Return {stat name: value} for the first stats dump in a file."""
    stats = {}
    with open(path) as f:
        for line in f:
            if line.startswith("---------- End"):
                break
            parts = line.split()
            if len(parts) >= 2:
                try:
                    stats[parts[0]] = float(parts[1])
                except ValueError:
                    pass
    return stats


def metrics(stats):
    insts = stats.get("simInsts", 0)
    if insts == 0:
        return None
    kilo = insts / 1000.0
    llc_demand = sum(
        v
        for k, v in stats.items()
        if re.match(r"system\.l3\.demandMisses::switch_cpus\.", k)
    )
    llc_prefetch = sum(
        v
        for k, v in stats.items()
        if re.match(r"system\.l3\.demandMisses::.*prefetcher$", k)
    )
    return {
        "ipc": stats.get("system.switch_cpus.ipc", 0),
        "l1i_mpki": stats.get("system.cpu.icache.demandMisses::total", 0)
        / kilo,
        "l1i_lat": stats.get(
            "system.cpu.icache.demandAvgMissLatency::total", 0
        )
        / TICKS_PER_CYCLE,
        "llc_d_mpki": llc_demand / kilo,
        "llc_p_mpki": llc_prefetch / kilo,
    }


def main(results_dir):
    runs = {}
    for name in sorted(os.listdir(results_dir)):
        stats_file = os.path.join(results_dir, name, "stats.txt")
        if "_" not in name or not os.path.isfile(stats_file):
            continue
        bench, policy = name.rsplit("_", 1)
        m = metrics(read_stats(stats_file))
        if m is None:
            print(f"warning: {name} has no simulated instructions")
            continue
        runs[(bench, policy)] = m

    print(
        f"{'benchmark':10} {'policy':7} {'IPC':>7} {'speedup':>8} "
        f"{'L1I MPKI':>9} {'L1I lat':>8} {'LLC dMPKI':>10} {'LLC pMPKI':>10}"
    )
    speedups = {}
    for (bench, policy), m in sorted(runs.items()):
        base = runs.get((bench, "LRU"))
        speedup = m["ipc"] / base["ipc"] if base and base["ipc"] else None
        if speedup:
            speedups.setdefault(policy, []).append(speedup)
        shown = f"{speedup:8.4f}" if speedup else f"{'-':>8}"
        print(
            f"{bench:10} {policy:7} {m['ipc']:7.4f} {shown} "
            f"{m['l1i_mpki']:9.3f} {m['l1i_lat']:8.1f} "
            f"{m['llc_d_mpki']:10.3f} {m['llc_p_mpki']:10.3f}"
        )

    if speedups:
        print("\nGeometric mean speedup over LRU:")
        for policy, values in sorted(speedups.items()):
            geomean = math.exp(sum(math.log(v) for v in values) / len(values))
            print(f"  {policy:7} {geomean:.4f}  ({len(values)} benchmarks)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])