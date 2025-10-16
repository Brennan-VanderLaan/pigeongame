#!/bin/bash



docker run -d \
  --name talos-cp \
  --hostname talos-cp \
  --read-only \
  --privileged \
  --security-opt seccomp=unconfined \
  --mount type=tmpfs,destination=/run \
  --mount type=tmpfs,destination=/system \
  --mount type=tmpfs,destination=/tmp \
  --mount type=volume,destination=/system/state \
  --mount type=volume,destination=/var \
  --mount type=volume,destination=/etc/cni \
  --mount type=volume,destination=/etc/kubernetes \
  --mount type=volume,destination=/usr/libexec/kubernetes \
  --mount type=volume,destination=/usr/etc/udev \
  --mount type=volume,destination=/opt \
  --network=bridge \
  -e PLATFORM=container \
  -p 0.0.0.0:51111:51111/udp \
  -e USERDATA=$cp_out \
   ghcr.io/siderolabs/talos:v1.11.1