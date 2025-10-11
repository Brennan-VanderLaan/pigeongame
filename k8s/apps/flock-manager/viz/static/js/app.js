const API_BASE = '';
let currentMeshId = null;
let meshes = [];
let nodes = [];
let hubs = [];
let pollingInterval = null;
let pollingEnabled = true;
const POLL_INTERVAL_MS = 2000; // Poll every 2 seconds

function showMessage(message, isError = false) {
    const messagesDiv = document.getElementById('messages');
    messagesDiv.innerHTML = `<div class="${isError ? 'error' : 'success'}">${message}</div>`;
    setTimeout(() => messagesDiv.innerHTML = '', 5000);
}

async function createMesh() {
    const name = document.getElementById('meshName').value;
    if (!name) {
        showMessage('Please enter a mesh name', true);
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/mesh`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name})
        });

        if (response.ok) {
            showMessage('Mesh created successfully');
            document.getElementById('meshName').value = '';
            loadMeshes();
        } else {
            showMessage('Failed to create mesh', true);
        }
    } catch (error) {
        showMessage('Error creating mesh: ' + error.message, true);
    }
}

async function loadMeshes() {
    try {
        const response = await fetch(`${API_BASE}/mesh`);
        if (response.ok) {
            meshes = await response.json();
            displayMeshes();
            updateMeshSelect();

            // Auto-select if there's exactly one mesh
            if (meshes.length === 1 && !currentMeshId) {
                selectMesh(meshes[0].id);
            }
        } else {
            showMessage('Failed to load meshes', true);
        }
    } catch (error) {
        showMessage('Error loading meshes: ' + error.message, true);
    }
}

function displayMeshes() {
    const meshListDiv = document.getElementById('meshList');
    if (meshes.length === 0) {
        meshListDiv.innerHTML = '<p>No meshes found</p>';
        return;
    }

    meshListDiv.innerHTML = meshes.map(mesh => `
        <div class="item compact-item">
            <h4>${mesh.name} <small style="color: #666;">(${mesh.nodes.length} nodes, ${mesh.hubs.length} hubs)</small></h4>
            <div class="inline-actions">
                <button class="btn" onclick="selectMesh('${mesh.id}')">Select</button>
                <button class="btn btn-danger" onclick="deleteMesh('${mesh.id}')">Delete</button>
            </div>
        </div>
    `).join('');
}

function updateMeshSelect() {
    const select = document.getElementById('selectedMesh');
    select.innerHTML = '<option value="">Select a mesh</option>' +
        meshes.map(mesh => `<option value="${mesh.id}">${mesh.name}</option>`).join('');
}

async function selectMesh(meshId) {
    currentMeshId = meshId;
    document.getElementById('selectedMesh').value = meshId;

    try {
        const response = await fetch(`${API_BASE}/mesh/${meshId}`);
        if (response.ok) {
            const mesh = await response.json();
            nodes = mesh.nodes;
            hubs = mesh.hubs;
            displayNodes();
            displayHubs();
            updateNodeSelects();
            updateHubSelect();
            showMessage(`Selected mesh: ${mesh.name}`);
        } else {
            showMessage('Failed to load mesh details', true);
        }
    } catch (error) {
        showMessage('Error loading mesh: ' + error.message, true);
    }
}

async function deleteMesh(meshId) {
    if (!confirm('Are you sure you want to delete this mesh?')) return;

    try {
        const response = await fetch(`${API_BASE}/mesh/${meshId}`, {method: 'DELETE'});
        if (response.ok) {
            showMessage('Mesh deleted successfully');
            if (currentMeshId === meshId) {
                currentMeshId = null;
                nodes = [];
                hubs = [];
                displayNodes();
                displayHubs();
                updateNodeSelects();
                updateHubSelect();
                updateTopologyDisplay();
                // Clear the graph
                if (network) {
                    network.destroy();
                    network = null;
                }
            }
            loadMeshes();
        } else {
            showMessage('Failed to delete mesh', true);
        }
    } catch (error) {
        showMessage('Error deleting mesh: ' + error.message, true);
    }
}

async function addNode() {
    if (!currentMeshId) {
        showMessage('Please select a mesh first', true);
        return;
    }

    const name = document.getElementById('nodeName').value;
    const addrsStr = document.getElementById('nodeAddrs').value;
    const dataStr = document.getElementById('nodeData').value;

    if (!name || !addrsStr) {
        showMessage('Please enter node name and addresses', true);
        return;
    }

    const addrs = addrsStr.split(',').map(addr => addr.trim());

    // Parse JSON data if provided
    let data = {};
    if (dataStr.trim()) {
        try {
            data = JSON.parse(dataStr);
        } catch (e) {
            showMessage('Invalid JSON in node data field: ' + e.message, true);
            return;
        }
    }

    try {
        const response = await fetch(`${API_BASE}/mesh/${currentMeshId}/node`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, addrs, data})
        });

        if (response.ok) {
            showMessage('Node added successfully');
            document.getElementById('nodeName').value = '';
            document.getElementById('nodeAddrs').value = '';
            document.getElementById('nodeData').value = '';
            selectMesh(currentMeshId); // Refresh
        } else {
            showMessage('Failed to add node', true);
        }
    } catch (error) {
        showMessage('Error adding node: ' + error.message, true);
    }
}

function displayNodes() {
    const nodeListDiv = document.getElementById('nodeList');
    if (nodes.length === 0) {
        nodeListDiv.innerHTML = '<p>No nodes found</p>';
        return;
    }

    nodeListDiv.innerHTML = nodes.map(node => {
        const isHub = hubs.some(hub => hub.node_id === node.id);
        return `
            <div class="item compact-item clickable-node" onclick="selectNodeForAction('${node.id}')">
                <h4>${node.name} ${isHub ? '🔶' : ''} <small style="color: #888;">${node.addrs[0] || ''}</small></h4>
                ${node.addrs.length > 1 ? `<p style="font-size: 0.65rem; color: #666;">+${node.addrs.length - 1} more addr</p>` : ''}
                ${Object.keys(node.data || {}).length > 0 ? `<p><code style="font-size: 0.65rem;">${JSON.stringify(node.data).substring(0, 40)}...</code></p>` : ''}
                <div class="inline-actions">
                    <button class="btn btn-danger" onclick="event.stopPropagation(); deleteNode('${node.id}')">Delete</button>
                    ${!isHub ? `<button class="btn" onclick="event.stopPropagation(); quickMakeHub('${node.id}')">→ Hub</button>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

function selectNodeForAction(nodeId) {
    // Pre-select node in link dropdown
    const linkNodeSelect = document.getElementById('linkNodeSelect');
    if (linkNodeSelect) {
        linkNodeSelect.value = nodeId;
        showMessage('Node selected for linking', false);
    }
}

function quickMakeHub(nodeId) {
    document.getElementById('hubNodeSelect').value = nodeId;
    createHub();
}

function toggleQuickAddMode() {
    const quickSection = document.getElementById('quickAddSection');
    const standardSection = document.getElementById('standardAddSection');

    if (quickSection.style.display === 'none') {
        quickSection.style.display = 'block';
        standardSection.style.display = 'none';
    } else {
        quickSection.style.display = 'none';
        standardSection.style.display = 'block';
    }
}

async function quickAddNodes() {
    if (!currentMeshId) {
        showMessage('Please select a mesh first', true);
        return;
    }

    const input = document.getElementById('quickAddInput').value.trim();
    if (!input) {
        showMessage('Please enter node data', true);
        return;
    }

    const lines = input.split('\n').filter(line => line.trim());
    let successCount = 0;
    let errorCount = 0;

    for (const line of lines) {
        const parts = line.split(',').map(p => p.trim());
        if (parts.length < 2) {
            showMessage(`Skipping invalid line: ${line}`, true);
            errorCount++;
            continue;
        }

        const name = parts[0];
        const addrs = parts.slice(1);

        try {
            const response = await fetch(`${API_BASE}/mesh/${currentMeshId}/node`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name, addrs, data: {}})
            });

            if (response.ok) {
                successCount++;
            } else {
                errorCount++;
            }
        } catch (error) {
            errorCount++;
        }
    }

    showMessage(`Added ${successCount} nodes successfully${errorCount > 0 ? `, ${errorCount} failed` : ''}`, errorCount > 0);
    document.getElementById('quickAddInput').value = '';
    toggleQuickAddMode();
    selectMesh(currentMeshId); // Refresh
}

async function deleteNode(nodeId) {
    if (!currentMeshId) return;
    if (!confirm('Are you sure you want to delete this node?')) return;

    try {
        const response = await fetch(`${API_BASE}/mesh/${currentMeshId}/node/${nodeId}`, {method: 'DELETE'});
        if (response.ok) {
            showMessage('Node deleted successfully');
            selectMesh(currentMeshId); // Refresh
        } else {
            showMessage('Failed to delete node', true);
        }
    } catch (error) {
        showMessage('Error deleting node: ' + error.message, true);
    }
}

function updateNodeSelects() {
    const hubNodeSelect = document.getElementById('hubNodeSelect');
    const linkNodeSelect = document.getElementById('linkNodeSelect');

    const options = '<option value="">Select a node</option>' +
        nodes.map(node => `<option value="${node.id}">${node.name}</option>`).join('');

    hubNodeSelect.innerHTML = options;
    linkNodeSelect.innerHTML = options;
}

async function createHub() {
    if (!currentMeshId) {
        showMessage('Please select a mesh first', true);
        return;
    }

    const nodeId = document.getElementById('hubNodeSelect').value;
    if (!nodeId) {
        showMessage('Please select a node to make a hub', true);
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/mesh/${currentMeshId}/hub`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({node_id: nodeId})
        });

        if (response.ok) {
            showMessage('Hub created successfully');
            document.getElementById('hubNodeSelect').value = '';
            selectMesh(currentMeshId); // Refresh
        } else {
            const error = await response.json();
            showMessage('Failed to create hub: ' + (error.detail || 'Unknown error'), true);
        }
    } catch (error) {
        showMessage('Error creating hub: ' + error.message, true);
    }
}

