package main

import (
	"bufio"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

type ControlMessage struct {
	Command   string  `json:"command"`
	Data      string  `json:"data"`
	Timestamp float64 `json:"timestamp"`
}

type BandwidthStats struct {
	BytesReceived int64   `json:"bytes_received"`
	PacketsReceived int64 `json:"packets_received"`
	Duration      float64 `json:"duration"`
	BandwidthMbps float64 `json:"bandwidth_mbps"`
	StartTime     time.Time
	LastPacketTime time.Time
}

type Server struct {
	controlPort int
	dataPort    int
	
	tcpListener net.Listener
	udpConn     *net.UDPConn
	
	clients     map[string]*ClientSession
	clientsMux  sync.RWMutex
	
	stats       *BandwidthStats
	statsMux    sync.RWMutex
	
	ctx         context.Context
	cancel      context.CancelFunc
}

type ClientSession struct {
	ID       string
	TCPConn  net.Conn
	UDPAddr  *net.UDPAddr
	LastSeen time.Time
	Testing  bool
}

type Client struct {
	host        string
	controlPort int
	dataPort    int
	
	tcpConn     net.Conn
	udpConn     *net.UDPConn
	serverAddr  *net.UDPAddr
	
	ctx         context.Context
	cancel      context.CancelFunc
}

type TestResult struct {
	PayloadSize   int
	BandwidthMbps float64
	LatencyMs     float64
	BytesSent     int64
	Duration      time.Duration
}

func NewServer(controlPort, dataPort int) *Server {
	ctx, cancel := context.WithCancel(context.Background())
	return &Server{
		controlPort: controlPort,
		dataPort:    dataPort,
		clients:     make(map[string]*ClientSession),
		stats:       &BandwidthStats{},
		ctx:         ctx,
		cancel:      cancel,
	}
}

func (s *Server) Start() error {
	log.Printf("Starting PISP Performance Server on control port %d, data port %d", s.controlPort, s.dataPort)
	
	// Start TCP control server
	tcpAddr, err := net.ResolveTCPAddr("tcp", fmt.Sprintf(":%d", s.controlPort))
	if err != nil {
		return fmt.Errorf("failed to resolve TCP address: %w", err)
	}
	
	s.tcpListener, err = net.ListenTCP("tcp", tcpAddr)
	if err != nil {
		return fmt.Errorf("failed to listen on TCP port %d: %w", s.controlPort, err)
	}
	
	// Start UDP data server
	udpAddr, err := net.ResolveUDPAddr("udp", fmt.Sprintf(":%d", s.dataPort))
	if err != nil {
		return fmt.Errorf("failed to resolve UDP address: %w", err)
	}
	
	s.udpConn, err = net.ListenUDP("udp", udpAddr)
	if err != nil {
		return fmt.Errorf("failed to listen on UDP port %d: %w", s.dataPort, err)
	}
	
	// Start background routines
	go s.acceptTCPConnections()
	go s.handleUDPData()
	go s.cleanupStaleClients()
	
	log.Println("PISP Performance Server started successfully")
	return nil
}

func (s *Server) Stop() error {
	log.Println("Stopping PISP Performance Server...")
	
	s.cancel()
	
	if s.tcpListener != nil {
		s.tcpListener.Close()
	}
	
	if s.udpConn != nil {
		s.udpConn.Close()
	}
	
	// Close all client connections
	s.clientsMux.Lock()
	for _, client := range s.clients {
		if client.TCPConn != nil {
			client.TCPConn.Close()
		}
	}
	s.clientsMux.Unlock()
	
	log.Println("PISP Performance Server stopped")
	return nil
}

func (s *Server) acceptTCPConnections() {
	for {
		select {
		case <-s.ctx.Done():
			return
		default:
			conn, err := s.tcpListener.Accept()
			if err != nil {
				if s.ctx.Err() != nil {
					return
				}
				log.Printf("Failed to accept TCP connection: %v", err)
				continue
			}
			
			go s.handleTCPClient(conn)
		}
	}
}

func (s *Server) handleTCPClient(conn net.Conn) {
	defer conn.Close()
	
	clientID := conn.RemoteAddr().String()
	log.Printf("New TCP client connected: %s", clientID)
	
	client := &ClientSession{
		ID:       clientID,
		TCPConn:  conn,
		LastSeen: time.Now(),
		Testing:  false,
	}
	
	s.clientsMux.Lock()
	s.clients[clientID] = client
	s.clientsMux.Unlock()
	
	defer func() {
		s.clientsMux.Lock()
		delete(s.clients, clientID)
		s.clientsMux.Unlock()
		log.Printf("TCP client disconnected: %s", clientID)
	}()
	
	scanner := bufio.NewScanner(conn)
	for scanner.Scan() {
		select {
		case <-s.ctx.Done():
			return
		default:
			line := strings.TrimSpace(scanner.Text())
			if line == "" {
				continue
			}
			
			s.processControlMessage(client, line)
			client.LastSeen = time.Now()
		}
	}
	
	if err := scanner.Err(); err != nil {
		log.Printf("Error reading from TCP client %s: %v", clientID, err)
	}
}

func (s *Server) processControlMessage(client *ClientSession, messageStr string) {
	var msg ControlMessage
	if err := json.Unmarshal([]byte(messageStr), &msg); err != nil {
		log.Printf("Failed to parse control message from %s: %v", client.ID, err)
		return
	}
	
	log.Printf("Received control message from %s: %s - %s", client.ID, msg.Command, msg.Data)
	
	switch msg.Command {
	case "CONNECT":
		s.sendControlMessage(client, "CONNECT_ACK", "Server ready")
		
	case "PING":
		s.sendControlMessage(client, "PONG", msg.Data)
		
	case "START_TEST":
		s.handleStartTest(client, msg.Data)
		
	case "STOP_TEST":
		s.handleStopTest(client, msg.Data)
		
	case "DISCONNECT":
		log.Printf("Client %s requested disconnect", client.ID)
		
	default:
		log.Printf("Unknown control command from %s: %s", client.ID, msg.Command)
	}
}

func (s *Server) handleStartTest(client *ClientSession, data string) {
	log.Printf("Starting bandwidth test for client %s", client.ID)
	
	client.Testing = true
	
	// Reset stats
	s.statsMux.Lock()
	s.stats = &BandwidthStats{
		StartTime: time.Now(),
	}
	s.statsMux.Unlock()
	
	// Parse test parameters
	params := make(map[string]string)
	if data != "" {
		pairs := strings.Split(data, ",")
		for _, pair := range pairs {
			if kv := strings.Split(pair, ":"); len(kv) == 2 {
				params[strings.TrimSpace(kv[0])] = strings.TrimSpace(kv[1])
			}
		}
	}
	
	duration := "10"
	if d, ok := params["duration"]; ok {
		duration = d
	}
	
	packetSize := "1024"
	if ps, ok := params["packetSize"]; ok {
		packetSize = ps
	}
	
	log.Printf("Test parameters - Duration: %ss, Packet Size: %s bytes", duration, packetSize)
	
	s.sendControlMessage(client, "TEST_READY", fmt.Sprintf("duration:%s,packetSize:%s", duration, packetSize))
}

func (s *Server) handleStopTest(client *ClientSession, data string) {
	log.Printf("Stopping bandwidth test for client %s", client.ID)
	
	client.Testing = false
	
	s.statsMux.Lock()
	stats := *s.stats
	if !stats.StartTime.IsZero() && !stats.LastPacketTime.IsZero() {
		stats.Duration = stats.LastPacketTime.Sub(stats.StartTime).Seconds()
		if stats.Duration > 0 {
			stats.BandwidthMbps = float64(stats.BytesReceived*8) / (stats.Duration * 1000000)
		}
	}
	s.statsMux.Unlock()
	
	resultsData := fmt.Sprintf("bytes_received:%d,packets_received:%d,duration:%.2f,bandwidth_mbps:%.2f",
		stats.BytesReceived, stats.PacketsReceived, stats.Duration, stats.BandwidthMbps)
	
	s.sendControlMessage(client, "TEST_RESULTS", resultsData)
	
	log.Printf("Test completed - Received %d bytes (%d packets) in %.2fs, Bandwidth: %.2f Mbps",
		stats.BytesReceived, stats.PacketsReceived, stats.Duration, stats.BandwidthMbps)
}

func (s *Server) sendControlMessage(client *ClientSession, command, data string) {
	msg := ControlMessage{
		Command:   command,
		Data:      data,
		Timestamp: float64(time.Now().UnixNano()) / 1e9,
	}
	
	jsonData, err := json.Marshal(msg)
	if err != nil {
		log.Printf("Failed to marshal control message: %v", err)
		return
	}
	
	_, err = client.TCPConn.Write(append(jsonData, '\n'))
	if err != nil {
		log.Printf("Failed to send control message to %s: %v", client.ID, err)
	}
}

func (s *Server) handleUDPData() {
	buffer := make([]byte, 65536)
	
	for {
		select {
		case <-s.ctx.Done():
			return
		default:
			s.udpConn.SetReadDeadline(time.Now().Add(100 * time.Millisecond))
			n, addr, err := s.udpConn.ReadFromUDP(buffer)
			if err != nil {
				if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
					continue
				}
				if s.ctx.Err() != nil {
					return
				}
				log.Printf("Error reading UDP data: %v", err)
				continue
			}
			
			s.processUDPPacket(addr, buffer[:n])
		}
	}
}

