# gem5-pacipv

Implementation of **PACIPV** from *Light-weight Cache Replacement for
Instruction Heavy Workloads* (Mostofi et al., ISCA 2025) in gem5, evaluated
on SPEC CPU2017.

- Base: gem5 commit `f5c5a6e` (v25.1 stable). All changes are on branch `pacipv`.
- Official gem5 (up to v26.0) has no PACIPV and no prefetch-flag fix.

## What was added

| File | Change |
|---|---|
| `src/mem/cache/replacement_policies/pacipv_rp.{hh,cc}` | PACIPV policy: 2-bit RRPV, demand/prefetch IPVs, SRRIP victim selection (based on BRRIP) |
| `src/mem/cache/replacement_policies/ReplacementPolicies.py` | `PACIPVRP` SimObject (`num_bits`, `demand_ipv`, `prefetch_ipv`) |
| `src/mem/cache/replacement_policies/SConscript` | Build registration |
| `src/mem/cache/prefetch/queued.cc` | Tag hardware prefetches with `Request::PREFETCH` |
| `configs/pacipv/pacipv_se.py` | Paper's system (O3 core, 32K/48K L1, 1.25M L2, 3M LLC); LLC policy, IPV and prefetcher options |
| `configs/pacipv/summarize.py` | IPC, speedup, L1I MPKI/latency, LLC demand/prefetch MPKI, geomean |
| `configs/common/cpu2017.py`, `se.py` | SPEC CPU2017 workloads for SE mode (setup) |
| `util/dockerfiles/pacipv/Dockerfile` | Build environment: gem5's Ubuntu 24.04 image + x86-64 libraries for SPEC |

## Build and run

**1. Get the code**

    git clone -b pacipv https://github.com/DivyamCS/gem5-pacipv.git gem5
    cd gem5

