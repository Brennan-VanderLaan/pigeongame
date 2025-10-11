using System;
using System.Collections;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using UnityEngine.InputSystem;

public class NetworkBandwidthTester : MonoBehaviour
{
    [Header("Server Configuration")]
    public string serverIP = "127.0.0.1";
    public int controlPort = 5201;
    public int dataPort = 5202;
    
    [Header("Test Configuration")]
    public int testDurationSeconds = 10;
    public int packetSize = 1024;
    public float sendIntervalMs = 1f;
    
    [Header("Multi-Size Test Configuration")]
    public bool runMultiSizeTest = true;
    public int[] testPayloadSizes = { 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072, 262144, 524288, 1048576 }; // 32B to 1MB
    public int testDurationPerSizeSeconds = 5;
    
    [Header("Status")]
    public bool isConnected = false;
    public bool isTesting = false;
    public float currentBandwidthMbps = 0f;
    public float averageLatencyMs = 0f;
    
    [Header("UI Components")]
    public TextMeshProUGUI debugText;
    
    private TcpClient tcpClient;
    private NetworkStream tcpStream;
    private UdpClient udpClient;
    private IPEndPoint serverEndPoint;
    private Thread tcpThread;
    private Thread udpThread;
    private bool shouldStop = false;
    
    private long totalBytesSent = 0;
    private long totalBytesReceived = 0;
    private float testStartTime = 0f;
    private float lastLatencyMs = 0f;
    
    // Multi-size test state
    private bool isRunningMultiSizeTest = false;
    private int currentTestSizeIndex = 0;
    private Coroutine multiSizeTestCoroutine = null;
    
    // Test results for graphing
    [System.Serializable]
    public class TestResult
    {
        public int payloadSize;
        public float bandwidthMbps;
        public float latencyMs;
        public long totalBytes;
        public float duration;
        public float timestamp;
    }
    
    private List<TestResult> testResults = new List<TestResult>();
    
    [System.Serializable]
    public class ControlMessage
    {
        public string command;
        public string data;
        public float timestamp;
        
        public string ToJson()
        {
            return JsonUtility.ToJson(this);
        }
        
        public static ControlMessage FromJson(string json)
        {
            return JsonUtility.FromJson<ControlMessage>(json);
        }
    }
    
    void Start()
    {
        Debug.Log("NetworkBandwidthTester initialized");
        Debug.Log("Keyboard Controls:");
        Debug.Log("1 - Connect to Server");
        Debug.Log("2 - Disconnect from Server");
        Debug.Log("3 - Start Single Bandwidth Test");
        Debug.Log("4 - Start Multi-Size Test");
        Debug.Log("5 - Stop Test");
        Debug.Log("6 - Send Ping");
        Debug.Log("7 - Clear Results");
        
        // Force initial display update
        UpdateDebugDisplay();
        
        // Check if debugText is assigned
        if (debugText == null)
        {
            Debug.LogError("debugText is not assigned! Please assign a TextMeshProUGUI component in the inspector.");
        }
        else
        {
            Debug.Log("debugText component found and assigned correctly.");
        }
    }
    
    void Update()
    {
        // Handle keyboard input
        HandleKeyboardInput();
        
        // Update bandwidth calculation
        if (isTesting && testStartTime > 0f)
        {
            float elapsedTime = Time.time - testStartTime;
            if (elapsedTime > 0f)
            {
                currentBandwidthMbps = (totalBytesSent * 8f) / (elapsedTime * 1000000f);
            }
        }
        
        UpdateDebugDisplay();
    }
    
    private void HandleKeyboardInput()
    {
        var keyboard = Keyboard.current;
        if (keyboard == null) return;
        
        if (keyboard.digit1Key.wasPressedThisFrame)
        {
            Debug.Log("Key 1: Connect to Server");
            ConnectToServer();
        }
        else if (keyboard.digit2Key.wasPressedThisFrame)
        {
            Debug.Log("Key 2: Disconnect from Server");
            Disconnect();
        }
        else if (keyboard.digit3Key.wasPressedThisFrame)
        {
            Debug.Log("Key 3: Start Single Bandwidth Test");
            StartSingleBandwidthTest();
        }
        else if (keyboard.digit4Key.wasPressedThisFrame)
        {
            Debug.Log("Key 4: Start Multi-Size Test");
            StartMultiSizeBandwidthTest();
        }
        else if (keyboard.digit5Key.wasPressedThisFrame)
        {
            Debug.Log("Key 5: Stop Test");
            StopBandwidthTest();
        }
        else if (keyboard.digit6Key.wasPressedThisFrame)
        {
            Debug.Log("Key 6: Send Ping");
            SendPing();
        }
        else if (keyboard.digit7Key.wasPressedThisFrame)
        {
            Debug.Log("Key 7: Clear Results");
            ClearTestResults();
        }
    }
    
