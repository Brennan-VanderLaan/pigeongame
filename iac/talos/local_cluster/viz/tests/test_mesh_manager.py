"""
Tests for the mesh_manager common library
"""

import pytest
import json
from tests.test_base import TestDatabaseManager, TestClient
from mesh_manager import MeshNetworkManager
from models import MeshCreate, NodeCreate, HubCreate, LinkRequest, HubLinkRequest
from database import AsyncSessionLocal


class TestMeshManagerLibrary:
    """Tests to verify the mesh manager library works correctly"""

    @pytest.mark.asyncio
    async def test_mesh_manager_creates_mesh(self):
        """Test that the mesh manager can create a mesh"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with AsyncSessionLocal() as db:
                manager = MeshNetworkManager(db)

                mesh_create = MeshCreate(name="manager-test-mesh")
                mesh = await manager.meshes.create_mesh(mesh_create)

                assert mesh.name == "manager-test-mesh"
                assert mesh.nodes == []
                assert mesh.hubs == []
                assert mesh.id is not None
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_mesh_manager_creates_node_with_data(self):
        """Test that the mesh manager can create a node with JSON data"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with AsyncSessionLocal() as db:
                manager = MeshNetworkManager(db)

                # Create mesh first
                mesh_create = MeshCreate(name="node-data-test-mesh")
                mesh = await manager.meshes.create_mesh(mesh_create)

                # Create node with complex data
                node_data = {
                    "environment": "production",
                    "server_config": {
                        "cpu_cores": 8,
                        "memory_gb": 32,
                        "storage_gb": 500
                    },
                    "tags": ["critical", "database"],
                    "monitoring": True
                }

                node_create = NodeCreate(
                    name="test-server",
                    addrs=["192.168.1.10", "10.0.0.5"],
                    data=node_data
                )

                node = await manager.nodes.add_node_to_mesh(mesh.id, node_create)

                assert node is not None
                assert node.name == "test-server"
                assert node.addrs == ["192.168.1.10", "10.0.0.5"]
                assert node.data["environment"] == "production"
                assert node.data["server_config"]["cpu_cores"] == 8
                assert node.data["tags"] == ["critical", "database"]
                assert node.data["monitoring"] == True
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_mesh_manager_hub_operations(self):
        """Test hub creation and management through the mesh manager"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with AsyncSessionLocal() as db:
                manager = MeshNetworkManager(db)

                # Create mesh and node
                mesh_create = MeshCreate(name="hub-test-mesh")
                mesh = await manager.meshes.create_mesh(mesh_create)

                node_create = NodeCreate(
                    name="hub-node",
                    addrs=["192.168.1.1"],
                    data={"role": "hub", "capacity": "high"}
                )
                node = await manager.nodes.add_node_to_mesh(mesh.id, node_create)

                # Create hub
                hub_create = HubCreate(node_id=node.id)
                result = await manager.hubs.create_hub(mesh.id, hub_create)

                assert "hub" in result
                hub = result["hub"]
                assert hub.name == "hub-node"
                assert hub.node_id == node.id
                assert hub.spokes == []

                # Get hubs list
                hubs = await manager.hubs.get_hubs(mesh.id)
                assert len(hubs) == 1
                assert hubs[0].name == "hub-node"
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_mesh_manager_link_operations(self):
        """Test link operations through the mesh manager"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with AsyncSessionLocal() as db:
                manager = MeshNetworkManager(db)

                # Create mesh
                mesh_create = MeshCreate(name="link-test-mesh")
                mesh = await manager.meshes.create_mesh(mesh_create)

                # Create hub node
                hub_node_create = NodeCreate(
                    name="hub-node",
                    addrs=["192.168.1.1"],
                    data={"role": "hub"}
                )
                hub_node = await manager.nodes.add_node_to_mesh(mesh.id, hub_node_create)

                # Create spoke node
                spoke_node_create = NodeCreate(
                    name="spoke-node",
                    addrs=["192.168.1.2"],
                    data={"role": "spoke", "service": "web"}
                )
                spoke_node = await manager.nodes.add_node_to_mesh(mesh.id, spoke_node_create)

                # Create hub
                hub_create = HubCreate(node_id=hub_node.id)
                hub_result = await manager.hubs.create_hub(mesh.id, hub_create)
                hub = hub_result["hub"]

                # Link spoke to hub
                link_request = LinkRequest(node_id=spoke_node.id, hub_id=hub.id)
                link_result = await manager.links.link_node_to_hub(mesh.id, link_request)

                assert "message" in link_result
                assert link_result["message"] == "Node linked to hub successfully"

                # Verify link exists
                hubs = await manager.hubs.get_hubs(mesh.id)
                assert len(hubs) == 1
                assert len(hubs[0].spokes) == 1
                assert hubs[0].spokes[0].name == "spoke-node"
                assert hubs[0].spokes[0].data["service"] == "web"
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_mesh_manager_error_handling(self):
        """Test error handling in the mesh manager"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with AsyncSessionLocal() as db:
                manager = MeshNetworkManager(db)

                fake_uuid = "12345678-1234-5678-1234-567812345678"

                # Test mesh not found
                mesh = await manager.meshes.get_mesh(fake_uuid)
                assert mesh is None

                # Test node creation with non-existent mesh
                node_create = NodeCreate(name="orphan", addrs=["192.168.1.1"], data={})
                node = await manager.nodes.add_node_to_mesh(fake_uuid, node_create)
                assert node is None

                # Test hub creation with non-existent mesh
                hub_create = HubCreate(node_id=fake_uuid)
                hub_result = await manager.hubs.create_hub(fake_uuid, hub_create)
                assert "error" in hub_result
                assert hub_result["status_code"] == 404
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_mesh_manager_complete_workflow(self):
        """Test a complete workflow using the mesh manager"""
        db_manager = TestDatabaseManager()
        await db_manager.setup()

        try:
            async with AsyncSessionLocal() as db:
                manager = MeshNetworkManager(db)

                # Create mesh
                mesh_create = MeshCreate(name="complete-workflow-test")
                mesh = await manager.meshes.create_mesh(mesh_create)

                # Create multiple nodes with different data
                datacenter_node = await manager.nodes.add_node_to_mesh(
                    mesh.id,
                    NodeCreate(
                        name="datacenter",
                        addrs=["10.1.0.1"],
                        data={"role": "hub", "location": "us-east", "capacity": "high"}
                    )
                )

                web_server_node = await manager.nodes.add_node_to_mesh(
                    mesh.id,
                    NodeCreate(
                        name="web-server",
                        addrs=["192.168.1.10"],
                        data={"role": "web", "service": "nginx", "cpu_cores": 4}
                    )
                )

                db_server_node = await manager.nodes.add_node_to_mesh(
                    mesh.id,
                    NodeCreate(
                        name="db-server",
                        addrs=["192.168.1.20"],
                        data={"role": "database", "service": "postgresql", "storage_gb": 1000}
                    )
                )

                # Create hub from datacenter
                hub_result = await manager.hubs.create_hub(
                    mesh.id,
                    HubCreate(node_id=datacenter_node.id)
                )
                hub = hub_result["hub"]

                # Link servers to hub
                await manager.links.link_node_to_hub(
                    mesh.id,
                    LinkRequest(node_id=web_server_node.id, hub_id=hub.id)
                )
                await manager.links.link_node_to_hub(
                    mesh.id,
                    LinkRequest(node_id=db_server_node.id, hub_id=hub.id)
                )

                # Verify final state
                final_mesh = await manager.meshes.get_mesh(mesh.id)
                assert len(final_mesh.nodes) == 3
                assert len(final_mesh.hubs) == 1
                assert len(final_mesh.hubs[0].spokes) == 2

                # Verify data is preserved
                spoke_names = [spoke.name for spoke in final_mesh.hubs[0].spokes]
                assert "web-server" in spoke_names
                assert "db-server" in spoke_names

                # Check specific node data
                for spoke in final_mesh.hubs[0].spokes:
                    if spoke.name == "web-server":
                        assert spoke.data["service"] == "nginx"
                        assert spoke.data["cpu_cores"] == 4
                    elif spoke.name == "db-server":
                        assert spoke.data["service"] == "postgresql"
                        assert spoke.data["storage_gb"] == 1000
        finally:
            await db_manager.teardown()