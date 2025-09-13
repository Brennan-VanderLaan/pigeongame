#!/bin/bash

rm -r ./gen
mkdir -p ./gen/pki

WG_CIDR=10.12.0.0/24
WG_LOCAL_ADDR=10.12.0.5/24
LOCAL_ADDR=10.12.0.2/32
WG_ENDPOINT=192.168.10.13:51111
# Initialize control plane and worker IP addresses
control_plane_ip_start=6
worker_ip_start=11

#Generate the PKI for the WSL host to join
talosctl gen secrets -o ./gen/secrets.yaml
wg genkey >./gen/pki/wg-local-secret.key
wg pubkey <./gen/pki/wg-local-secret.key >./gen/pki/wg-local-public.key

# Generate control plane nodes PKI for wireguard
for i in $(seq 0 $((num_control_planes - 1))); do
  control_plane_ip="10.12.0.$((control_plane_ip_start + i - 1))/32"
  endpoint_ip=$(ip addr show eth0 | grep -w inet | awk '{print $2}' | cut -d '/' -f 1) # host IP
  # Generate the PKI for wireguard
  mkdir -p ./gen/pki/cp/$i/
  mkdir -p ./gen/config/cp/$i/
  wg genkey >./gen/pki/cp/$i/wg-secret.key
  wg pubkey <./gen/pki/cp/$i/wg-secret.key >./gen/pki/cp/$i/wg-public.key
done

# Generate worker nodes
for i in $(seq 0 $((num_workers - 1))); do
  worker_ip="10.12.0.$((worker_ip_start + i - 1))/32"
  # Generate the PKI for wireguard
  mkdir -p ./gen/pki/worker/$i/
  mkdir -p ./gen/config/worker/$i/
  wg genkey >./gen/pki/worker/$i/wg-secret.key
  wg pubkey <./gen/pki/worker/$i/wg-secret.key >./gen/pki/worker/$i/wg-public.key
  sed "s|<WG-PRIVATE-KEY>|$(cat ./gen/pki/worker/$i/wg-secret.key)|g; s|<WG-PUBLIC-KEY>|$(cat ./gen/pki/cp/0/wg-public.key)|g; s|<WG-CIDR>|$WG_CIDR|g; s|<WG-ADDR>|$worker_ip|g; s|<WG-ENDPOINT>|$WG_ENDPOINT|g" wireguard-worker-patch.yaml >./gen/wg-worker-$i.yaml

  talosctl gen config --with-secrets ./gen/secrets.yaml --with-examples=false --with-docs=false --config-patch-worker=@./gen/wg-worker-$i.yaml --config-patch-worker=@worker.patch.yaml --output=./gen/config/worker/$i/ talos-pisp https://10.12.0.4:6443
  rm ./gen/config/worker/$i/controlplane.yaml
  rm ./gen/config/worker/$i/talosconfig
done

# Finish control plane nodes
for i in $(seq 0 $((num_control_planes - 1))); do
  control_plane_ip="10.12.0.$((control_plane_ip_start + i - 1))/32"
  endpoint_ip=$(ip addr show eth0 | grep -w inet | awk '{print $2}' | cut -d '/' -f 1) # host IP

  sed "s|<WG-PRIVATE-KEY>|$(cat ./gen/pki/cp/$i/wg-secret.key)|g; s|<WG-ADDR>|$control_plane_ip|g; s|<WG-ROUTES-CIDR>|$WG_CIDR|g; s|<WG-CIDR>|$LOCAL_ADDR|g; s|<WG-PUBLIC-KEY>|$(cat ./gen/pki/wg-local-public.key)|g; s|<WG-ENDPOINT>|$endpoint_ip:51110|g" wireguard-cp-patch.yaml >./gen/wg-cp-$i.yaml

  # Build up the list of new peers to add to the control plane
  echo -e "\n" >>./gen/wg-cp-$i.yaml
  for j in $(seq 0 $((num_workers - 1))); do
    worker_ip="10.12.0.$((worker_ip_start + j - 1))/32"
    endpoint=${worker_endpoints[$j]}
    worker_public_key=$(cat ./gen/pki/worker/$j/wg-public.key)
    peer_entry="            - allowedIPs:\n              - $worker_ip\n              endpoint: $endpoint\n              persistentKeepaliveInterval: 10s\n              publicKey: $worker_public_key"
    echo -e "$peer_entry" >>./gen/wg-cp-$i.yaml
    echo -e "$peer_entry"
  done

  talosctl gen config --with-secrets ./gen/secrets.yaml --with-examples=false --with-docs=false --config-patch-control-plane=@./gen/wg-cp-$i.yaml --config-patch-control-plane=@controlplane.patch.yaml --config-patch-control-plane=@build-security.yaml --output=./gen/config/cp/$i/ talos-pisp https://10.12.0.4:6443
  rm ./gen/config/cp/$i/worker.yaml
  cp ./gen/config/cp/$i/talosconfig ./gen/
done