func (s *Server) processUDPPacket(addr *net.UDPAddr, data []byte) {
	// Update client UDP address if we have a corresponding TCP client
	clientID := fmt.Sprintf("%s:%d", addr.IP.String(), addr.Port-1) // Assume control port is data port - 1
	
	s.clientsMux.RLock()
	client, exists := s.clients[clientID]
	s.clientsMux.RUnlock()
	
	if exists {
		client.UDPAddr = addr
		client.LastSeen = time.Now()
		
		if client.Testing {
			s.updateStats(len(data))
		}
	} else {
		// Create a temporary entry for UDP-only traffic
		s.updateStats(len(data))
	}
}

func (s *Server) updateStats(packetSize int) {
	s.statsMux.Lock()
	defer s.statsMux.Unlock()
	
	s.stats.BytesReceived += int64(packetSize)
	s.stats.PacketsReceived++
	s.stats.LastPacketTime = time.Now()
	
	if !s.stats.StartTime.IsZero() {
		duration := time.Since(s.stats.StartTime).Seconds()
		if duration > 0 {
			s.stats.BandwidthMbps = float64(s.stats.BytesReceived*8) / (duration * 1000000)
		}
	}
}

func (s *Server) cleanupStaleClients() {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()
	
	for {
		select {
		case <-s.ctx.Done():
			return
		case <-ticker.C:
			s.clientsMux.Lock()
			for id, client := range s.clients {
				if time.Since(client.LastSeen) > 60*time.Second {
					log.Printf("Cleaning up stale client: %s", id)
					if client.TCPConn != nil {
						client.TCPConn.Close()
					}
					delete(s.clients, id)
				}
			}
			s.clientsMux.Unlock()
		}
	}
}