    public void ConnectToServer()
    {
        if (isConnected) return;
        
        try
        {
            serverEndPoint = new IPEndPoint(IPAddress.Parse(serverIP), dataPort);
            
            Debug.Log($"Connecting to server at {serverIP}:{controlPort}");
            
            tcpClient = new TcpClient();
            tcpClient.Connect(serverIP, controlPort);
            tcpStream = tcpClient.GetStream();
            isConnected = true;
            
            udpClient = new UdpClient();
            udpClient.Connect(serverEndPoint);
            
            shouldStop = false;
            tcpThread = new Thread(TcpListenerLoop);
            tcpThread.Start();
            
            SendControlMessage("CONNECT", $"Unity client connected");
            
            Debug.Log("Connected to server successfully");
        }
        catch (Exception e)
        {
            Debug.LogError($"Failed to connect to server: {e.Message}");
            Disconnect();
        }
    }
    
    public void Disconnect()
    {
        shouldStop = true;
        isConnected = false;
        isTesting = false;
        
        try
        {
            if (tcpStream != null)
            {
                SendControlMessage("DISCONNECT", "Unity client disconnecting");
                tcpStream.Close();
            }
            tcpClient?.Close();
            udpClient?.Close();
            
            if (tcpThread != null && tcpThread.IsAlive)
            {
                tcpThread.Join(1000);
            }
            
            if (udpThread != null && udpThread.IsAlive)
            {
                udpThread.Join(1000);
            }
        }
        catch (Exception e)
        {
            Debug.LogError($"Error during disconnect: {e.Message}");
        }
        
        Debug.Log("Disconnected from server");
    }
    
    public void StartSingleBandwidthTest()
    {
        if (!isConnected || isTesting || isRunningMultiSizeTest) return;
        
        StartBandwidthTestWithSize(packetSize, testDurationSeconds);
    }
    
    public void StartMultiSizeBandwidthTest()
    {
        if (!isConnected || isTesting || isRunningMultiSizeTest) return;
        
        if (multiSizeTestCoroutine != null)
        {
            StopCoroutine(multiSizeTestCoroutine);
        }
        
        multiSizeTestCoroutine = StartCoroutine(RunMultiSizeTest());
    }
    
    private void StartBandwidthTestWithSize(int size, int duration)
    {
        if (!isConnected || isTesting) return;
        
        packetSize = size; // Update current packet size
        SendControlMessage("START_TEST", $"duration:{duration},packetSize:{size}");
        
        isTesting = true;
        testStartTime = Time.time;
        totalBytesSent = 0;
        totalBytesReceived = 0;
        
        udpThread = new Thread(UdpSenderLoop);
        udpThread.Start();
        
        Debug.Log($"Started bandwidth test with {size} byte packets for {duration} seconds");
    }
    
    public void StopBandwidthTest()
    {
        // Stop multi-size test if running
        if (isRunningMultiSizeTest)
        {
            isRunningMultiSizeTest = false;
            if (multiSizeTestCoroutine != null)
            {
                StopCoroutine(multiSizeTestCoroutine);
                multiSizeTestCoroutine = null;
            }
            Debug.Log("Multi-size test stopped.");
        }
        
        if (!isTesting) return;
        
        isTesting = false;
        shouldStop = true;
        
        if (udpThread != null && udpThread.IsAlive)
        {
            udpThread.Join(1000);
        }
        
        float testDuration = Time.time - testStartTime;
        float finalBandwidthMbps = (totalBytesSent * 8f) / (testDuration * 1000000f);
        
        // Save test result
        SaveTestResult(packetSize, finalBandwidthMbps, lastLatencyMs, totalBytesSent, testDuration);
        
        SendControlMessage("STOP_TEST", $"bytes_sent:{totalBytesSent},duration:{testDuration:F2},bandwidth_mbps:{finalBandwidthMbps:F2}");
        
        Debug.Log($"Test completed. Sent {totalBytesSent} bytes in {testDuration:F2}s. Bandwidth: {finalBandwidthMbps:F2} Mbps");
        
        shouldStop = false;
    }
    