async function loadHubs() {
    if (!currentMeshId) return;

    try {
        const response = await fetch(`${API_BASE}/mesh/${currentMeshId}/hub`);
        if (response.ok) {
            hubs = await response.json();
            displayHubs();
            updateHubSelect();
        } else {
            showMessage('Failed to load hubs', true);
        }
    } catch (error) {
        showMessage('Error loading hubs: ' + error.message, true);
    }
}

function displayHubs() {
    const hubListDiv = document.getElementById('hubList');
    if (hubs.length === 0) {
        hubListDiv.innerHTML = '<p>No hubs found</p>';
        return;
    }

    hubListDiv.innerHTML = hubs.map(hub => `
        <div class="item compact-item clickable-node" onclick="selectHubForAction('${hub.id}')">
            <h4>🔶 ${hub.name} <small style="color: #888;">(${hub.spokes.length} spokes${hub.connected_hubs && hub.connected_hubs.length > 0 ? `, ${hub.connected_hubs.length} hubs` : ''})</small></h4>
            ${hub.spokes.length > 0 ? '<p style="margin: 2px 0;">' + hub.spokes.map(spoke =>
                `<span class="node-badge" onclick="event.stopPropagation(); unlinkSpokeQuick('${spoke.id}', '${hub.id}')" title="Click to unlink">${spoke.name} ✖</span>`
            ).join(' ') + '</p>' : ''}
            ${hub.connected_hubs && hub.connected_hubs.length > 0 ?
                '<p style="margin: 2px 0;"><small style="color: #ef4444;">⟷ ' + hub.connected_hubs.map(h => h.name).join(', ') + '</small></p>' : ''}
            <div class="inline-actions">
                <button class="btn btn-danger" onclick="event.stopPropagation(); deleteHub('${hub.id}')">Delete Hub</button>
            </div>
        </div>
    `).join('');
}