func (s *Server) printStats() {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()
	
	for {
		select {
		case <-s.ctx.Done():
			return
		case <-ticker.C:
			s.statsMux.RLock()
			stats := *s.stats
			s.statsMux.RUnlock()
			
			s.clientsMux.RLock()
			clientCount := len(s.clients)
			testingCount := 0
			for _, client := range s.clients {
				if client.Testing {
					testingCount++
				}
			}
			s.clientsMux.RUnlock()
			
			if stats.BytesReceived > 0 {
				log.Printf("Stats - Clients: %d (Testing: %d), Received: %d bytes (%d packets), Current Bandwidth: %.2f Mbps",
					clientCount, testingCount, stats.BytesReceived, stats.PacketsReceived, stats.BandwidthMbps)
			}
		}
	}
}

// Client methods
func NewClient(host string, controlPort, dataPort int) *Client {
	ctx, cancel := context.WithCancel(context.Background())
	return &Client{
		host:        host,
		controlPort: controlPort,
		dataPort:    dataPort,
		ctx:         ctx,
		cancel:      cancel,
	}
}

func (c *Client) Connect() error {
	// Connect TCP control channel
	tcpAddr := fmt.Sprintf("%s:%d", c.host, c.controlPort)
	conn, err := net.Dial("tcp", tcpAddr)
	if err != nil {
		return fmt.Errorf("failed to connect to TCP control port: %v", err)
	}
	c.tcpConn = conn
	
	// Setup UDP connection
	udpAddr := fmt.Sprintf("%s:%d", c.host, c.dataPort)
	serverAddr, err := net.ResolveUDPAddr("udp", udpAddr)
	if err != nil {
		c.tcpConn.Close()
		return fmt.Errorf("failed to resolve UDP address: %v", err)
	}
	c.serverAddr = serverAddr
	
	udpConn, err := net.DialUDP("udp", nil, serverAddr)
	if err != nil {
		c.tcpConn.Close()
		return fmt.Errorf("failed to connect to UDP data port: %v", err)
	}
	c.udpConn = udpConn
	
	// Send connect message
	return c.sendControlMessage("CONNECT", "Go client connected")
}

