#!/bin/bash

# download reference cni plugins v1.1.1
mkdir -p /tmp/cni
echo "Pulling CNI plugins..."
curl -L -o /tmp/cni/bridge-cni.tgz https://github.com/containernetworking/plugins/releases/download/v1.1.1/cni-plugins-linux-amd64-v1.1.1.tgz
curl -L -o /tmp/cni/traefik.tgz https://github.com/traefik/traefik/releases/download/v2.6.6/traefik_v2.6.6_linux_amd64.tar.gz
cd /tmp/cni
echo "Unpacking CNI plugins..."
tar -zxvf bridge-cni.tgz
tar -zxvf traefik.tgz
chmod a+x bridge
chmod a+x traefik

echo "Moving CNI plugins into /opt/cni/bin"
mkdir -p /opt/cni/bin
mv bridge /opt/cni/bin
cp /pigeon-cni /opt/cni/bin/pigeon-cni
# mv traefik /opt/cni/bin
echo "Done..."

while true; do sleep 100; done