function selectHubForAction(hubId) {
    // Pre-select hub in link dropdown
    const linkHubSelect = document.getElementById('linkHubSelect');
    const sourceHubSelect = document.getElementById('sourceHubSelect');

    if (linkHubSelect) {
        linkHubSelect.value = hubId;
    }
    if (sourceHubSelect) {
        sourceHubSelect.value = hubId;
    }
    showMessage('Hub selected for linking', false);
}

async function unlinkSpokeQuick(nodeId, hubId) {
    if (!confirm('Unlink this spoke from the hub?')) return;

    try {
        const response = await fetch(`${API_BASE}/mesh/${currentMeshId}/unlink_from_hub`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({node_id: nodeId, hub_id: hubId})
        });

        if (response.ok) {
            showMessage('Node unlinked successfully');
            selectMesh(currentMeshId);
        } else {
            const error = await response.json();
            showMessage('Failed to unlink: ' + (error.detail || 'Unknown error'), true);
        }
    } catch (error) {
        showMessage('Error unlinking node: ' + error.message, true);
    }
}

function updateHubSelect() {
    const linkHubSelect = document.getElementById('linkHubSelect');
    const sourceHubSelect = document.getElementById('sourceHubSelect');
    const targetHubSelect = document.getElementById('targetHubSelect');

    const options = '<option value="">Select a hub</option>' +
        hubs.map(hub => `<option value="${hub.id}">${hub.name}</option>`).join('');

    linkHubSelect.innerHTML = options;
    if (sourceHubSelect) sourceHubSelect.innerHTML = options;
    if (targetHubSelect) targetHubSelect.innerHTML = options;
}

async function deleteHub(hubId) {
    if (!currentMeshId) return;
    if (!confirm('Are you sure you want to delete this hub?')) return;

    try {
        const response = await fetch(`${API_BASE}/mesh/${currentMeshId}/hub/${hubId}`, {method: 'DELETE'});
        if (response.ok) {
            showMessage('Hub deleted successfully');
            selectMesh(currentMeshId); // Refresh
        } else {
            showMessage('Failed to delete hub', true);
        }
    } catch (error) {
        showMessage('Error deleting hub: ' + error.message, true);
    }
}

async function linkToHub() {
    if (!currentMeshId) {
        showMessage('Please select a mesh first', true);
        return;
    }

    const nodeId = document.getElementById('linkNodeSelect').value;
    const hubId = document.getElementById('linkHubSelect').value;

    if (!nodeId || !hubId) {
        showMessage('Please select both a node and a hub', true);
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/mesh/${currentMeshId}/link_to_hub`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({node_id: nodeId, hub_id: hubId})
        });

        if (response.ok) {
            showMessage('Node linked to hub successfully');
            selectMesh(currentMeshId); // Refresh
        } else {
            const error = await response.json();
            showMessage('Failed to link: ' + (error.detail || 'Unknown error'), true);
        }
    } catch (error) {
        showMessage('Error linking node: ' + error.message, true);
    }
}

async function unlinkFromHub() {
    if (!currentMeshId) {
        showMessage('Please select a mesh first', true);
        return;
    }

    const nodeId = document.getElementById('linkNodeSelect').value;
    const hubId = document.getElementById('linkHubSelect').value;

    if (!nodeId || !hubId) {
        showMessage('Please select both a node and a hub', true);
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/mesh/${currentMeshId}/unlink_from_hub`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({node_id: nodeId, hub_id: hubId})
        });

        if (response.ok) {
            showMessage('Node unlinked from hub successfully');
            selectMesh(currentMeshId); // Refresh
        } else {
            const error = await response.json();
            showMessage('Failed to unlink: ' + (error.detail || 'Unknown error'), true);
        }
    } catch (error) {
        showMessage('Error unlinking node: ' + error.message, true);
    }
}

// Hub-to-Hub Connection Functions
async function connectHubs() {
    if (!currentMeshId) {
        showMessage('Please select a mesh first', true);
        return;
    }

    const sourceHubId = document.getElementById('sourceHubSelect').value;
    const targetHubId = document.getElementById('targetHubSelect').value;

    if (!sourceHubId || !targetHubId) {
        showMessage('Please select both source and target hubs', true);
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/mesh/${currentMeshId}/connect_hubs`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({source_hub_id: sourceHubId, target_hub_id: targetHubId})
        });

        if (response.ok) {
            showMessage('Hubs connected successfully');
            document.getElementById('sourceHubSelect').value = '';
            document.getElementById('targetHubSelect').value = '';
            selectMesh(currentMeshId); // Refresh
            updateTopologyDisplay();
            updateNetworkGraph();
        } else {
            const error = await response.json();
            showMessage('Failed to connect hubs: ' + (error.detail || 'Unknown error'), true);
        }
    } catch (error) {
        showMessage('Error connecting hubs: ' + error.message, true);
    }
}

async function disconnectHubs() {
    if (!currentMeshId) {
        showMessage('Please select a mesh first', true);
        return;
    }

    const sourceHubId = document.getElementById('sourceHubSelect').value;
    const targetHubId = document.getElementById('targetHubSelect').value;

    if (!sourceHubId || !targetHubId) {
        showMessage('Please select both source and target hubs', true);
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/mesh/${currentMeshId}/disconnect_hubs`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({source_hub_id: sourceHubId, target_hub_id: targetHubId})
        });

        if (response.ok) {
            showMessage('Hubs disconnected successfully');
            document.getElementById('sourceHubSelect').value = '';
            document.getElementById('targetHubSelect').value = '';
            selectMesh(currentMeshId); // Refresh
            updateTopologyDisplay();
            updateNetworkGraph();
        } else {
            const error = await response.json();
            showMessage('Failed to disconnect hubs: ' + (error.detail || 'Unknown error'), true);
        }
    } catch (error) {
        showMessage('Error disconnecting hubs: ' + error.message, true);
    }
}

