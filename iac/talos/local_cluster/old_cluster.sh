#!/bin/bash

#It's here for history - don't run it~
#exit 0

# Define the endpoints array
worker_endpoints=(127.0.0.1:51112 172.16.1.3:51111 192.168.10.13:51111 192.168.1.74:51111 )
num_control_planes=1
num_workers=${#worker_endpoints[@]}

rm -r ./gen
mkdir -p ./gen/pki
talosctl gen secrets -o ./gen/secrets.yaml
WG_CIDR=10.12.0.0/24
WG_ADDR=10.12.0.5/24
LOCAL_ADDR=10.12.0.2/32
WG_ENDPOINT=192.168.10.13:51111
#Generate the PKI for the WSL host to join
wg genkey >./gen/pki/wg-local-secret.key
wg pubkey <./gen/pki/wg-local-secret.key >./gen/pki/wg-local-public.key

# Initialize control plane and worker IP addresses
control_plane_ip_start=6
worker_ip_start=11

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

sudo ip link del dev wg0
sudo ip link add dev wg0 type wireguard
sudo ip addr add $LOCAL_ADDR dev wg0
sudo wg set wg0 listen-port 51110
sudo wg set wg0 private-key ./gen/pki/wg-local-secret.key
sudo ip link set dev wg0 up
sudo ip route add $WG_CIDR dev wg0
sudo wg set wg0 peer $(cat ./gen/pki/cp/0/wg-public.key) allowed-ips $WG_CIDR endpoint 127.0.0.1:51111

cp_out=$(cat ./gen/config/cp/0/controlplane.yaml | base64 -w 0)
docker rm -f talos-cp
#
docker run -d \
  --gpus all \
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
  -p 0.0.0.0:30000:30000 \
  -p 0.0.0.0:80:30001 \
  -p 0.0.0.0:443:30002 \
  -p 0.0.0.0:50000:50000 \
  -p 0.0.0.0:50001:50001 \
  -p 0.0.0.0:51111:51111/udp \
  -e USERDATA=$cp_out \
   ghcr.io/siderolabs/talos:v1.7.1


#
echo "Bootstrapping..."
sleep 4
talosctl bootstrap -e 10.12.0.5 -n 10.12.0.5 --talosconfig=./gen/config/cp/0/talosconfig
echo "Bootstrapped..."
sleep 20
echo "Getting kubeconfig"
talosctl kubeconfig -f -n 10.12.0.5 -e 10.12.0.5 --talosconfig=./gen/config/cp/0/talosconfig ./gen/kubeconfig
cp ./gen/kubeconfig ~/.kube/config
echo "Done..."


