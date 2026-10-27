FROM ghcr.io/gem5/ubuntu-24.04_all-dependencies:latest
# x86-64 runtime libraries so SPEC x86-64 binaries run in gem5 SE mode on an ARM host
RUN apt-get update && apt-get install -y \
      libc6-amd64-cross libstdc++6-amd64-cross \
      libgcc-s1-amd64-cross libgfortran5-amd64-cross \
 && mkdir -p /lib64 \
 && ln -sf /usr/x86_64-linux-gnu/lib/ld-linux-x86-64.so.2 /lib64/ld-linux-x86-64.so.2 \
 && ( [ -e /usr/lib/x86_64-linux-gnu ] || ln -s /usr/x86_64-linux-gnu/lib /usr/lib/x86_64-linux-gnu ) \
 && rm -rf /var/lib/apt/lists/*