// Graph Visualization Functions
let network = null;

function updateNetworkGraph() {
    if (!currentMeshId || !nodes || !hubs) return;

    const graphNodes = [];
    const graphEdges = [];

    // Add regular nodes
    nodes.forEach(node => {
        // Check if this node is also a hub
        const isHub = hubs.some(hub => hub.node_id === node.id);
        graphNodes.push({
            id: node.id,
            label: node.name,
            color: {
                background: isHub ? '#ff9500' : '#00d4ff',
                border: isHub ? '#ffa500' : '#00a8cc',
                highlight: {
                    background: isHub ? '#ffb84d' : '#33ddff',
                    border: isHub ? '#ffb84d' : '#00d4ff'
                }
            },
            shape: isHub ? 'hexagon' : 'dot',
            size: isHub ? 20 : 15,
            font: {
                color: '#ffffff',
                size: 11,
                face: 'arial',
                background: 'rgba(0, 0, 0, 0.7)',
                strokeWidth: 2,
                strokeColor: '#000000'
            }
        });
    });

    // Add hub-to-hub connections
    hubs.forEach(hub => {
        if (hub.connected_hubs && hub.connected_hubs.length > 0) {
            hub.connected_hubs.forEach(connectedHub => {
                // Only add edge once (avoid duplicates)
                if (hub.id < connectedHub.id) {
                    const hubNode = nodes.find(n => n.id === hub.node_id);
                    const connectedHubNode = nodes.find(n => n.id === connectedHub.node_id);

                    graphEdges.push({
                        from: hub.node_id,
                        to: connectedHub.node_id,
                        color: { color: '#ef4444', highlight: '#ff0000' },
                        width: 2,
                        arrows: { to: { enabled: false } },
                        dashes: false,
                        length: 400,
                        label: `${hubNode?.addrs[0] || hubNode?.name || ''} <-> ${connectedHubNode?.addrs[0] || connectedHubNode?.name || ''}`,
                        font: {
                            size: 9,
                            color: '#e5e7eb',
                            align: 'middle',
                            background: 'rgba(0, 0, 0, 0.8)',
                            strokeWidth: 0
                        }
                    });
                }
            });
        }

        // Add node-to-hub connections (spokes)
        if (hub.spokes && hub.spokes.length > 0) {
            hub.spokes.forEach(spoke => {
                const spokeNode = nodes.find(n => n.id === spoke.id);
                const hubNode = nodes.find(n => n.id === hub.node_id);

                graphEdges.push({
                    from: spoke.id,
                    to: hub.node_id,
                    color: { color: '#10b981', highlight: '#059669' },
                    width: 1.5,
                    arrows: { to: { enabled: true, scaleFactor: 0.4 } },
                    dashes: true,
                    length: 200,
                    label: `${spokeNode?.addrs[0] || spokeNode?.name || ''} → ${hubNode?.addrs[0] || hubNode?.name || ''}`,
                    font: {
                        size: 9,
                        color: '#e5e7eb',
                        align: 'middle',
                        background: 'rgba(0, 0, 0, 0.8)',
                        strokeWidth: 0
                    }
                });
            });
        }
    });

    // Create network
    const container = document.getElementById('networkGraph');
    const data = { nodes: new vis.DataSet(graphNodes), edges: new vis.DataSet(graphEdges) };
    const options = {
        physics: {
            enabled: true,
            solver: 'forceAtlas2Based',
            forceAtlas2Based: {
                gravitationalConstant: -20,
                centralGravity: 0.005,
                springLength: 180,
                springConstant: 0.2
            },
            stabilization: { iterations: 100 }
        },
        interaction: {
            dragNodes: true,
            dragView: true,
            zoomView: true,
            navigationButtons: false
        },
        nodes: {
            borderWidth: 2,
            shadow: {
                enabled: true,
                color: 'rgba(0, 212, 255, 0.5)',
                size: 6,
                x: 0,
                y: 0
            },
            font: { size: 11, face: 'arial' }
        },
        edges: {
            shadow: {
                enabled: true,
                color: 'rgba(0, 0, 0, 0.5)',
                size: 5,
                x: 2,
                y: 2
            },
            smooth: { type: 'continuous' }
        },
        configure: {
            enabled: false
        }
    };

    if (network) {
        network.destroy();
    }
    network = new vis.Network(container, data, options);

    // Track drag state
    let draggedNodeId = null;
    let hoveredHubId = null;

    // Drag start event
    network.on('dragStart', function(params) {
        if (params.nodes.length > 0) {
            draggedNodeId = params.nodes[0];
            // Disable physics for the dragged node so it can move freely
            data.nodes.update({id: draggedNodeId, physics: false});
            // Freeze the entire graph while dragging
            network.setOptions({ physics: { enabled: false } });
        }
    });

    // Dragging event - highlight hub when hovering
    network.on('dragging', function(params) {
        if (draggedNodeId) {
            // Use canvas coordinates for more reliable node detection
            const canvasPos = params.pointer.canvas;
            let targetNodeId = null;

            // Find the closest node to the pointer within a reasonable distance
            let minDistance = 50; // pixels - detection radius
            const positions = network.getPositions();

            Object.keys(positions).forEach(nodeId => {
                if (nodeId !== draggedNodeId) {
                    const pos = positions[nodeId];
                    const dx = pos.x - canvasPos.x;
                    const dy = pos.y - canvasPos.y;
                    const distance = Math.sqrt(dx * dx + dy * dy);

                    if (distance < minDistance) {
                        minDistance = distance;
                        targetNodeId = nodeId;
                    }
                }
            });

            if (targetNodeId && targetNodeId !== draggedNodeId) {
                const targetHub = hubs.find(h => h.node_id === targetNodeId);
                const draggedHub = hubs.find(h => h.node_id === draggedNodeId);

                // If dragging a node over a hub (or hub over hub), highlight it
                if (targetHub && (!draggedHub || draggedNodeId !== targetNodeId)) {
                    if (hoveredHubId !== targetNodeId) {
                        // Remove previous highlight
                        if (hoveredHubId) {
                            const wasHub = hubs.find(h => h.node_id === hoveredHubId);
                            data.nodes.update({
                                id: hoveredHubId,
                                color: '#ff9500',
                                borderWidth: 2
                            });
                        }
                        // Add new highlight
                        hoveredHubId = targetNodeId;
                        data.nodes.update({
                            id: targetNodeId,
                            color: '#00ff00',
                            borderWidth: 4
                        });
                    }
                } else {
                    // Clear highlight if not over a valid hub
                    if (hoveredHubId) {
                        data.nodes.update({
                            id: hoveredHubId,
                            color: '#ff9500',
                            borderWidth: 2
                        });
                        hoveredHubId = null;
                    }
                }
            } else {
                // Clear highlight if not over any node
                if (hoveredHubId) {
                    data.nodes.update({
                        id: hoveredHubId,
                        color: '#ff9500',
                        borderWidth: 2
                    });
                    hoveredHubId = null;
                }
            }
        }
    });

    // Drag end event - handle linking when dropping on a hub
    network.on('dragEnd', function(params) {
        if (draggedNodeId) {
            // Re-enable physics for the graph
            network.setOptions({ physics: { enabled: true } });

            // Re-enable physics for the dragged node
            data.nodes.update({id: draggedNodeId, physics: true});

            // Clear any hover highlight
            if (hoveredHubId) {
                data.nodes.update({
                    id: hoveredHubId,
                    color: '#ff9500',
                    borderWidth: 2
                });
            }

            if (params.pointer.canvas) {
                // Use the hovered hub ID if we have it (most reliable)
                let targetNodeId = hoveredHubId;

                // If no hover detected, do a final distance check
                if (!targetNodeId) {
                    const canvasPos = params.pointer.canvas;
                    let minDistance = 50; // pixels - detection radius
                    const positions = network.getPositions();

                    Object.keys(positions).forEach(nodeId => {
                        if (nodeId !== draggedNodeId) {
                            const pos = positions[nodeId];
                            const dx = pos.x - canvasPos.x;
                            const dy = pos.y - canvasPos.y;
                            const distance = Math.sqrt(dx * dx + dy * dy);

                            if (distance < minDistance) {
                                minDistance = distance;
                                targetNodeId = nodeId;
                            }
                        }
                    });
                }

                if (targetNodeId && targetNodeId !== draggedNodeId) {
                    const draggedNode = nodes.find(n => n.id === draggedNodeId);
                    const targetHub = hubs.find(h => h.node_id === targetNodeId);
                    const draggedHub = hubs.find(h => h.node_id === draggedNodeId);

                    // Case 1: Dragging a regular node onto a hub - link as spoke (no confirmation)
                    if (draggedNode && targetHub && !draggedHub) {
                        linkNodeToHubDirect(draggedNodeId, targetHub.id);
                    }
                    // Case 2: Dragging a hub onto another hub - connect hubs (no confirmation)
                    else if (draggedHub && targetHub && draggedNodeId !== targetNodeId) {
                        connectHubsDirect(draggedHub.id, targetHub.id);
                    }
                }
            }

            hoveredHubId = null;
            draggedNodeId = null;
        }
    });

    // Right-click context menu
    network.on('oncontext', function(params) {
        params.event.preventDefault();

        const nodeId = network.getNodeAt(params.pointer.DOM);
        if (nodeId) {
            const node = nodes.find(n => n.id === nodeId);
            const hub = hubs.find(h => h.node_id === nodeId);
            // Get the canvas element position to convert canvas coordinates to page coordinates
            const canvas = container.querySelector('canvas');
            const rect = canvas.getBoundingClientRect();
            const pageX = rect.left + params.pointer.DOM.x;
            const pageY = rect.top + params.pointer.DOM.y;
            showContextMenu(pageX, pageY, node, hub);
        } else {
            hideContextMenu();
        }
    });

    // Click event to hide context menu and show details
    network.on('click', function(params) {
        hideContextMenu();

        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            showDetailsPanel(nodeId);
        }
    });
}

