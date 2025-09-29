"""
Unit tests for individual API endpoints
"""

import pytest
from tests.test_base import TestDatabaseManager, TestClient, create_test_mesh, create_test_node, create_test_hub


class TestMeshEndpoints:
    """Unit tests for mesh-related endpoints"""

    @pytest.mark.asyncio
    async def test_create_mesh(self):
        """Test mesh creation"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with TestClient() as client:
                response = await client.post("/mesh", json={"name": "unit-test-mesh"})
                assert response.status_code == 201

                mesh = response.json()
                assert mesh["name"] == "unit-test-mesh"
                assert "id" in mesh
                assert mesh["nodes"] == []
                assert mesh["hubs"] == []
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_get_mesh_by_id(self):
        """Test retrieving mesh by ID"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with TestClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "retrieval-test")

                # Retrieve mesh
                response = await client.get(f"/mesh/{mesh['id']}")
                assert response.status_code == 200

                retrieved = response.json()
                assert retrieved["id"] == mesh["id"]
                assert retrieved["name"] == "retrieval-test"
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_get_nonexistent_mesh(self):
        """Test error handling for non-existent mesh"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with TestClient() as client:
                fake_uuid = "12345678-1234-5678-1234-567812345678"
                response = await client.get(f"/mesh/{fake_uuid}")
                assert response.status_code == 404
                assert "Mesh not found" in response.json()["detail"]
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_list_meshes(self):
        """Test listing all meshes"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with TestClient() as client:
                # Create multiple meshes
                mesh1 = await create_test_mesh(client, "mesh-1")
                mesh2 = await create_test_mesh(client, "mesh-2")

                # List all meshes
                response = await client.get("/mesh")
                assert response.status_code == 200

                meshes = response.json()
                assert len(meshes) == 2
                mesh_names = [m["name"] for m in meshes]
                assert "mesh-1" in mesh_names
                assert "mesh-2" in mesh_names
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_delete_mesh(self):
        """Test mesh deletion"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with TestClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "deletable-mesh")

                # Delete mesh
                response = await client.delete(f"/mesh/{mesh['id']}")
                assert response.status_code == 204

                # Verify deletion
                response = await client.get(f"/mesh/{mesh['id']}")
                assert response.status_code == 404
        finally:
            await db_manager.teardown()


class TestNodeEndpoints:
    """Unit tests for node-related endpoints"""

    @pytest.mark.asyncio
    async def test_add_node_to_mesh(self):
        """Test adding a node to a mesh"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with TestClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client)

                # Add node
                node_data = {"name": "unit-test-node", "addrs": ["10.0.0.1", "192.168.1.1"], "data": {}}
                response = await client.post(f"/mesh/{mesh['id']}/node", json=node_data)
                assert response.status_code == 201

                node = response.json()
                assert node["name"] == "unit-test-node"
                assert node["addrs"] == ["10.0.0.1", "192.168.1.1"]
                assert node["data"] == {}
                assert "id" in node
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_add_node_to_nonexistent_mesh(self):
        """Test error when adding node to non-existent mesh"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with TestClient() as client:
                fake_uuid = "12345678-1234-5678-1234-567812345678"
                node_data = {"name": "orphan-node", "addrs": ["192.168.1.1"], "data": {}}

                response = await client.post(f"/mesh/{fake_uuid}/node", json=node_data)
                assert response.status_code == 404
                assert "Mesh not found" in response.json()["detail"]
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_remove_node_from_mesh(self):
        """Test removing a node from a mesh"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with TestClient() as client:
                # Create mesh and node
                mesh = await create_test_mesh(client)
                node = await create_test_node(client, mesh["id"], "removable-node")

                # Remove node
                response = await client.delete(f"/mesh/{mesh['id']}/node/{node['id']}")
                assert response.status_code == 204

                # Verify node is gone
                response = await client.get(f"/mesh/{mesh['id']}")
                updated_mesh = response.json()
                assert len(updated_mesh["nodes"]) == 0
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_remove_nonexistent_node(self):
        """Test error when removing non-existent node"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with TestClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client)

                fake_uuid = "12345678-1234-5678-1234-567812345678"
                response = await client.delete(f"/mesh/{mesh['id']}/node/{fake_uuid}")
                assert response.status_code == 404
        finally:
            await db_manager.teardown()


class TestHubEndpoints:
    """Unit tests for hub-related endpoints"""

    @pytest.mark.asyncio
    async def test_create_hub_from_node(self):
        """Test creating a hub from an existing node"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with TestClient() as client:
                # Create mesh and node
                mesh = await create_test_mesh(client)
                node = await create_test_node(client, mesh["id"], "hub-node")

                # Create hub
                hub = await create_test_hub(client, mesh["id"], node["id"])

                assert hub["name"] == "hub-node"
                assert hub["node_id"] == node["id"]
                assert hub["spokes"] == []
                assert "id" in hub
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_create_hub_from_nonexistent_node(self):
        """Test error when creating hub from non-existent node"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with TestClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client)

                fake_uuid = "12345678-1234-5678-1234-567812345678"
                response = await client.post(
                    f"/mesh/{mesh['id']}/hub",
                    json={"node_id": fake_uuid}
                )
                assert response.status_code == 404
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_duplicate_hub_creation(self):
        """Test error when creating duplicate hub"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with TestClient() as client:
                # Create mesh and node
                mesh = await create_test_mesh(client)
                node = await create_test_node(client, mesh["id"], "unique-node")

                # Create hub first time
                await create_test_hub(client, mesh["id"], node["id"])

                # Try to create hub again
                response = await client.post(
                    f"/mesh/{mesh['id']}/hub",
                    json={"node_id": node["id"]}
                )
                assert response.status_code == 400
                assert "already a hub" in response.json()["detail"]
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_get_hubs_in_mesh(self):
        """Test retrieving all hubs in a mesh"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with TestClient() as client:
                # Create mesh and nodes
                mesh = await create_test_mesh(client)
                node1 = await create_test_node(client, mesh["id"], "hub-1")
                node2 = await create_test_node(client, mesh["id"], "hub-2")

                # Create hubs
                await create_test_hub(client, mesh["id"], node1["id"])
                await create_test_hub(client, mesh["id"], node2["id"])

                # Get all hubs
                response = await client.get(f"/mesh/{mesh['id']}/hub")
                assert response.status_code == 200

                hubs = response.json()
                assert len(hubs) == 2
                hub_names = [h["name"] for h in hubs]
                assert "hub-1" in hub_names
                assert "hub-2" in hub_names
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_remove_hub(self):
        """Test removing a hub"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with TestClient() as client:
                # Create mesh, node, and hub
                mesh = await create_test_mesh(client)
                node = await create_test_node(client, mesh["id"], "removable-hub")
                hub = await create_test_hub(client, mesh["id"], node["id"])

                # Remove hub
                response = await client.delete(f"/mesh/{mesh['id']}/hub/{hub['id']}")
                assert response.status_code == 204

                # Verify hub is gone
                response = await client.get(f"/mesh/{mesh['id']}/hub")
                hubs = response.json()
                assert len(hubs) == 0
        finally:
            await db_manager.teardown()