    private void StopCurrentTest()
    {
        if (!isTesting) return;
        
        isTesting = false;
        shouldStop = true;
        
        if (udpThread != null && udpThread.IsAlive)
        {
            udpThread.Join(1000);
        }
        
        float testDuration = Time.time - testStartTime;
        float finalBandwidthMbps = (totalBytesSent * 8f) / (testDuration * 1000000f);
        
        // Save test result
        SaveTestResult(packetSize, finalBandwidthMbps, lastLatencyMs, totalBytesSent, testDuration);
        
        SendControlMessage("STOP_TEST", $"bytes_sent:{totalBytesSent},duration:{testDuration:F2},bandwidth_mbps:{finalBandwidthMbps:F2}");
        
        Debug.Log($"Test completed. Sent {totalBytesSent} bytes in {testDuration:F2}s. Bandwidth: {finalBandwidthMbps:F2} Mbps");
        
        shouldStop = false;
    }
    
    private IEnumerator StopTestAfterDuration()
    {
        yield return new WaitForSeconds(testDurationSeconds);
        if (isTesting)
        {
            StopBandwidthTest();
        }
    }
    
    private IEnumerator RunMultiSizeTest()
    {
        isRunningMultiSizeTest = true;
        currentTestSizeIndex = 0;
        
        Debug.Log($"Starting multi-size test with {testPayloadSizes.Length} different payload sizes");
        
        for (int i = 0; i < testPayloadSizes.Length; i++)
        {
            if (!isRunningMultiSizeTest || !isConnected) break;
            
            currentTestSizeIndex = i;
            int currentSize = testPayloadSizes[i];
            
            Debug.Log($"Testing payload size: {currentSize} bytes ({i + 1}/{testPayloadSizes.Length})");
            
            // Start test for this size
            StartBandwidthTestWithSize(currentSize, testDurationPerSizeSeconds);
            
            // Wait for test to complete
            yield return new WaitForSeconds(testDurationPerSizeSeconds + 0.5f); // Small buffer
            
            // Stop current test
            if (isTesting)
            {
                StopCurrentTest();
            }
            
            // Small delay between tests
            yield return new WaitForSeconds(1f);
        }
        
        isRunningMultiSizeTest = false;
        multiSizeTestCoroutine = null;
        
        Debug.Log($"Multi-size test completed! Collected {testResults.Count} results.");
    }
    
    private void SaveTestResult(int payloadSize, float bandwidthMbps, float latencyMs, long totalBytes, float duration)
    {
        var result = new TestResult
        {
            payloadSize = payloadSize,
            bandwidthMbps = bandwidthMbps,
            latencyMs = latencyMs,
            totalBytes = totalBytes,
            duration = duration,
            timestamp = Time.time
        };
        
        testResults.Add(result);
        Debug.Log($"Saved result: {payloadSize}B -> {bandwidthMbps:F2} Mbps, {latencyMs:F1} ms");
    }
    
    public void ClearTestResults()
    {
        testResults.Clear();
        Debug.Log("Test results cleared.");
    }
    
    private void SendControlMessage(string command, string data = "")
    {
        if (tcpStream == null || !tcpStream.CanWrite) return;
        
        try
        {
            var message = new ControlMessage
            {
                command = command,
                data = data,
                timestamp = Time.time
            };
            
            string json = message.ToJson();
            byte[] messageBytes = Encoding.UTF8.GetBytes(json + "\n");
            tcpStream.Write(messageBytes, 0, messageBytes.Length);
            tcpStream.Flush();
        }
        catch (Exception e)
        {
            Debug.LogError($"Failed to send control message: {e.Message}");
        }
    }
    
