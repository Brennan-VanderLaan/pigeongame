package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/containernetworking/cni/pkg/skel"
	"github.com/containernetworking/cni/pkg/types"
	current "github.com/containernetworking/cni/pkg/types/100"
	"github.com/containernetworking/cni/pkg/version"
	"github.com/vishvananda/netlink"
	"github.com/vishvananda/netns"
)

const (
	logFile = "/var/log/pigeon-cni-plugin.log"
	ipStore = "/tmp/reserved_ips"
)

type NetConf struct {
	types.NetConf
	ClientAddress    string `json:"client_address"`
	GwAddress        string `json:"gw_address"`
	Subnet           string `json:"subnet"`
	ClientInterface  string `json:"client_interface"`
	GatewayInterface string `json:"gateway_interface"`
	Name             string `json:"name"`
}

func init() {
	runtime.LockOSThread()
}

func setupLogging() {
	if os.Getenv("DEBUG") != "" {
		logFile, err := os.OpenFile(logFile, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
		if err == nil {
			log.SetOutput(logFile)
		}
	}
}

func cmdAdd(args *skel.CmdArgs) error {
	setupLogging()
	log.Printf("CNI command: ADD")
	log.Printf("Args: %+v", args)

	conf := NetConf{}
	if err := json.Unmarshal(args.StdinData, &conf); err != nil {
		return fmt.Errorf("failed to parse network configuration: %v", err)
	}

	log.Printf("Config: %+v", conf)

	// Create /var/run/netns directory if it doesn't exist
	if err := os.MkdirAll("/var/run/netns", 0755); err != nil {
		return fmt.Errorf("failed to create netns directory: %v", err)
	}

	// Create symlinks for network namespace
	nsPath := filepath.Join("/var/run/netns", args.ContainerID)
	if err := os.Remove(nsPath); err != nil && !os.IsNotExist(err) {
		log.Printf("Warning: failed to remove existing symlink: %v", err)
	}
	
	if err := os.Symlink(args.Netns, nsPath); err != nil {
		return fmt.Errorf("failed to create netns symlink: %v", err)
	}

	clientNSPath := filepath.Join("/var/run/netns", fmt.Sprintf("%s-%s-%s", conf.ClientInterface, conf.Name, conf.GatewayInterface))
	if err := os.Remove(clientNSPath); err != nil && !os.IsNotExist(err) {
		log.Printf("Warning: failed to remove existing client symlink: %v", err)
	}
	
	if err := os.Symlink(args.Netns, clientNSPath); err != nil {
		return fmt.Errorf("failed to create client netns symlink: %v", err)
	}

	var address string
	var mac net.HardwareAddr
	var err error

	if args.IfName == conf.GatewayInterface {
		log.Println("We're the gateway")
		address = conf.GwAddress
		mac, err = handleGateway(args, &conf)
		if err != nil {
			return err
		}
	} else {
		log.Println("We're the client")
		address = conf.ClientAddress
		mac, err = handleClient(args, &conf)
		if err != nil {
			return err
		}
	}

	result := &current.Result{
		CNIVersion: conf.CNIVersion,
		Interfaces: []*current.Interface{
			{
				Name:    args.IfName,
				Mac:     mac.String(),
				Sandbox: args.Netns,
			},
		},
		IPs: []*current.IPConfig{
			{
				Address: net.IPNet{
					IP:   net.ParseIP(strings.Split(address, "/")[0]),
					Mask: net.CIDRMask(getSubnetMaskSize(address), 32),
				},
				Gateway:   net.ParseIP("0.0.0.0"),
				Interface: &[]int{0}[0],
			},
		},
	}

	return types.PrintResult(result, conf.CNIVersion)
}

func handleGateway(args *skel.CmdArgs, conf *NetConf) (net.HardwareAddr, error) {
	// Get the target network namespace
	targetNS, err := netns.GetFromPath(args.Netns)
	if err != nil {
		return nil, fmt.Errorf("failed to get netns: %v", err)
	}
	defer targetNS.Close()

	// Find the veth interface and move it to the container namespace
	vethName := fmt.Sprintf("pisp%s", conf.GatewayInterface)
	link, err := netlink.LinkByName(vethName)
	if err != nil {
		return nil, fmt.Errorf("failed to find veth interface %s: %v", vethName, err)
	}

	// Move interface to container namespace
	if err := netlink.LinkSetNsFd(link, int(targetNS)); err != nil {
		return nil, fmt.Errorf("failed to move interface to namespace: %v", err)
	}

	// Enter the network namespace to configure the interface
	return configureInterfaceInNS(targetNS, vethName, conf.GwAddress, args.IfName)
}

func handleClient(args *skel.CmdArgs, conf *NetConf) (net.HardwareAddr, error) {
	// Create veth pair
	clientVeth := fmt.Sprintf("pisp%s", args.IfName)
	gatewayVeth := fmt.Sprintf("pisp%s", conf.GatewayInterface)

	veth := &netlink.Veth{
		LinkAttrs: netlink.LinkAttrs{Name: clientVeth},
		PeerName:  gatewayVeth,
	}

	// Create the veth pair (ignore error if it already exists)
	if err := netlink.LinkAdd(veth); err != nil && !strings.Contains(err.Error(), "file exists") {
		return nil, fmt.Errorf("failed to create veth pair: %v", err)
	}

	// Get the target network namespace
	clientNSPath := fmt.Sprintf("%s-%s-%s", conf.ClientInterface, conf.Name, conf.GatewayInterface)
	targetNS, err := netns.GetFromPath(filepath.Join("/var/run/netns", clientNSPath))
	if err != nil {
		return nil, fmt.Errorf("failed to get client netns: %v", err)
	}
	defer targetNS.Close()

	// Move client interface to client namespace
	clientLink, err := netlink.LinkByName(clientVeth)
	if err != nil {
		return nil, fmt.Errorf("failed to find client veth: %v", err)
	}

	if err := netlink.LinkSetNsFd(clientLink, int(targetNS)); err != nil {
		return nil, fmt.Errorf("failed to move client interface to namespace: %v", err)
	}

	// Configure client interface in its namespace
	mac, err := configureInterfaceInNS(targetNS, clientVeth, conf.ClientAddress, args.IfName)
	if err != nil {
		return nil, err
	}

	// Set up routing in client namespace
	if err := setupClientRouting(targetNS, clientVeth, conf.GwAddress); err != nil {
		return nil, err
	}

	return mac, nil
}

func configureInterfaceInNS(ns netns.NsHandle, linkName, address, finalName string) (net.HardwareAddr, error) {
	// Get current namespace to restore later
	origns, err := netns.Get()
	if err != nil {
		return nil, fmt.Errorf("failed to get current netns: %v", err)
	}
	defer origns.Close()

	// Switch to target namespace
	if err := netns.Set(ns); err != nil {
		return nil, fmt.Errorf("failed to set netns: %v", err)
	}
	defer netns.Set(origns) // Switch back when done

	// Execute in the target namespace
	err = func() error {
		// Get the link by its current name
		link, err := netlink.LinkByName(linkName)
		if err != nil {
			return fmt.Errorf("failed to find link %s: %v", linkName, err)
		}

		// Rename the interface if needed
		if linkName != finalName {
			if err := netlink.LinkSetName(link, finalName); err != nil {
				return fmt.Errorf("failed to rename interface: %v", err)
			}
			// Get the link again with its new name
			link, err = netlink.LinkByName(finalName)
			if err != nil {
				return fmt.Errorf("failed to find renamed link: %v", err)
			}
		}

		// Bring the interface up
		if err := netlink.LinkSetUp(link); err != nil {
			return fmt.Errorf("failed to bring interface up: %v", err)
		}

		// Add IP address
		addr, err := netlink.ParseAddr(address)
		if err != nil {
			return fmt.Errorf("failed to parse address %s: %v", address, err)
		}

		if err := netlink.AddrAdd(link, addr); err != nil && !strings.Contains(err.Error(), "file exists") {
			return fmt.Errorf("failed to add address: %v", err)
		}

		// Disable TX checksums (equivalent to ethtool -K tx off)
		// Note: This is a simplified approach - in production you might want more sophisticated handling
		
		return nil
	}()

	if err != nil {
		return nil, err
	}

	// Get MAC address
	var mac net.HardwareAddr

	// Switch to target namespace again to get MAC
	if err := netns.Set(ns); err != nil {
		return nil, fmt.Errorf("failed to set netns for MAC: %v", err)
	}
	defer netns.Set(origns) // Switch back when done

	err = func() error {
		link, err := netlink.LinkByName(finalName)
		if err != nil {
			return err
		}
		mac = link.Attrs().HardwareAddr
		return nil
	}()

	return mac, err
}

func setupClientRouting(ns netns.NsHandle, linkName, gwAddress string) error {
	// Get current namespace to restore later
	origns, err := netns.Get()
	if err != nil {
		return fmt.Errorf("failed to get current netns: %v", err)
	}
	defer origns.Close()

	// Switch to target namespace
	if err := netns.Set(ns); err != nil {
		return fmt.Errorf("failed to set netns: %v", err)
	}
	defer netns.Set(origns) // Switch back when done

	return func() error {
		link, err := netlink.LinkByName(linkName)
		if err != nil {
			return fmt.Errorf("failed to find link for routing: %v", err)
		}

		// Parse gateway address (remove CIDR notation if present)
		gwIP := net.ParseIP(strings.Split(gwAddress, "/")[0])
		if gwIP == nil {
			return fmt.Errorf("invalid gateway address: %s", gwAddress)
		}

		// Add default route
		route := &netlink.Route{
			LinkIndex: link.Attrs().Index,
			Gw:        gwIP,
			Dst:       nil, // default route (0.0.0.0/0)
		}

		if err := netlink.RouteAdd(route); err != nil && !strings.Contains(err.Error(), "file exists") {
			return fmt.Errorf("failed to add default route: %v", err)
		}

		return nil
	}()
}

func cmdDel(args *skel.CmdArgs) error {
	setupLogging()
	log.Printf("CNI command: DEL")

	conf := NetConf{}
	if err := json.Unmarshal(args.StdinData, &conf); err != nil {
		return fmt.Errorf("failed to parse network configuration: %v", err)
	}

	// Remove the network namespace symlinks
	clientNSPath := filepath.Join("/var/run/netns", fmt.Sprintf("%s-%s-%s", conf.ClientInterface, conf.Name, conf.GatewayInterface))
	if err := os.Remove(clientNSPath); err != nil && !os.IsNotExist(err) {
		log.Printf("Warning: failed to remove client netns symlink: %v", err)
	}

	return nil
}

func cmdCheck(args *skel.CmdArgs) error {
	return fmt.Errorf("CHECK not supported")
}

func getSubnetMaskSize(address string) int {
	if strings.Contains(address, "/") {
		parts := strings.Split(address, "/")
		if len(parts) == 2 {
			// Parse the CIDR notation
			_, ipNet, err := net.ParseCIDR(address)
			if err == nil {
				ones, _ := ipNet.Mask.Size()
				return ones
			}
		}
	}
	return 24 // default /24
}

func main() {
	skel.PluginMain(cmdAdd, cmdCheck, cmdDel, version.All, "PigeonCNI v1.0.0")
}