**2. Environment.** gem5 builds on Linux. Build the Docker image once
(gem5's Ubuntu 24.04 image + x86-64 libraries for SPEC):

    docker build -t pacipv-gem5 util/dockerfiles/pacipv

Start it from inside the `gem5` folder. The repo must be mounted at `/gem5`,
because `cpu2017.py` uses absolute `/gem5/...` paths:

    docker run -it -v $PWD:/gem5 -w /gem5 pacipv-gem5

Tested on an Apple M4 Mac with Docker. Native macOS is not tested.

**3. Build** (inside the container):

    scons build/X86/gem5.opt -j8

**4. SPEC CPU2017** (not included, licensed). Place x86-64 binaries and
inputs at:

    /gem5/spec/cpu2017/cpu2017/binaries/<benchmark>
    /gem5/spec/cpu2017/cpu2017/data/<benchmark>/{ref,all}/input/

**5. Run** (200M instructions fast-forward, 50M measured):

    build/X86/gem5.opt -d m5out/mcf_PACIPV configs/pacipv/pacipv_se.py \
        --bench mcf --llc-policy PACIPV \
        --llc-demand-ipv 0,0,1,2,2 --llc-prefetch-ipv 0,1,0,0,3 \
        --l1d-pf bop -F 200000000 --maxinsts 50000000

    build/X86/gem5.opt -d m5out/mcf_LRU configs/pacipv/pacipv_se.py \
        --bench mcf --llc-policy LRU \
        --l1d-pf bop -F 200000000 --maxinsts 50000000

- `--llc-policy`: LRU, SRRIP, DRRIP, SHiP, PACIPV (required).
- IPVs default to the paper's: demand `0,1,1,0,3`, prefetch `0,1,0,0,3`.
- Prefetchers: `--l1i-pf`, `--l1d-pf`, `--l2-pf` take none, nextline,
  stride or bop (defaults: nextline, stride, nextline).
- `--llc-size` must give a power-of-2 number of sets with 12 ways
  (e.g. 1536KiB, 3MiB, 6MiB).

**6. Summarize** (run folders must be named `<benchmark>_<policy>`):

    python3 configs/pacipv/summarize.py m5out

## Results (geomean speedup over LRU, 200M instructions, 7 benchmarks)

| SRRIP | DRRIP | SHiP | PACIPV (paper IPVs) | PACIPV (trained) | PACIPV (identical IPVs) |
|---|---|---|---|---|---|
| -0.17% | -0.22% | -0.01% | -0.67% | -0.04% | **+0.14%** |

Trained: demand `0,0,1,2,2`, prefetch `0,1,0,0,3`. Identical: both `0,0,1,2,2`.
Paper IPVs: demand `0,1,1,0,3`, prefetch `0,1,0,0,3`.

---


# The gem5 Simulator

This is the repository for the gem5 simulator. It contains the full source code
for the simulator and all tests and regressions.

The gem5 simulator is a modular platform for computer-system architecture
research, encompassing system-level architecture as well as processor
microarchitecture. It is primarily used to evaluate new hardware designs,
system software changes, and compile-time and run-time system optimizations.

The main website can be found at <http://www.gem5.org>.

## Testing and code coverage status

**Note**: These regard tests run on the develop branch of gem5:
<https://github.com/gem5/gem5/tree/develop>.

[![Daily Tests](https://github.com/gem5/gem5/actions/workflows/daily-tests.yaml/badge.svg?branch=develop)](https://github.com/gem5/gem5/actions/workflows/daily-tests.yaml)
[![Weekly Tests](https://github.com/gem5/gem5/actions/workflows/weekly-tests.yaml/badge.svg?branch=develop)](https://github.com/gem5/gem5/actions/workflows/weekly-tests.yaml)
[![Compiler Tests](https://github.com/gem5/gem5/actions/workflows/compiler-tests.yaml/badge.svg?branch=develop)](https://github.com/gem5/gem5/actions/workflows/compiler-tests.yaml)
[![codecov](https://codecov.io/gh/gem5/gem5/branch/develop/graph/badge.svg)](https://app.codecov.io/gh/gem5/gem5/tree/develop)

## Getting started

A good starting point is <http://www.gem5.org/about>, and for
more information about building the simulator and getting started
please see <http://www.gem5.org/documentation> and
<http://www.gem5.org/documentation/learning_gem5/introduction>.

## Building gem5

To build gem5, you will need the following software: g++ or clang,
Python (gem5 links in the Python interpreter), SCons, zlib 1.2+, GNU m4
1.4+, and lastly protobuf if you want trace capture and playback support.
Please see
<http://www.gem5.org/documentation/general_docs/building> for more details
concerning the minimum versions of these tools.

Once you have all dependencies resolved, execute
`scons build/ALL/gem5.opt` to build an optimized version of the gem5 binary
(`gem5.opt`) containing all gem5 ISAs. If you only wish to compile gem5 to
include a single ISA, you can replace `ALL` with the name of the ISA. Valid
options include `ARM`, `NULL`, `MIPS`, `POWER`, `RISCV`, `SPARC`, and `X86`
The complete list of options can be found in the build_opts directory.

See https://www.gem5.org/documentation/general_docs/building for more
information on building gem5.

## The Source Tree

The main source tree includes these subdirectories:

* build_opts: pre-made default configurations for gem5
* build_tools: tools used internally by gem5's build process.
* configs: example simulation configuration scripts
* ext: less-common external packages needed to build gem5
* include: include files for use in other programs
* site_scons: modular components of the build system
* src: source code of the gem5 simulator. The C++ source, Python wrappers, and Python standard library are found in this directory.
* system: source for some optional system software for simulated systems
* tests: regression tests
* util: useful utility programs and files

## gem5 Resources

To run full-system simulations, you may need compiled system firmware, kernel
binaries and one or more disk images, depending on gem5's configuration and
what type of workload you're trying to run. Many of these resources can be
obtained from <https://resources.gem5.org>.

More information on gem5 Resources can be found at
<https://www.gem5.org/documentation/general_docs/gem5_resources/>.

## Getting Help, Reporting bugs, and Requesting Features

We provide a variety of channels for users and developers to get help, report
bugs, requests features, or engage in community discussions. Below
are a few of the most common we recommend using.

* **GitHub Discussions**: A GitHub Discussions page. This can be used to start
discussions or ask questions. Available at
<https://github.com/orgs/gem5/discussions>.
* **GitHub Issues**: A GitHub Issues page for reporting bugs or requesting
features. Available at <https://github.com/gem5/gem5/issues>.
* **gem5-users@gem5.org**: A mailing list for users of gem5 to ask questions
or start discussions. To join the mailing list please visit
<https://www.gem5.org/mailing_lists>.
* **gem5-dev@gem5.org**: A mailing list for developers of gem5 to ask questions
or start discussions. To join the mailing list please visit
<https://www.gem5.org/mailing_lists>.

## Contributing to gem5

We hope you enjoy using gem5. When appropriate we advise sharing your
contributions to the project. <https://www.gem5.org/contributing> can help you
get started. Additional information can be found in the CONTRIBUTING.md file.