// Tab switching
function switchTab(tabName) {
    const tabs = document.querySelectorAll('.tab');
    const tabContents = document.querySelectorAll('.tab-content');

    tabs.forEach(tab => tab.classList.remove('active'));
    tabContents.forEach(content => content.style.display = 'none');

    event.target.classList.add('active');
    document.getElementById(tabName + 'Tab').style.display = 'block';

    if (tabName === 'topology') {
        updateTopologyDisplay();
    }
}

// Update topology display
function updateTopologyDisplay() {
    const topologyDiv = document.getElementById('hubTopologyList');
    if (!currentMeshId || hubs.length === 0) {
        topologyDiv.innerHTML = '<p>No hubs found or no mesh selected</p>';
        return;
    }

    let html = '';
    hubs.forEach(hub => {
        html += `
            <div class="item compact-item">
                <h4>🔶 ${hub.name}</h4>
                <p><strong>Spokes:</strong> ${hub.spokes.length > 0 ? hub.spokes.map(s => s.name).join(', ') : 'None'}</p>
                ${hub.connected_hubs && hub.connected_hubs.length > 0 ?
                    `<p><strong>⟷ Hubs:</strong> ${hub.connected_hubs.map(h => h.name).join(', ')}</p>` : ''}
            </div>
        `;
    });

    topologyDiv.innerHTML = html;
}

// Enhanced selectMesh function to update graph
const originalSelectMesh = selectMesh;
selectMesh = async function(meshId) {
    await originalSelectMesh(meshId);
    updateNetworkGraph();
    updateTopologyDisplay();
};

