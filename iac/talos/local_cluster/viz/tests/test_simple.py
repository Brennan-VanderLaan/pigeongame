import pytest
from tests.test_base import DatabaseManager, ApiClient

@pytest.mark.asyncio
async def test_create_mesh():
    """Test creating a mesh"""
    db_manager = DatabaseManager()
    await db_manager.setup()

    try:
        async with ApiClient() as client:
            response = await client.post("/mesh", json={"name": "test-mesh"})
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "test-mesh"
            assert "id" in data
            assert data["nodes"] == []
            assert data["hubs"] == []
    finally:
        await db_manager.teardown()

@pytest.mark.asyncio
async def test_full_workflow():
    """Test the complete workflow: create mesh, add node, create hub, link"""
    db_manager = DatabaseManager()
    await db_manager.setup()

    try:
        async with ApiClient() as client:
            # Create mesh
            response = await client.post("/mesh", json={"name": "test-mesh"})
            assert response.status_code == 201
            mesh = response.json()
            mesh_id = mesh["id"]

            # Add two nodes
            response = await client.post(
                f"/mesh/{mesh_id}/node",
                json={"name": "hub-node", "addrs": ["192.168.1.1"]}
            )
            assert response.status_code == 201
            hub_node = response.json()

            response = await client.post(
                f"/mesh/{mesh_id}/node",
                json={"name": "spoke-node", "addrs": ["192.168.1.2"]}
            )
            assert response.status_code == 201
            spoke_node = response.json()

            # Create hub from first node
            response = await client.post(
                f"/mesh/{mesh_id}/hub",
                json={"node_id": hub_node["id"]}
            )
            assert response.status_code == 201
            hub = response.json()

            # Link spoke node to hub
            response = await client.post(
                f"/mesh/{mesh_id}/link_to_hub",
                json={"node_id": spoke_node["id"], "hub_id": hub["id"]}
            )
            assert response.status_code == 200

            # Verify the mesh structure
            response = await client.get(f"/mesh/{mesh_id}")
            assert response.status_code == 200
            mesh_data = response.json()
            assert len(mesh_data["nodes"]) == 2
            assert len(mesh_data["hubs"]) == 1
            assert len(mesh_data["hubs"][0]["spokes"]) == 1

    finally:
        await db_manager.teardown()