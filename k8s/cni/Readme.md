# PigeonCNI

CNI go brrrrrrr

### Historical version for reference

```bash
#!/bin/bash -e

# https://github.com/s-matyukevich/bash-cni-plugin/blob/master/01_gcp/bash-cni

if [[ ${DEBUG} -gt 0 ]]; then set -x; fi

exec 3>&1 # make stdout available as fd 3 for the result
exec &>> /var/log/bash-cni-plugin.log

IP_STORE=/tmp/reserved_ips # all reserved ips will be stored there

echo "CNI command: $CNI_COMMAND"

stdin=`cat /dev/stdin`
echo "stdin: $stdin"


case $CNI_COMMAND in
ADD)
	client_address=$(echo "$stdin" | jq -r ".client_address")
	gw_address=$(echo "$stdin" | jq -r ".gw_address")
	subnet=$(echo "$stdin" | jq -r ".subnet")
	client_interface=$(echo "$stdin" | jq -r ".client_interface")
	gw_interface=$(echo "$stdin" | jq -r ".gateway_interface")
	name=$(echo "$stdin" | jq -r ".name")
	subnet_mask_size=$(echo $subnet | awk -F  "/" '{print $2}')

  mkdir -p /var/run/netns/

  #link the process namespace into netns
  ln -sfT $CNI_NETNS /var/run/netns/$CNI_CONTAINERID
  ln -sfT $CNI_NETNS /var/run/netns/${client_interface}-${name}-${gw_interface}

  if [[ $CNI_IFNAME == $gw_interface ]]; then
    echo "We're the gateway"
    echo "Trying to finish interface pair ${CNI_IFNAME} (soon) ${client_interface}"
    address=$gw_address

    ip link set pisp${gw_interface} netns $CNI_CONTAINERID
    echo "Moved to NS"
    ip netns exec $CNI_CONTAINERID ip link set pisp${gw_interface} up
    echo "Brought ${gw_interface} up"
    ip netns exec $CNI_CONTAINERID ip addr add $gw_address dev pisp${CNI_IFNAME}
    echo "Configured IP ${gw_address} on ${gw_interface}"
    ip netns exec $CNI_CONTAINERID ethtool -K pisp${CNI_IFNAME} tx off || true

  else
    echo "We're the client"
    echo "Trying to create interface pair ${CNI_IFNAME} (now) ${gw_interface}"

    address=$client_address
    # Container interface, host interface
    ip link add pisp${CNI_IFNAME} type veth peer name pisp${gw_interface} || true

    echo "Tweaking ns"
    ip link set pisp${CNI_IFNAME} netns ${client_interface}-${name}-${gw_interface} || true

    ip netns exec ${client_interface}-${name}-${gw_interface} ip link set pisp${CNI_IFNAME} up || true

    echo "turning off tcp checks"
    ip netns exec ${client_interface}-${name}-${gw_interface} ethtool -K pisp${CNI_IFNAME} tx off || true

    ip netns exec ${client_interface}-${name}-${gw_interface} ip addr add ${client_address} dev pisp${CNI_IFNAME}

    gw_address=$(echo $gw_address | cut -f 1 -d /)

    ip netns exec ${client_interface}-${name}-${gw_interface} ip route add default via ${gw_address} dev pisp${CNI_IFNAME}

  fi

	mac=$(ip netns exec ${CNI_CONTAINERID} ip link show pisp${CNI_IFNAME} | awk '/ether/ {print $2}')

echo "{
  \"cniVersion\": \"0.3.1\",
  \"interfaces\": [
      {
          \"name\": \"$CNI_IFNAME\",
          \"mac\": \"$mac\",
          \"sandbox\": \"$CNI_NETNS\"
      }
  ],
  \"ips\": [
      {
          \"version\": \"4\",
          \"address\": \"$address\",
          \"gateway\": \"0.0.0.0\",
          \"interface\": 0
      }
  ]
}" >&3

;;

DEL)
  name=$(echo "$stdin" | jq -r ".name")
  client_interface=$(echo "$stdin" | jq -r ".client_interface")
	gw_interface=$(echo "$stdin" | jq -r ".gateway_interface")
	unlink /var/run/netns/${client_interface}-${name}-${gw_interface}
#	idfk yet
;;

GET)
	echo "GET not supported"
	exit 1
;;

VERSION)
echo '{
  "cniVersion": "0.3.1",
  "supportedVersions": [ "0.3.0", "0.3.1", "0.4.0" ]
}' >&3
;;

*)
  echo "Unknown cni commandn: $CNI_COMMAND"
  exit 1
;;

esac
```