class TestLinkEndpoints:
    """Unit tests for link-related endpoints"""

    @pytest.mark.asyncio
    async def test_link_node_to_hub(self):
        """Test linking a node to a hub"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with TestClient() as client:
                # Create mesh, nodes, and hub
                mesh = await create_test_mesh(client)
                hub_node = await create_test_node(client, mesh["id"], "hub-node")
                spoke_node = await create_test_node(client, mesh["id"], "spoke-node", ["192.168.1.2"])
                hub = await create_test_hub(client, mesh["id"], hub_node["id"])

                # Link spoke to hub
                response = await client.post(
                    f"/mesh/{mesh['id']}/link_to_hub",
                    json={"node_id": spoke_node["id"], "hub_id": hub["id"]}
                )
                assert response.status_code == 200

                # Verify link
                response = await client.get(f"/mesh/{mesh['id']}/hub")
                hubs = response.json()
                assert len(hubs) == 1
                assert len(hubs[0]["spokes"]) == 1
                assert hubs[0]["spokes"][0]["id"] == spoke_node["id"]
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_unlink_node_from_hub(self):
        """Test unlinking a node from a hub"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with TestClient() as client:
                # Create mesh, nodes, hub, and link
                mesh = await create_test_mesh(client)
                hub_node = await create_test_node(client, mesh["id"], "hub-node")
                spoke_node = await create_test_node(client, mesh["id"], "spoke-node", ["192.168.1.2"])
                hub = await create_test_hub(client, mesh["id"], hub_node["id"])

                # Link first
                await client.post(
                    f"/mesh/{mesh['id']}/link_to_hub",
                    json={"node_id": spoke_node["id"], "hub_id": hub["id"]}
                )

                # Then unlink
                response = await client.post(
                    f"/mesh/{mesh['id']}/unlink_from_hub",
                    json={"node_id": spoke_node["id"], "hub_id": hub["id"]}
                )
                assert response.status_code == 200

                # Verify unlink
                response = await client.get(f"/mesh/{mesh['id']}/hub")
                hubs = response.json()
                assert len(hubs) == 1
                assert len(hubs[0]["spokes"]) == 0
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_link_to_nonexistent_hub(self):
        """Test error when linking to non-existent hub"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with TestClient() as client:
                # Create mesh and node
                mesh = await create_test_mesh(client)
                node = await create_test_node(client, mesh["id"], "orphan-node")

                fake_uuid = "12345678-1234-5678-1234-567812345678"
                response = await client.post(
                    f"/mesh/{mesh['id']}/link_to_hub",
                    json={"node_id": node["id"], "hub_id": fake_uuid}
                )
                assert response.status_code == 404
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_link_nonexistent_node(self):
        """Test error when linking non-existent node"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with TestClient() as client:
                # Create mesh, node, and hub
                mesh = await create_test_mesh(client)
                hub_node = await create_test_node(client, mesh["id"], "hub-node")
                hub = await create_test_hub(client, mesh["id"], hub_node["id"])

                fake_uuid = "12345678-1234-5678-1234-567812345678"
                response = await client.post(
                    f"/mesh/{mesh['id']}/link_to_hub",
                    json={"node_id": fake_uuid, "hub_id": hub["id"]}
                )
                assert response.status_code == 404
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_duplicate_link(self):
        """Test error when creating duplicate link"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with TestClient() as client:
                # Create mesh, nodes, hub, and link
                mesh = await create_test_mesh(client)
                hub_node = await create_test_node(client, mesh["id"], "hub-node")
                spoke_node = await create_test_node(client, mesh["id"], "spoke-node", ["192.168.1.2"])
                hub = await create_test_hub(client, mesh["id"], hub_node["id"])

                # Link first time
                response = await client.post(
                    f"/mesh/{mesh['id']}/link_to_hub",
                    json={"node_id": spoke_node["id"], "hub_id": hub["id"]}
                )
                assert response.status_code == 200

                # Try to link again
                response = await client.post(
                    f"/mesh/{mesh['id']}/link_to_hub",
                    json={"node_id": spoke_node["id"], "hub_id": hub["id"]}
                )
                assert response.status_code == 400
                assert "already linked" in response.json()["detail"]
        finally:
            await db_manager.teardown()