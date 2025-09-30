#!/bin/bash

## Helpers

print_header() {
    local text="$1"
    local width=40
    local text_len=${#text}
    local padding=$(( (width - text_len - 2) / 2 ))

    printf "%${width}s\n" | tr ' ' '#'
    printf "#%*s%s%*s#\n" $padding "" "$text" $padding "" 
    printf "%${width}s\n" | tr ' ' '#'
}

run_with_status() {
    local message="$1"
    shift
    printf "%-35s" "$message"
    if "$@" >/dev/null 2>&1; then
        echo -e "\033[36mDONE\033[0m"
        return 0
    else
        echo -e "\033[35mERR\033[0m"
        return 1
    fi
}

generate_wg_keys() {
    local key_path="$1"
    local dir=$(dirname "$key_path")

    # Create directory if it doesn't exist
    mkdir -p "$dir"

    # Generate private key
    wg genkey > "${key_path}-secret.key"

    # Generate public key from private key
    wg pubkey < "${key_path}-secret.key" > "${key_path}-public.key"
}

# start_node() {
#     local container_name="$1"
#     local 


# }


##---------------------------------------------------------------------------------##

print_header "CLEAN FOR MO"

run_with_status "Nuking ./gen folder" rm -rf ./gen/
run_with_status "Scaffolding..." mkdir ./gen/


echo
print_header "BOOT"

# For cluster
run_with_status "Generating cluster pki..." talosctl gen secrets -o ./gen/secrets.yaml

echo
print_header "WIREGUARD INIT KEYS"

run_with_status "wg-wsl" generate_wg_keys "./gen/pki/wg-wsl"
run_with_status "wg-node0" generate_wg_keys "./gen/pki/wg-node0"
run_with_status "wg-node1" generate_wg_keys "./gen/pki/wg-node1"
run_with_status "wg-node2" generate_wg_keys "./gen/pki/wg-node2"

echo
print_header "DOCKER CLEANUP"

run_with_status "Nuking existing nodes" docker rm -f talos-cp0 talos-worker0

run_with_status "Removing network" docker network rm test-network
run_with_status "Creating network" docker network create --driver bridge --attachable test-network


echo
print_header "Create initial mesh"
echo "WSL / Win11   talos cluster"
echo " [you]           [cp0]"
echo "                   "
echo "                   "
echo "                   "
echo "               [worker0]"
echo

echo "Spinning up nodes..."

# TODO: Need to calculate USERDATA for both nodes, or test applying configs via sketchy port forwarding of talos api?

run_with_status "Creating controlplane" docker run -d \
  --name talos-cp0 \
  --hostname talos-cp0 \
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
  --network=test-network \
  -e PLATFORM=container \
  -p 0.0.0.0:50000:50000 \
  -p 0.0.0.0:50001:50001 \
  -p 0.0.0.0:51111:51111/udp \
  -e USERDATA=$cp_out \
   ghcr.io/siderolabs/talos:v1.11.2

run_with_status "Creating worker0" docker run -d \
  --name talos-worker0 \
  --hostname talos-worker0 \
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
  --network=test-network \
  -e PLATFORM=container \
  -e USERDATA=$cp_out \
   ghcr.io/siderolabs/talos:v1.11.2

# TODO: Verify cluster forms

echo "WSL / Win11   talos cluster"
echo " [you]           [cp0]"
echo "                   ^"
echo "                   |"
echo "                   v"
echo "               [worker0]"
echo

sleep 2
echo "Setting up local access to mesh..."

# TODO: Set up local connection to mesh

# Ping test to cp0
# Ping test to worker0 (proves routing)

echo 
echo "WSL / Win11   talos cluster"
echo " [you] <-------> [cp0]"
echo "                   ^"
echo "                   |"
echo "                   v"
echo "               [worker0]"