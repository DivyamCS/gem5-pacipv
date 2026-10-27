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
SE-mode script for the PACIPV study (Mostofi et al., ISCA 2025).

It is based on configs/deprecated/example/se.py, but builds the paper's
three-level cache hierarchy (Table 1) instead of the generic one:

    L1I 32KiB 8-way  -> private L2 1280KiB 10-way -> shared L3 (LLC)
    L1D 48KiB 12-way ->                               3MiB 12-way

The LLC replacement policy is chosen with --llc-policy, and the PACIPV
demand/prefetch IPVs with --llc-demand-ipv / --llc-prefetch-ipv.

Example:
    build/X86/gem5.opt -d m5out/mcf_PACIPV configs/pacipv/pacipv_se.py \\
        --bench mcf --llc-policy PACIPV -F 100000000 --maxinsts 20000000
"""

import argparse
import os

import m5
from m5.objects import *
from m5.util import (
    addToPath,
    fatal,
)

addToPath("../")

from common import (
    MemConfig,
    ObjectList,
    Options,
    Simulation,
)
from common.cpu2017 import *
from common.FileSystemConfig import config_filesystem

# ---------------------------------------------------------------------------
# Caches from the paper's Table 1. In gem5 a hit costs max(tag, data)
# latency, so both are set to the paper's latency.
# ---------------------------------------------------------------------------


class PaperL1ICache(Cache):
    size = "32KiB"
    assoc = 8
    tag_latency = 4
    data_latency = 4
    response_latency = 4
    mshrs = 16
    tgts_per_mshr = 20
    is_read_only = True
    writeback_clean = True


class PaperL1DCache(Cache):
    size = "48KiB"
    assoc = 12
    tag_latency = 5
    data_latency = 5
    response_latency = 5
    mshrs = 16
    tgts_per_mshr = 20


class PaperL2Cache(Cache):
    size = "1280KiB"
    assoc = 10
    tag_latency = 15
    data_latency = 15
    response_latency = 15
    mshrs = 48
    tgts_per_mshr = 12
    write_buffers = 16


class PaperL3Cache(Cache):
    size = "3MiB"
    assoc = 12
    tag_latency = 74
    data_latency = 74
    response_latency = 74
    mshrs = 64
    tgts_per_mshr = 12
    write_buffers = 32


class WalkerCache(Cache):
    size = "1KiB"
    assoc = 2
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 10
    tgts_per_mshr = 12


# Prefetcher substitutes for the paper's EIP (L1I), Berti (L1D) and
# next-line (L2), which gem5 does not have
PREFETCHERS = {
    "none": lambda: NULL,
    "nextline": lambda: TaggedPrefetcher(degree=1),
    "stride": lambda: StridePrefetcher(),
    "bop": lambda: BOPPrefetcher(),
}

LLC_POLICIES = ["LRU", "SRRIP", "DRRIP", "SHiP", "PACIPV"]


def parse_ipv(text):
    """Turn '0,1,1,0,3' into [0, 1, 1, 0, 3]."""
    try:
        ipv = [int(x) for x in text.split(",")]
    except ValueError:
        raise argparse.ArgumentTypeError(f"bad IPV '{text}'")
    if len(ipv) != 5 or any(v < 0 or v > 3 for v in ipv):
        raise argparse.ArgumentTypeError(
            f"IPV '{text}' must be 5 values between 0 and 3"
        )
    return ipv


def make_llc_policy(args):
    """Create the LLC replacement policy chosen with --llc-policy."""
    if args.llc_policy == "LRU":
        return LRURP()
    if args.llc_policy == "SRRIP":
        # Insert at RRPV 2, promote to 0 on a hit: IPV [0,0,0,0,2]
        return RRIPRP(hit_priority=True)
    if args.llc_policy == "DRRIP":
        # Set dueling between SRRIP and BRRIP with 32 sample sets per team.
        # A constituency must hold whole sets, so it is a multiple of assoc.
        num_entries = m5.util.convert.toMemorySize(args.llc_size) // 64
        return DRRIPRP(
            constituency_size=num_entries // 32,
            team_size=args.llc_assoc,
            replacement_policy_a=BRRIPRP(hit_priority=True),
            replacement_policy_b=RRIPRP(hit_priority=True),
        )
    if args.llc_policy == "SHiP":
        return SHiPPCRP()
    return PACIPVRP(
        demand_ipv=args.llc_demand_ipv, prefetch_ipv=args.llc_prefetch_ipv
    )


def tune_o3(cpu_class):
    """Apply the paper's core (Table 1) to an O3 CPU class."""
    if cpu_class is None or not ObjectList.is_o3_cpu(cpu_class):
        return
    cpu_class.fetchWidth = 16
    cpu_class.decodeWidth = 6
    cpu_class.renameWidth = 6
    cpu_class.dispatchWidth = 6
    cpu_class.issueWidth = 12
    cpu_class.wbWidth = 12
    cpu_class.commitWidth = 12
    cpu_class.numROBEntries = 512
    cpu_class.LQEntries = 192
    cpu_class.SQEntries = 114
    cpu_class.numPhysIntRegs = 280
    cpu_class.numPhysFloatRegs = 332
    cpu_class.branchPred = BranchPredictor(
        conditionalBranchPred=TAGE_SC_L_64KB()
    )