func (c *Client) Close() {
	if c.tcpConn != nil {
		c.sendControlMessage("DISCONNECT", "Go client disconnecting")
		c.tcpConn.Close()
	}
	if c.udpConn != nil {
		c.udpConn.Close()
	}
	c.cancel()
}

func (c *Client) RunBandwidthTest(payloadSize int, duration time.Duration) (TestResult, error) {
	result := TestResult{
		PayloadSize: payloadSize,
	}
	
	// Send start test command
	testParams := fmt.Sprintf("duration:%d,packetSize:%d", int(duration.Seconds()), payloadSize)
	if err := c.sendControlMessage("START_TEST", testParams); err != nil {
		return result, err
	}
	
	// Create test data
	testData := make([]byte, payloadSize)
	for i := range testData {
		testData[i] = byte(i % 256)
	}
	
	// Run test
	startTime := time.Now()
	endTime := startTime.Add(duration)
	var bytesSent int64
	
	// Send ping for latency measurement
	pingStart := time.Now()
	c.sendControlMessage("PING", fmt.Sprintf("%.6f", float64(pingStart.UnixNano())/1e9))
	
	for time.Now().Before(endTime) {
		_, err := c.udpConn.Write(testData)
		if err != nil {
			log.Printf("UDP send error: %v", err)
			continue
		}
		bytesSent += int64(len(testData))
		
		// Small delay to prevent overwhelming
		time.Sleep(time.Millisecond)
	}
	
	actualDuration := time.Since(startTime)
	
	// Calculate bandwidth
	bandwidthMbps := (float64(bytesSent) * 8.0) / (actualDuration.Seconds() * 1000000.0)
	
	// Send stop test command
	stopParams := fmt.Sprintf("bytes_sent:%d,duration:%.2f,bandwidth_mbps:%.2f", 
		bytesSent, actualDuration.Seconds(), bandwidthMbps)
	c.sendControlMessage("STOP_TEST", stopParams)
	
	result.BandwidthMbps = bandwidthMbps
	result.BytesSent = bytesSent
	result.Duration = actualDuration
	result.LatencyMs = 0.0 // TODO: Implement proper latency measurement
	
	return result, nil
}

func (c *Client) sendControlMessage(command, data string) error {
	if c.tcpConn == nil {
		return fmt.Errorf("TCP connection not established")
	}
	
	message := ControlMessage{
		Command:   command,
		Data:      data,
		Timestamp: float64(time.Now().UnixNano()) / 1e9,
	}
	
	messageBytes, err := json.Marshal(message)
	if err != nil {
		return err
	}
	
	messageBytes = append(messageBytes, '\n')
	_, err = c.tcpConn.Write(messageBytes)
	return err
}