// Polling functions for auto-refresh
function startPolling() {
    if (pollingInterval) return; // Already polling

    pollingInterval = setInterval(async () => {
        if (!pollingEnabled) return;

        try {
            if (currentMeshId) {
                // Silently refresh current mesh data
                const response = await fetch(`${API_BASE}/mesh/${currentMeshId}`);
                if (response.ok) {
                    const mesh = await response.json();
                    const oldNodesJSON = JSON.stringify(nodes);
                    const oldHubsJSON = JSON.stringify(hubs);

                    nodes = mesh.nodes;
                    hubs = mesh.hubs;

                    const newNodesJSON = JSON.stringify(nodes);
                    const newHubsJSON = JSON.stringify(hubs);

                    // Update displays if data changed
                    if (oldNodesJSON !== newNodesJSON || oldHubsJSON !== newHubsJSON) {
                        displayNodes();
                        displayHubs();
                        updateNodeSelects();
                        updateHubSelect();
                        updateNetworkGraph();
                        updateTopologyDisplay();

                        // Show subtle notification
                        showAutoRefreshIndicator();
                    }
                }
            } else {
                // No mesh selected, poll for mesh list changes
                const response = await fetch(`${API_BASE}/mesh`);
                if (response.ok) {
                    const newMeshes = await response.json();
                    const oldMeshesJSON = JSON.stringify(meshes);
                    const newMeshesJSON = JSON.stringify(newMeshes);

                    if (oldMeshesJSON !== newMeshesJSON) {
                        meshes = newMeshes;
                        displayMeshes();
                        updateMeshSelect();
                        showAutoRefreshIndicator();
                    }
                }
            }
        } catch (error) {
            console.error('Polling error:', error);
        }
    }, POLL_INTERVAL_MS);
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

function togglePolling() {
    pollingEnabled = !pollingEnabled;
    const btn = document.getElementById('pollingToggle');
    if (btn) {
        btn.textContent = pollingEnabled ? '⏸ Pause' : '▶ Resume';
        btn.className = pollingEnabled ? 'btn btn-success' : 'btn';
    }

    if (pollingEnabled) {
        startPolling();
    } else {
        stopPolling();
    }
}

function showAutoRefreshIndicator() {
    const indicator = document.getElementById('refreshIndicator');
    if (indicator) {
        indicator.style.opacity = '1';
        setTimeout(() => {
            indicator.style.opacity = '0';
        }, 1000);
    }
}

// Enhanced selectMesh to start/stop polling
const originalSelectMeshFunc = selectMesh;
selectMesh = async function(meshId) {
    await originalSelectMeshFunc(meshId);
    startPolling(); // Start polling when a mesh is selected
};

// Context menu functions
function showContextMenu(x, y, node, hub) {
    hideContextMenu(); // Remove any existing menu

    const menu = document.createElement('div');
    menu.id = 'contextMenu';
    menu.className = 'context-menu';
    menu.style.left = x + 'px';
    menu.style.top = y + 'px';

    let menuHTML = '';

    if (hub) {
        // Hub context menu
        menuHTML = `
            <div class="context-menu-item" onclick="viewNodeDetails('${node.id}')">
                ℹ️ View Details
            </div>
            <div class="context-menu-item" onclick="removeHubFromMenu('${hub.id}')">
                🔽 Demote to Node
            </div>
            <div class="context-menu-item danger" onclick="deleteNodeFromMenu('${node.id}')">
                🗑️ Delete Hub & Node
            </div>
        `;
    } else {
        // Regular node context menu
        menuHTML = `
            <div class="context-menu-item" onclick="viewNodeDetails('${node.id}')">
                ℹ️ View Details
            </div>
            <div class="context-menu-item" onclick="quickMakeHub('${node.id}')">
                ⬆️ Promote to Hub
            </div>
            <div class="context-menu-item danger" onclick="deleteNodeFromMenu('${node.id}')">
                🗑️ Delete Node
            </div>
        `;
    }

    menu.innerHTML = menuHTML;
    document.body.appendChild(menu);

    // Close menu when clicking outside
    setTimeout(() => {
        document.addEventListener('click', hideContextMenu, { once: true });
    }, 0);
}

function hideContextMenu() {
    const menu = document.getElementById('contextMenu');
    if (menu) {
        menu.remove();
    }
}

function showLinkToHubSubmenu(nodeId, nodeName) {
    const menu = document.getElementById('contextMenu');
    if (!menu) return;

    const availableHubs = hubs.filter(h => {
        // Don't show hubs this node is already connected to
        return !h.spokes.some(s => s.id === nodeId);
    });

    if (availableHubs.length === 0) {
        menu.innerHTML = `
            <div class="context-menu-item" onclick="hideContextMenu()">
                ← Back
            </div>
            <div class="context-menu-divider"></div>
            <div class="context-menu-item" style="color: #999; cursor: default;">
                No hubs available
            </div>
        `;
        return;
    }

    let submenuHTML = `
        <div class="context-menu-item" onclick="showContextMenu(${menu.style.left.replace('px', '')}, ${menu.style.top.replace('px', '')}, nodes.find(n => n.id === '${nodeId}'), null)">
            ← Back
        </div>
        <div class="context-menu-divider"></div>
    `;

    availableHubs.forEach(hub => {
        submenuHTML += `
            <div class="context-menu-item" onclick="linkNodeToHubDirect('${nodeId}', '${hub.id}'); hideContextMenu();">
                🔗 ${hub.name}
            </div>
        `;
    });

    menu.innerHTML = submenuHTML;
}

function showConnectHubSubmenu(sourceHubId, sourceHubName) {
    const menu = document.getElementById('contextMenu');
    if (!menu) return;

    const sourceHub = hubs.find(h => h.id === sourceHubId);
    const connectedHubIds = new Set(sourceHub.connected_hubs?.map(h => h.id) || []);

    const availableHubs = hubs.filter(h => {
        // Don't show the source hub itself or already connected hubs
        return h.id !== sourceHubId && !connectedHubIds.has(h.id);
    });

    if (availableHubs.length === 0) {
        menu.innerHTML = `
            <div class="context-menu-item" onclick="hideContextMenu()">
                ← Back
            </div>
            <div class="context-menu-divider"></div>
            <div class="context-menu-item" style="color: #999; cursor: default;">
                No hubs available
            </div>
        `;
        return;
    }

    const node = nodes.find(n => n.id === sourceHub.node_id);
    let submenuHTML = `
        <div class="context-menu-item" onclick="showContextMenu(${menu.style.left.replace('px', '')}, ${menu.style.top.replace('px', '')}, nodes.find(n => n.id === '${node.id}'), hubs.find(h => h.id === '${sourceHubId}'))">
            ← Back
        </div>
        <div class="context-menu-divider"></div>
    `;

    availableHubs.forEach(hub => {
        submenuHTML += `
            <div class="context-menu-item" onclick="connectHubsDirect('${sourceHubId}', '${hub.id}'); hideContextMenu();">
                🔗 ${hub.name}
            </div>
        `;
    });

    menu.innerHTML = submenuHTML;
}

function deleteNodeFromMenu(nodeId) {
    hideContextMenu();
    deleteNode(nodeId);
}

function removeHubFromMenu(hubId) {
    hideContextMenu();
    if (confirm('Remove hub status? This will disconnect all spokes.')) {
        deleteHub(hubId);
    }
}

function viewNodeDetails(nodeId) {
    hideContextMenu();
    showDetailsPanel(nodeId);
}

function showDetailsPanel(nodeId) {
    const node = nodes.find(n => n.id === nodeId);
    const hub = hubs.find(h => h.node_id === nodeId);

    if (!node) return;

    const detailsPanel = document.getElementById('detailsPanel');
    const detailsContent = document.getElementById('detailsContent');

    let html = `
        <div class="details-section">
            <h4>${hub ? '🟠 Hub' : '🔵 Node'}</h4>
            <div class="details-field">
                <label>Name</label>
                <div class="value">${node.name}</div>
            </div>
            <div class="details-field">
                <label>ID</label>
                <div class="value">${node.id}</div>
            </div>
            <div class="details-field">
                <label>Addresses</label>
                <div class="value">${node.addrs.join(', ')}</div>
            </div>
        </div>
    `;

    if (hub) {
        html += `
            <div class="details-section">
                <h4>Hub Information</h4>
                <div class="details-field">
                    <label>Hub ID</label>
                    <div class="value">${hub.id}</div>
                </div>
                <div class="details-field">
                    <label>Connected Spokes</label>
                    <div class="value">${hub.spokes.length} node(s)${hub.spokes.length > 0 ? ': ' + hub.spokes.map(s => s.name).join(', ') : ''}</div>
                </div>
                ${hub.connected_hubs && hub.connected_hubs.length > 0 ? `
                <div class="details-field">
                    <label>Connected Hubs</label>
                    <div class="value">${hub.connected_hubs.map(h => h.name).join(', ')}</div>
                </div>
                ` : ''}
            </div>
        `;
    }

    html += `
        <div class="details-section">
            <h4>Node Data</h4>
            <div class="details-field">
                <label>JSON Data Payload</label>
                <textarea id="nodeDataEdit">${JSON.stringify(node.data || {}, null, 2)}</textarea>
                <small style="color: #666; font-size: 11px;">Edit the JSON data and click Update to save changes</small>
            </div>
            <div class="details-actions">
                <button class="btn btn-success" onclick="updateNodeData('${nodeId}')">Update Data</button>
                ${!hub ? `<button class="btn" onclick="quickMakeHub('${nodeId}')">Promote to Hub</button>` : ''}
            </div>
        </div>

        <div class="details-section">
            <h4>Actions</h4>
            <div class="details-actions" style="padding-top: 0; border-top: none;">
                ${hub ? `<button class="btn" onclick="removeHubFromMenu('${hub.id}')">Demote to Node</button>` : ''}
                <button class="btn btn-danger" onclick="deleteNodeFromMenu('${nodeId}')">Delete ${hub ? 'Hub & ' : ''}Node</button>
            </div>
        </div>
    `;

    detailsContent.innerHTML = html;
    detailsPanel.classList.remove('collapsed');
}

function closeDetailsPanel() {
    const detailsPanel = document.getElementById('detailsPanel');
    detailsPanel.classList.add('collapsed');
}

async function updateNodeData(nodeId) {
    if (!currentMeshId) {
        showMessage('No mesh selected', true);
        return;
    }

    const dataTextarea = document.getElementById('nodeDataEdit');
    let newData;

    try {
        newData = JSON.parse(dataTextarea.value);
    } catch (e) {
        showMessage('Invalid JSON: ' + e.message, true);
        return;
    }

    try {
        // Use PATCH to update only the data field without affecting connections
        const response = await fetch(`${API_BASE}/mesh/${currentMeshId}/node/${nodeId}`, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ data: newData })
        });

        if (response.ok) {
            showMessage('Node data updated successfully');
            await selectMesh(currentMeshId);
            showDetailsPanel(nodeId);
        } else {
            const error = await response.json();
            showMessage('Failed to update node data: ' + (error.detail || 'Unknown error'), true);
        }
    } catch (error) {
        showMessage('Error updating node data: ' + error.message, true);
    }
}