def build_caches(args, system):
    """Build L1I/L1D and private L2 per core, and one shared L3 (LLC)."""
    system.l3 = PaperL3Cache(
        size=args.llc_size,
        assoc=args.llc_assoc,
        replacement_policy=make_llc_policy(args),
        clk_domain=system.cpu_clk_domain,
    )
    system.tol3bus = L2XBar(clk_domain=system.cpu_clk_domain)
    system.l3.cpu_side = system.tol3bus.mem_side_ports
    system.l3.mem_side = system.membus.cpu_side_ports

    for cpu in system.cpu:
        icache = PaperL1ICache(prefetcher=PREFETCHERS[args.l1i_pf]())
        dcache = PaperL1DCache(prefetcher=PREFETCHERS[args.l1d_pf]())
        l2cache = PaperL2Cache(prefetcher=PREFETCHERS[args.l2_pf]())
        cpu.addTwoLevelCacheHierarchy(
            icache, dcache, l2cache, WalkerCache(), WalkerCache()
        )
        cpu.createInterruptController()
        cpu.connectAllPorts(
            system.tol3bus.cpu_side_ports,
            system.membus.cpu_side_ports,
            system.membus.mem_side_ports,
        )


parser = argparse.ArgumentParser()
Options.addCommonOptions(parser)
Options.addSEOptions(parser)

pacipv_group = parser.add_argument_group("PACIPV study options")
pacipv_group.add_argument(
    "--llc-policy",
    choices=LLC_POLICIES,
    required=True,
    help="Replacement policy of the last-level cache (L3)",
)
pacipv_group.add_argument(
    "--llc-demand-ipv",
    type=parse_ipv,
    default=parse_ipv("0,1,1,0,3"),
    help="PACIPV demand IPV (default: paper's 0,1,1,0,3)",
)
pacipv_group.add_argument(
    "--llc-prefetch-ipv",
    type=parse_ipv,
    default=parse_ipv("0,1,0,0,3"),
    help="PACIPV prefetch IPV (default: paper's 0,1,0,0,3)",
)
pacipv_group.add_argument(
    "--llc-size", default="3MiB", help="LLC size (default: 3MiB)"
)
pacipv_group.add_argument(
    "--llc-assoc", type=int, default=12, help="LLC associativity"
)
for level, default in (
    ("l1i", "nextline"),
    ("l1d", "stride"),
    ("l2", "nextline"),
):
    pacipv_group.add_argument(
        f"--{level}-pf",
        choices=list(PREFETCHERS),
        default=default,
        help=f"{level.upper()} prefetcher (default: {default})",
    )

# Paper defaults: O3 core and DDR4 with 2 channels (TAGE-SC-L is set in
# tune_o3)
parser.set_defaults(
    cpu_type="O3CPU",
    caches=True,
    mem_type="DDR4_2400_8x8",
    mem_channels=2,
    mem_size="8GiB",
)

args = parser.parse_args()

if args.num_cpus != 1:
    fatal("This script models the paper's single-core system only")

if args.bench:
    try:
        workload = globals()[args.bench]("x86", "linux", args.spec_input)
        process = workload.makeProcess()
    except Exception as e:
        fatal(f"Unable to set up benchmark '{args.bench}': {e}")
elif args.cmd:
    process = Process(pid=100, executable=args.cmd, cwd=os.getcwd())
    process.cmd = [args.cmd] + args.options.split()
    if args.input:
        process.input = args.input
    if args.output:
        process.output = args.output
else:
    fatal("No workload specified, use --bench or --cmd")

(CPUClass, test_mem_mode, FutureClass) = Simulation.setCPUClass(args)
tune_o3(CPUClass)
tune_o3(FutureClass)

system = System(
    cpu=[CPUClass(cpu_id=0)],
    mem_mode=test_mem_mode,
    mem_ranges=[AddrRange(args.mem_size)],
    cache_line_size=args.cacheline_size,
)

system.voltage_domain = VoltageDomain(voltage=args.sys_voltage)
system.clk_domain = SrcClockDomain(
    clock=args.sys_clock, voltage_domain=system.voltage_domain
)
system.cpu_voltage_domain = VoltageDomain()
system.cpu_clk_domain = SrcClockDomain(
    clock=args.cpu_clock, voltage_domain=system.cpu_voltage_domain
)

cpu = system.cpu[0]
cpu.clk_domain = system.cpu_clk_domain
cpu.workload = process
cpu.createThreads()

system.membus = SystemXBar()
system.system_port = system.membus.cpu_side_ports
build_caches(args, system)
MemConfig.config_mem(args, system)
config_filesystem(system, args)

system.workload = SEWorkload.init_compatible(process.executable)

root = Root(full_system=False, system=system)
Simulation.run(args, root, system, FutureClass)