func main() {
	var (
		mode        = flag.String("mode", "server", "Mode: 'server' or 'client'")
		host        = flag.String("host", "127.0.0.1", "Server host (for client mode)")
		controlPort = flag.Int("control-port", 5201, "Control port")
		dataPort    = flag.Int("data-port", 5202, "Data port")
		testSizes   = flag.String("test-sizes", "32,64,128,256,512,1024,2048,4096,8192,16384,32768,65536,131072,262144,524288,1048576", "Comma-separated list of payload sizes to test (client mode)")
		duration    = flag.Int("duration", 5, "Test duration per size in seconds (client mode)")
	)
	flag.Parse()

	if *mode == "client" {
		runClient(*host, *controlPort, *dataPort, *testSizes, *duration)
	} else {
		runServer(*controlPort, *dataPort)
	}
}

func runServer(controlPort, dataPort int) {
	server := NewServer(controlPort, dataPort)
	
	// Handle graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	
	// Start server
	if err := server.Start(); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
	
	// Start stats reporting
	go server.printStats()
	
	// Wait for shutdown signal
	<-sigChan
	log.Println("Received shutdown signal")
	
	// Graceful shutdown
	if err := server.Stop(); err != nil {
		log.Printf("Error during shutdown: %v", err)
	}
	
	log.Println("Server shutdown complete")
}

func runClient(host string, controlPort, dataPort int, testSizesStr string, durationSec int) {
	log.Printf("Starting pisp-perf client, connecting to %s:%d", host, controlPort)
	
	// Parse test sizes
	testSizes, err := parseTestSizes(testSizesStr)
	if err != nil {
		log.Fatalf("Failed to parse test sizes: %v", err)
	}
	
	client := NewClient(host, controlPort, dataPort)
	defer client.Close()
	
	if err := client.Connect(); err != nil {
		log.Fatalf("Failed to connect to server: %v", err)
	}
	
	log.Printf("Connected to server. Running bandwidth tests across %d payload sizes", len(testSizes))
	
	results := make([]TestResult, 0, len(testSizes))
	
	for i, size := range testSizes {
		log.Printf("Testing payload size %d bytes (%d/%d)", size, i+1, len(testSizes))
		
		result, err := client.RunBandwidthTest(size, time.Duration(durationSec)*time.Second)
		if err != nil {
			log.Printf("Test failed for size %d: %v", size, err)
			continue
		}
		
		results = append(results, result)
		log.Printf("Result: %d bytes -> %.2f Mbps, %.1f ms latency", 
			size, result.BandwidthMbps, result.LatencyMs)
		
		// Small delay between tests
		time.Sleep(500 * time.Millisecond)
	}
	
	// Print summary
	printClientSummary(results)
}

func parseTestSizes(testSizesStr string) ([]int, error) {
	parts := strings.Split(testSizesStr, ",")
	sizes := make([]int, 0, len(parts))
	
	for _, part := range parts {
		size, err := strconv.Atoi(strings.TrimSpace(part))
		if err != nil {
			return nil, fmt.Errorf("invalid size '%s': %v", part, err)
		}
		sizes = append(sizes, size)
	}
	
	return sizes, nil
}

func printClientSummary(results []TestResult) {
	if len(results) == 0 {
		log.Println("No test results to display")
		return
	}
	
	log.Println("\n=== BANDWIDTH TEST RESULTS ===")
	log.Printf("Completed %d tests", len(results))
	
	var maxBandwidth float64
	var totalLatency float64
	
	for _, result := range results {
		if result.BandwidthMbps > maxBandwidth {
			maxBandwidth = result.BandwidthMbps
		}
		totalLatency += result.LatencyMs
	}
	
	avgLatency := totalLatency / float64(len(results))
	
	log.Printf("Peak bandwidth: %.2f Mbps", maxBandwidth)
	log.Printf("Average latency: %.1f ms", avgLatency)
	
	log.Println("\nDetailed results:")
	for _, result := range results {
		log.Printf("  %8d bytes: %8.2f Mbps, %6.1f ms", 
			result.PayloadSize, result.BandwidthMbps, result.LatencyMs)
	}
}