// Direct linking functions for drag-and-drop
async function linkNodeToHubDirect(nodeId, hubId) {
    if (!currentMeshId) {
        showMessage('No mesh selected', true);
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/mesh/${currentMeshId}/link_to_hub`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({node_id: nodeId, hub_id: hubId})
        });

        if (response.ok) {
            showMessage('Node linked to hub successfully');
            // Just update the data without rebuilding the graph
            await updateMeshDataSilently();
        } else {
            const error = await response.json();
            showMessage('Failed to link: ' + (error.detail || 'Unknown error'), true);
        }
    } catch (error) {
        showMessage('Error linking node: ' + error.message, true);
    }
}

async function connectHubsDirect(sourceHubId, targetHubId) {
    if (!currentMeshId) {
        showMessage('No mesh selected', true);
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/mesh/${currentMeshId}/connect_hubs`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({source_hub_id: sourceHubId, target_hub_id: targetHubId})
        });

        if (response.ok) {
            showMessage('Hubs connected successfully');
            // Just update the data without rebuilding the graph
            await updateMeshDataSilently();
        } else {
            const error = await response.json();
            showMessage('Failed to connect hubs: ' + (error.detail || 'Unknown error'), true);
        }
    } catch (error) {
        showMessage('Error connecting hubs: ' + error.message, true);
    }
}

