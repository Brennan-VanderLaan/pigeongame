"""
Tests for hub-to-hub connection functionality
"""

import pytest
from tests.test_base import DatabaseManager, ApiClient, create_test_mesh, create_test_node, create_test_hub


class TestHubConnections:
    """Tests for hub-to-hub connections forming complex network topologies"""

    @pytest.mark.asyncio
    async def test_connect_two_hubs(self):
        """Test basic hub-to-hub connection"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "hub-connection-test")

                # Create two hubs
                hub1_node = await create_test_node(client, mesh["id"], "hub1-node")
                hub2_node = await create_test_node(client, mesh["id"], "hub2-node")

                hub1 = await create_test_hub(client, mesh["id"], hub1_node["id"])
                hub2 = await create_test_hub(client, mesh["id"], hub2_node["id"])

                # Connect the hubs
                response = await client.post(
                    f"/mesh/{mesh['id']}/connect_hubs",
                    json={"source_hub_id": hub1["id"], "target_hub_id": hub2["id"]}
                )
                assert response.status_code == 200

                # Verify connection exists in both directions
                response = await client.get(f"/mesh/{mesh['id']}/hub")
                hubs = response.json()

                hubs_by_id = {hub["id"]: hub for hub in hubs}
                assert len(hubs_by_id[hub1["id"]]["connected_hubs"]) == 1
                assert len(hubs_by_id[hub2["id"]]["connected_hubs"]) == 1
                assert hubs_by_id[hub1["id"]]["connected_hubs"][0]["id"] == hub2["id"]
                assert hubs_by_id[hub2["id"]]["connected_hubs"][0]["id"] == hub1["id"]
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_disconnect_hubs(self):
        """Test disconnecting hubs"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "hub-disconnection-test")

                # Create and connect two hubs
                hub1_node = await create_test_node(client, mesh["id"], "hub1-node")
                hub2_node = await create_test_node(client, mesh["id"], "hub2-node")

                hub1 = await create_test_hub(client, mesh["id"], hub1_node["id"])
                hub2 = await create_test_hub(client, mesh["id"], hub2_node["id"])

                # Connect hubs
                await client.post(
                    f"/mesh/{mesh['id']}/connect_hubs",
                    json={"source_hub_id": hub1["id"], "target_hub_id": hub2["id"]}
                )

                # Disconnect hubs
                response = await client.post(
                    f"/mesh/{mesh['id']}/disconnect_hubs",
                    json={"source_hub_id": hub1["id"], "target_hub_id": hub2["id"]}
                )
                assert response.status_code == 200

                # Verify connection no longer exists
                response = await client.get(f"/mesh/{mesh['id']}/hub")
                hubs = response.json()

                hubs_by_id = {hub["id"]: hub for hub in hubs}
                assert len(hubs_by_id[hub1["id"]]["connected_hubs"]) == 0
                assert len(hubs_by_id[hub2["id"]]["connected_hubs"]) == 0
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_complex_hub_topology(self):
        """Test creating complex hub-to-hub topology"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "complex-topology-test")

                # Create multiple hubs forming a triangle topology
                hub_nodes = []
                hubs = []
                for i in range(3):
                    node = await create_test_node(client, mesh["id"], f"hub{i+1}-node")
                    hub = await create_test_hub(client, mesh["id"], node["id"])
                    hub_nodes.append(node)
                    hubs.append(hub)

                # Connect hubs in a triangle: 1-2, 2-3, 3-1
                connections = [
                    (hubs[0]["id"], hubs[1]["id"]),  # hub1 -> hub2
                    (hubs[1]["id"], hubs[2]["id"]),  # hub2 -> hub3
                    (hubs[2]["id"], hubs[0]["id"])   # hub3 -> hub1
                ]

                for source_id, target_id in connections:
                    response = await client.post(
                        f"/mesh/{mesh['id']}/connect_hubs",
                        json={"source_hub_id": source_id, "target_hub_id": target_id}
                    )
                    assert response.status_code == 200

                # Verify all hubs have 2 connections each (triangle topology)
                response = await client.get(f"/mesh/{mesh['id']}/hub")
                hub_data = response.json()

                for hub in hub_data:
                    assert len(hub["connected_hubs"]) == 2

                # Verify specific connections
                hubs_by_id = {hub["id"]: hub for hub in hub_data}

                # Hub1 should connect to Hub2 and Hub3
                hub1_connections = {conn["id"] for conn in hubs_by_id[hubs[0]["id"]]["connected_hubs"]}
                assert hub1_connections == {hubs[1]["id"], hubs[2]["id"]}

                # Hub2 should connect to Hub1 and Hub3
                hub2_connections = {conn["id"] for conn in hubs_by_id[hubs[1]["id"]]["connected_hubs"]}
                assert hub2_connections == {hubs[0]["id"], hubs[2]["id"]}

                # Hub3 should connect to Hub1 and Hub2
                hub3_connections = {conn["id"] for conn in hubs_by_id[hubs[2]["id"]]["connected_hubs"]}
                assert hub3_connections == {hubs[0]["id"], hubs[1]["id"]}
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_hub_with_spokes_and_connections(self):
        """Test hub that has both spoke nodes and hub connections"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "hub-mixed-connections-test")

                # Create central hub
                central_hub_node = await create_test_node(client, mesh["id"], "central-hub-node")
                central_hub = await create_test_hub(client, mesh["id"], central_hub_node["id"])

                # Create spoke nodes
                spoke_nodes = []
                for i in range(2):
                    spoke = await create_test_node(client, mesh["id"], f"spoke{i+1}")
                    spoke_nodes.append(spoke)

                    # Link spoke to central hub
                    await client.post(
                        f"/mesh/{mesh['id']}/link_to_hub",
                        json={"node_id": spoke["id"], "hub_id": central_hub["id"]}
                    )

                # Create other hubs
                other_hubs = []
                for i in range(2):
                    hub_node = await create_test_node(client, mesh["id"], f"other-hub{i+1}-node")
                    hub = await create_test_hub(client, mesh["id"], hub_node["id"])
                    other_hubs.append(hub)

                    # Connect to central hub
                    await client.post(
                        f"/mesh/{mesh['id']}/connect_hubs",
                        json={"source_hub_id": central_hub["id"], "target_hub_id": hub["id"]}
                    )

                # Verify central hub has both spokes and hub connections
                response = await client.get(f"/mesh/{mesh['id']}/hub")
                hubs_data = response.json()

                central_hub_data = next(h for h in hubs_data if h["id"] == central_hub["id"])
                assert len(central_hub_data["spokes"]) == 2
                assert len(central_hub_data["connected_hubs"]) == 2

                # Verify spokes are correct
                spoke_ids = {spoke["id"] for spoke in central_hub_data["spokes"]}
                expected_spoke_ids = {spoke["id"] for spoke in spoke_nodes}
                assert spoke_ids == expected_spoke_ids

                # Verify hub connections are correct
                connected_hub_ids = {hub["id"] for hub in central_hub_data["connected_hubs"]}
                expected_hub_ids = {hub["id"] for hub in other_hubs}
                assert connected_hub_ids == expected_hub_ids
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_error_cases(self):
        """Test error cases for hub connections"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "hub-error-test")

                # Create one hub
                hub_node = await create_test_node(client, mesh["id"], "hub-node")
                hub = await create_test_hub(client, mesh["id"], hub_node["id"])

                fake_hub_id = "12345678-1234-5678-1234-567812345678"

                # Test connecting to non-existent hub
                response = await client.post(
                    f"/mesh/{mesh['id']}/connect_hubs",
                    json={"source_hub_id": hub["id"], "target_hub_id": fake_hub_id}
                )
                assert response.status_code == 404
                assert "Target hub not found" in response.json()["detail"]

                # Test connecting from non-existent hub
                response = await client.post(
                    f"/mesh/{mesh['id']}/connect_hubs",
                    json={"source_hub_id": fake_hub_id, "target_hub_id": hub["id"]}
                )
                assert response.status_code == 404
                assert "Source hub not found" in response.json()["detail"]

                # Test self-connection
                response = await client.post(
                    f"/mesh/{mesh['id']}/connect_hubs",
                    json={"source_hub_id": hub["id"], "target_hub_id": hub["id"]}
                )
                assert response.status_code == 400
                assert "cannot connect to itself" in response.json()["detail"]

                # Test duplicate connection
                hub2_node = await create_test_node(client, mesh["id"], "hub2-node")
                hub2 = await create_test_hub(client, mesh["id"], hub2_node["id"])

                # First connection should work
                response = await client.post(
                    f"/mesh/{mesh['id']}/connect_hubs",
                    json={"source_hub_id": hub["id"], "target_hub_id": hub2["id"]}
                )
                assert response.status_code == 200

                # Second connection should fail
                response = await client.post(
                    f"/mesh/{mesh['id']}/connect_hubs",
                    json={"source_hub_id": hub["id"], "target_hub_id": hub2["id"]}
                )
                assert response.status_code == 400
                assert "already connected" in response.json()["detail"]

                # Test disconnecting non-connected hubs
                hub3_node = await create_test_node(client, mesh["id"], "hub3-node")
                hub3 = await create_test_hub(client, mesh["id"], hub3_node["id"])

                response = await client.post(
                    f"/mesh/{mesh['id']}/disconnect_hubs",
                    json={"source_hub_id": hub["id"], "target_hub_id": hub3["id"]}
                )
                assert response.status_code == 400
                assert "not connected" in response.json()["detail"]
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_hub_deletion_breaks_connections(self):
        """Test that deleting a hub breaks all its connections"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "hub-deletion-test")

                # Create three hubs in a line: hub1 - hub2 - hub3
                hubs = []
                for i in range(3):
                    hub_node = await create_test_node(client, mesh["id"], f"hub{i+1}-node")
                    hub = await create_test_hub(client, mesh["id"], hub_node["id"])
                    hubs.append(hub)

                # Connect hub1-hub2 and hub2-hub3
                await client.post(
                    f"/mesh/{mesh['id']}/connect_hubs",
                    json={"source_hub_id": hubs[0]["id"], "target_hub_id": hubs[1]["id"]}
                )
                await client.post(
                    f"/mesh/{mesh['id']}/connect_hubs",
                    json={"source_hub_id": hubs[1]["id"], "target_hub_id": hubs[2]["id"]}
                )

                # Verify connections exist
                response = await client.get(f"/mesh/{mesh['id']}/hub")
                hub_data = response.json()
                hubs_by_id = {h["id"]: h for h in hub_data}

                assert len(hubs_by_id[hubs[0]["id"]]["connected_hubs"]) == 1
                assert len(hubs_by_id[hubs[1]["id"]]["connected_hubs"]) == 2
                assert len(hubs_by_id[hubs[2]["id"]]["connected_hubs"]) == 1

                # Delete middle hub
                response = await client.delete(f"/mesh/{mesh['id']}/hub/{hubs[1]['id']}")
                assert response.status_code == 204

                # Verify remaining hubs have no connections
                response = await client.get(f"/mesh/{mesh['id']}/hub")
                remaining_hubs = response.json()

                for hub in remaining_hubs:
                    assert len(hub["connected_hubs"]) == 0
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_scale_hub_connections(self):
        """Test many hub connections (star topology)"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "hub-scale-test")

                # Create central hub
                central_hub_node = await create_test_node(client, mesh["id"], "central-hub")
                central_hub = await create_test_hub(client, mesh["id"], central_hub_node["id"])

                # Create many edge hubs connected to central hub (star topology)
                edge_hubs = []
                num_edge_hubs = 10

                for i in range(num_edge_hubs):
                    edge_hub_node = await create_test_node(client, mesh["id"], f"edge-hub-{i}")
                    edge_hub = await create_test_hub(client, mesh["id"], edge_hub_node["id"])
                    edge_hubs.append(edge_hub)

                    # Connect to central hub
                    response = await client.post(
                        f"/mesh/{mesh['id']}/connect_hubs",
                        json={"source_hub_id": central_hub["id"], "target_hub_id": edge_hub["id"]}
                    )
                    assert response.status_code == 200

                # Verify central hub has connections to all edge hubs
                response = await client.get(f"/mesh/{mesh['id']}/hub")
                hubs_data = response.json()

                central_hub_data = next(h for h in hubs_data if h["id"] == central_hub["id"])
                assert len(central_hub_data["connected_hubs"]) == num_edge_hubs

                # Verify each edge hub has exactly one connection (to central hub)
                for hub_data in hubs_data:
                    if hub_data["id"] != central_hub["id"]:
                        assert len(hub_data["connected_hubs"]) == 1
                        assert hub_data["connected_hubs"][0]["id"] == central_hub["id"]
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_mesh_response_includes_hub_connections(self):
        """Test that mesh responses include hub connection information"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "mesh-response-test")

                # Create two connected hubs
                hub1_node = await create_test_node(client, mesh["id"], "hub1-node")
                hub2_node = await create_test_node(client, mesh["id"], "hub2-node")

                hub1 = await create_test_hub(client, mesh["id"], hub1_node["id"])
                hub2 = await create_test_hub(client, mesh["id"], hub2_node["id"])

                await client.post(
                    f"/mesh/{mesh['id']}/connect_hubs",
                    json={"source_hub_id": hub1["id"], "target_hub_id": hub2["id"]}
                )

                # Test individual mesh retrieval
                response = await client.get(f"/mesh/{mesh['id']}")
                assert response.status_code == 200
                mesh_data = response.json()

                hubs_by_id = {h["id"]: h for h in mesh_data["hubs"]}
                assert len(hubs_by_id[hub1["id"]]["connected_hubs"]) == 1
                assert len(hubs_by_id[hub2["id"]]["connected_hubs"]) == 1

                # Test mesh list retrieval
                response = await client.get("/mesh")
                assert response.status_code == 200
                meshes = response.json()

                test_mesh = next(m for m in meshes if m["id"] == mesh["id"])
                hubs_by_id = {h["id"]: h for h in test_mesh["hubs"]}
                assert len(hubs_by_id[hub1["id"]]["connected_hubs"]) == 1
                assert len(hubs_by_id[hub2["id"]]["connected_hubs"]) == 1
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_hub_cannot_connect_to_itself_comprehensive(self):
        """Test comprehensive scenarios where a hub cannot connect to itself"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "self-connection-prevention-test")

                # Create a single node
                node = await create_test_node(client, mesh["id"], "hub-node")

                # Convert node to hub
                hub = await create_test_hub(client, mesh["id"], node["id"])

                # Test 1: Direct self-connection (source_hub_id == target_hub_id)
                response = await client.post(
                    f"/mesh/{mesh['id']}/connect_hubs",
                    json={"source_hub_id": hub["id"], "target_hub_id": hub["id"]}
                )
                assert response.status_code == 400
                assert "cannot connect to itself" in response.json()["detail"]

                # Test 2: Try reverse order (same hub as both source and target)
                response = await client.post(
                    f"/mesh/{mesh['id']}/connect_hubs",
                    json={"source_hub_id": hub["id"], "target_hub_id": hub["id"]}
                )
                assert response.status_code == 400
                assert "cannot connect to itself" in response.json()["detail"]

                # Test 3: Verify hub has no connections after failed attempts
                response = await client.get(f"/mesh/{mesh['id']}/hub")
                hubs = response.json()

                hub_data = next(h for h in hubs if h["id"] == hub["id"])
                assert len(hub_data["connected_hubs"]) == 0
                assert len(hub_data["spokes"]) == 0  # Should have no spokes either

                # Test 4: Try to disconnect from itself (should fail gracefully)
                response = await client.post(
                    f"/mesh/{mesh['id']}/disconnect_hubs",
                    json={"source_hub_id": hub["id"], "target_hub_id": hub["id"]}
                )
                assert response.status_code == 400
                assert "not connected" in response.json()["detail"]

                # Test 5: Verify we can still connect to OTHER hubs normally
                # Create another hub
                other_node = await create_test_node(client, mesh["id"], "other-hub-node")
                other_hub = await create_test_hub(client, mesh["id"], other_node["id"])

                # This should work fine
                response = await client.post(
                    f"/mesh/{mesh['id']}/connect_hubs",
                    json={"source_hub_id": hub["id"], "target_hub_id": other_hub["id"]}
                )
                assert response.status_code == 200

                # Verify the connection exists
                response = await client.get(f"/mesh/{mesh['id']}/hub")
                hubs = response.json()
                hubs_by_id = {h["id"]: h for h in hubs}

                assert len(hubs_by_id[hub["id"]]["connected_hubs"]) == 1
                assert len(hubs_by_id[other_hub["id"]]["connected_hubs"]) == 1
                assert hubs_by_id[hub["id"]]["connected_hubs"][0]["id"] == other_hub["id"]
                assert hubs_by_id[other_hub["id"]]["connected_hubs"][0]["id"] == hub["id"]

        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_node_cannot_link_to_itself_as_hub(self):
        """Test that a node cannot be linked to itself as a hub (spoke of its own hub)"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "node-self-link-prevention-test")

                # Create a node
                node = await create_test_node(client, mesh["id"], "hub-node")

                # Convert node to hub
                hub = await create_test_hub(client, mesh["id"], node["id"])

                # Try to link the same node to its own hub (should fail)
                response = await client.post(
                    f"/mesh/{mesh['id']}/link_to_hub",
                    json={"node_id": node["id"], "hub_id": hub["id"]}
                )
                assert response.status_code == 400
                assert "cannot be linked to itself as a hub" in response.json()["detail"]

                # Verify hub has no spokes
                response = await client.get(f"/mesh/{mesh['id']}/hub")
                hubs = response.json()

                hub_data = next(h for h in hubs if h["id"] == hub["id"])
                assert len(hub_data["spokes"]) == 0

                # Verify we can still link OTHER nodes to this hub normally
                other_node = await create_test_node(client, mesh["id"], "other-node")

                response = await client.post(
                    f"/mesh/{mesh['id']}/link_to_hub",
                    json={"node_id": other_node["id"], "hub_id": hub["id"]}
                )
                assert response.status_code == 200

                # Verify the other node is linked
                response = await client.get(f"/mesh/{mesh['id']}/hub")
                hubs = response.json()

                hub_data = next(h for h in hubs if h["id"] == hub["id"])
                assert len(hub_data["spokes"]) == 1
                assert hub_data["spokes"][0]["id"] == other_node["id"]

                # Verify the hub node itself is NOT in the spokes
                spoke_ids = [spoke["id"] for spoke in hub_data["spokes"]]
                assert node["id"] not in spoke_ids

        finally:
            await db_manager.teardown()