    private void TcpListenerLoop()
    {
        byte[] buffer = new byte[4096];
        StringBuilder messageBuilder = new StringBuilder();
        
        try
        {
            while (!shouldStop && tcpStream != null && tcpStream.CanRead)
            {
                if (tcpStream.DataAvailable)
                {
                    int bytesRead = tcpStream.Read(buffer, 0, buffer.Length);
                    if (bytesRead > 0)
                    {
                        string received = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                        messageBuilder.Append(received);
                        
                        string messages = messageBuilder.ToString();
                        string[] lines = messages.Split('\n');
                        
                        for (int i = 0; i < lines.Length - 1; i++)
                        {
                            if (!string.IsNullOrEmpty(lines[i]))
                            {
                                ProcessControlMessage(lines[i]);
                            }
                        }
                        
                        messageBuilder.Clear();
                        if (!string.IsNullOrEmpty(lines[lines.Length - 1]))
                        {
                            messageBuilder.Append(lines[lines.Length - 1]);
                        }
                    }
                }
                Thread.Sleep(10);
            }
        }
        catch (Exception e)
        {
            Debug.LogError($"TCP listener error: {e.Message}");
        }
    }
    
    private void ProcessControlMessage(string json)
    {
        try
        {
            var message = ControlMessage.FromJson(json);
            Debug.Log($"Received control message: {message.command} - {message.data}");
            
            switch (message.command)
            {
                case "PONG":
                    float latency = (Time.time - message.timestamp) * 1000f;
                    lastLatencyMs = latency;
                    averageLatencyMs = (averageLatencyMs + latency) / 2f;
                    Debug.Log($"Ping response received. Latency: {latency:F2}ms");
                    break;
                case "TEST_READY":
                    Debug.Log("Server is ready for bandwidth test");
                    break;
                case "TEST_RESULTS":
                    Debug.Log($"Server test results: {message.data}");
                    break;
            }
        }
        catch (Exception e)
        {
            Debug.LogError($"Failed to process control message: {e.Message}");
        }
    }
    
    private void UdpSenderLoop()
    {
        byte[] testData = new byte[packetSize];
        for (int i = 0; i < packetSize; i++)
        {
            testData[i] = (byte)(i % 256);
        }
        
        try
        {
            while (isTesting && !shouldStop)
            {
                udpClient.Send(testData, testData.Length);
                totalBytesSent += testData.Length;
                
                Thread.Sleep(Mathf.RoundToInt(sendIntervalMs));
            }
        }
        catch (Exception e)
        {
            Debug.LogError($"UDP sender error: {e.Message}");
        }
    }
    
    public void SendPing()
    {
        SendControlMessage("PING", Time.time.ToString());
    }
    
    void OnDestroy()
    {
        Disconnect();
    }
    
    void OnApplicationPause(bool pauseStatus)
    {
        if (pauseStatus)
        {
            Disconnect();
        }
    }
    