// Update mesh data without rebuilding the graph (preserves positions)
async function updateMeshDataSilently() {
    if (!currentMeshId) return;

    try {
        const response = await fetch(`${API_BASE}/mesh/${currentMeshId}`);
        if (response.ok) {
            const mesh = await response.json();
            nodes = mesh.nodes;
            hubs = mesh.hubs;

            // Update displays and graph incrementally
            displayNodes();
            displayHubs();
            updateNodeSelects();
            updateHubSelect();
            updateNetworkGraphIncremental();
            updateTopologyDisplay();
        }
    } catch (error) {
        console.error('Error updating mesh data:', error);
    }
}

// Incremental graph update that preserves node positions
function updateNetworkGraphIncremental() {
    if (!currentMeshId || !nodes || !hubs || !network) return;

    // Get current positions
    const positions = network.getPositions();

    const graphNodes = [];
    const graphEdges = [];

    // Add nodes with preserved positions
    nodes.forEach(node => {
        const isHub = hubs.some(hub => hub.node_id === node.id);
        const nodeData = {
            id: node.id,
            label: node.name,
            color: {
                background: isHub ? '#ff9500' : '#00d4ff',
                border: isHub ? '#ffa500' : '#00a8cc',
                highlight: {
                    background: isHub ? '#ffb84d' : '#33ddff',
                    border: isHub ? '#ffb84d' : '#00d4ff'
                }
            },
            shape: isHub ? 'hexagon' : 'dot',
            size: isHub ? 20 : 15,
            font: {
                color: '#ffffff',
                size: 11,
                face: 'arial',
                background: 'rgba(0, 0, 0, 0.7)',
                strokeWidth: 2,
                strokeColor: '#000000'
            }
        };

        // Preserve position if it exists
        if (positions[node.id]) {
            nodeData.x = positions[node.id].x;
            nodeData.y = positions[node.id].y;
            nodeData.physics = false; // Don't let physics move positioned nodes
        }

        graphNodes.push(nodeData);
    });

    // Add edges with hostname/address labels
    hubs.forEach(hub => {
        if (hub.connected_hubs && hub.connected_hubs.length > 0) {
            hub.connected_hubs.forEach(connectedHub => {
                if (hub.id < connectedHub.id) {
                    const hubNode = nodes.find(n => n.id === hub.node_id);
                    const connectedHubNode = nodes.find(n => n.id === connectedHub.node_id);

                    graphEdges.push({
                        from: hub.node_id,
                        to: connectedHub.node_id,
                        color: { color: '#ef4444', highlight: '#ff0000' },
                        width: 2,
                        arrows: { to: { enabled: false } },
                        dashes: false,
                        length: 400,
                        label: `${hubNode?.addrs[0] || hubNode?.name || ''} <-> ${connectedHubNode?.addrs[0] || connectedHubNode?.name || ''}`,
                        font: {
                            size: 9,
                            color: '#e5e7eb',
                            align: 'middle',
                            background: 'rgba(0, 0, 0, 0.8)',
                            strokeWidth: 0
                        }
                    });
                }
            });
        }

        if (hub.spokes && hub.spokes.length > 0) {
            hub.spokes.forEach(spoke => {
                const spokeNode = nodes.find(n => n.id === spoke.id);
                const hubNode = nodes.find(n => n.id === hub.node_id);

                graphEdges.push({
                    from: spoke.id,
                    to: hub.node_id,
                    color: { color: '#10b981', highlight: '#059669' },
                    width: 1.5,
                    arrows: { to: { enabled: true, scaleFactor: 0.4 } },
                    dashes: true,
                    length: 200,
                    label: `${spokeNode?.addrs[0] || spokeNode?.name || ''} → ${hubNode?.addrs[0] || hubNode?.name || ''}`,
                    font: {
                        size: 9,
                        color: '#e5e7eb',
                        align: 'middle',
                        background: 'rgba(0, 0, 0, 0.8)',
                        strokeWidth: 0
                    }
                });
            });
        }
    });

    // Update the network data without destroying it
    const data = network.body.data;
    data.nodes.clear();
    data.nodes.add(graphNodes);
    data.edges.clear();
    data.edges.add(graphEdges);

    // Re-enable physics after a short delay to let new edges settle
    setTimeout(() => {
        graphNodes.forEach(node => {
            if (positions[node.id]) {
                data.nodes.update({id: node.id, physics: true});
            }
        });
    }, 100);
}

// Hide context menu on canvas click
document.addEventListener('click', function(e) {
    if (!e.target.closest('.context-menu')) {
        hideContextMenu();
    }
});

// Graph control functions
function zoomIn() {
    if (network) {
        const scale = network.getScale();
        network.moveTo({ scale: scale * 1.2 });
    }
}

function zoomOut() {
    if (network) {
        const scale = network.getScale();
        network.moveTo({ scale: scale * 0.8 });
    }
}

function fitGraph() {
    if (network) {
        network.fit({ animation: true });
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Auto-refresh mesh selection when dropdown changes
    document.getElementById('selectedMesh').addEventListener('change', function() {
        if (this.value) {
            selectMesh(this.value);
        }
    });

    // Load meshes on page load and start polling
    loadMeshes();
    startPolling();
});