    private void UpdateDebugDisplay()
    {
        if (debugText == null) 
        {
            Debug.LogWarning("UpdateDebugDisplay called but debugText is null!");
            return;
        }
        
        var sb = new StringBuilder();
        sb.AppendLine("=== BASELINE NETWORK CAPABILITY ===");
        sb.AppendLine();
        
        // Connection Status
        string statusColor = isConnected ? "#00FF00" : "#FF0000";
        sb.AppendLine($"<color={statusColor}>● {(isConnected ? "CONNECTED" : "DISCONNECTED")}</color>");
        if (isConnected)
        {
            sb.AppendLine($"Server: {serverIP}:{controlPort}");
        }
        sb.AppendLine();
        
        // Current Test Metrics
        sb.AppendLine("=== REAL-TIME METRICS ===");
        if (isTesting)
        {
            float elapsed = Time.time - testStartTime;
            float remaining = Mathf.Max(0f, testDurationSeconds - elapsed);
            sb.AppendLine($"<color=#FFFF00>🔄 TEST RUNNING</color> ({remaining:F1}s remaining)");
            sb.AppendLine();
            
            // Key performance indicators
            sb.AppendLine($"<size=16><color=#00FFFF>BANDWIDTH: {currentBandwidthMbps:F2} Mbps</color></size>");
            sb.AppendLine($"<size=16><color=#FF8800>LATENCY: {lastLatencyMs:F1} ms</color></size>");
            sb.AppendLine();
            
            // Throughput details
            sb.AppendLine("=== THROUGHPUT DETAILS ===");
            sb.AppendLine($"Data Sent: {totalBytesSent:N0} bytes");
            sb.AppendLine($"Packets/sec: {(totalBytesSent / packetSize) / elapsed:F1}");
            sb.AppendLine($"Avg Latency: {averageLatencyMs:F1} ms");
        }
        else
        {
            sb.AppendLine($"<color=#888888>⏸ IDLE</color>");
            sb.AppendLine();
            sb.AppendLine($"<size=16>Last Bandwidth: {currentBandwidthMbps:F2} Mbps</size>");
            sb.AppendLine($"<size=16>Last Latency: {lastLatencyMs:F1} ms</size>");
        }
        sb.AppendLine();
        
        // Multi-Size Test Status
        if (isRunningMultiSizeTest)
        {
            sb.AppendLine("=== MULTI-SIZE TEST PROGRESS ===");
            sb.AppendLine($"<color=#FFFF00>🔄 RUNNING MULTI-SIZE TEST</color>");
            sb.AppendLine($"Progress: {currentTestSizeIndex + 1}/{testPayloadSizes.Length}");
            if (currentTestSizeIndex < testPayloadSizes.Length)
            {
                sb.AppendLine($"Current Size: {testPayloadSizes[currentTestSizeIndex]:N0} bytes");
            }
            sb.AppendLine($"Results Collected: {testResults.Count}");
            sb.AppendLine();
        }
        
        // Test Results Summary
        if (testResults.Count > 0)
        {
            sb.AppendLine("=== TEST RESULTS SUMMARY ===");
            sb.AppendLine($"Results Collected: {testResults.Count}");
            if (testResults.Count > 0)
            {
                float maxBandwidth = 0f;
                foreach (var result in testResults)
                {
                    if (result.bandwidthMbps > maxBandwidth) maxBandwidth = result.bandwidthMbps;
                }
                sb.AppendLine($"Peak Bandwidth: {maxBandwidth:F2} Mbps");
            }
            sb.AppendLine();
        }
        
        // Test Configuration
        sb.AppendLine("=== TEST CONFIGURATION ===");
        sb.AppendLine($"Single Test - Packet Size: {packetSize:N0} bytes");
        sb.AppendLine($"Multi Test - Sizes: {testPayloadSizes.Length} from 32B to 1MB");
        sb.AppendLine($"Test Duration: {testDurationPerSizeSeconds}s per size");
        sb.AppendLine();
        
        // Keyboard Controls
        sb.AppendLine("=== KEYBOARD CONTROLS ===");
        sb.AppendLine("<color=#FFFF00>1</color> - Connect to Server");
        sb.AppendLine("<color=#FFFF00>2</color> - Disconnect");
        sb.AppendLine("<color=#FFFF00>3</color> - Start Single Test");
        sb.AppendLine("<color=#FFFF00>4</color> - Start Multi-Size Test");
        sb.AppendLine("<color=#FFFF00>5</color> - Stop Test");
        sb.AppendLine("<color=#FFFF00>6</color> - Send Ping");
        sb.AppendLine("<color=#FFFF00>7</color> - Clear Results");
        sb.AppendLine();
        
        // Purpose statement
        sb.AppendLine("=== PURPOSE ===");
        sb.AppendLine("Measuring baseline network capability");
        sb.AppendLine("across payload sizes for comparison");
        sb.AppendLine("with in-game performance.");
        
        debugText.text = sb.ToString();
    }
    
    // Fallback GUI display in case TextMeshPro isn't set up
    void OnGUI()
    {
        if (debugText != null) return; // Only show if TextMeshPro isn't assigned
        
        GUILayout.BeginArea(new Rect(10, 10, 400, 300));
        GUILayout.Label("=== NETWORK BANDWIDTH TESTER ===");
        GUILayout.Space(10);
        
        GUILayout.Label($"Connection: {(isConnected ? "CONNECTED" : "DISCONNECTED")}");
        GUILayout.Label($"Test Status: {(isTesting ? "RUNNING" : "IDLE")}");
        GUILayout.Label($"Bandwidth: {currentBandwidthMbps:F2} Mbps");
        GUILayout.Label($"Latency: {lastLatencyMs:F1} ms");
        
        GUILayout.Space(10);
        GUILayout.Label("=== KEYBOARD CONTROLS ===");
        GUILayout.Label("1 - Connect to Server");
        GUILayout.Label("2 - Disconnect");
        GUILayout.Label("3 - Start Bandwidth Test");
        GUILayout.Label("4 - Stop Test");
        GUILayout.Label("5 - Send Ping");
        
        GUILayout.Space(10);
        GUILayout.Label("Assign a TextMeshProUGUI to debugText for better display");
        
        GUILayout.EndArea();
    }
}