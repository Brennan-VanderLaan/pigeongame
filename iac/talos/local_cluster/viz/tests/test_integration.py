"""
Integration tests for complete user workflows
"""

import pytest
from tests.test_base import DatabaseManager, ApiClient


class TestUserWorkflows:
    """Integration tests for realistic user scenarios"""

    @pytest.mark.asyncio
    async def test_basic_mesh_workflow(self):
        """Test: User creates mesh, adds nodes, creates hub, links nodes"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # 1. User creates a new mesh
                mesh_response = await client.post("/mesh", json={"name": "company-network"})
                assert mesh_response.status_code == 201
                mesh = mesh_response.json()

                # 2. User adds several nodes to represent different locations
                datacenter = await client.post(
                    f"/mesh/{mesh['id']}/node",
                    json={"name": "datacenter-primary", "addrs": ["10.1.0.1", "192.168.100.1"], "data": {}}
                )
                assert datacenter.status_code == 201
                dc_node = datacenter.json()

                branch_office = await client.post(
                    f"/mesh/{mesh['id']}/node",
                    json={"name": "branch-office-nyc", "addrs": ["172.16.1.1"], "data": {}}
                )
                assert branch_office.status_code == 201
                branch_node = branch_office.json()

                remote_worker = await client.post(
                    f"/mesh/{mesh['id']}/node",
                    json={"name": "remote-worker-laptop", "addrs": ["192.168.1.100"], "data": {}}
                )
                assert remote_worker.status_code == 201
                remote_node = remote_worker.json()

                # 3. User promotes datacenter to be a hub
                hub_response = await client.post(
                    f"/mesh/{mesh['id']}/hub",
                    json={"node_id": dc_node["id"]}
                )
                assert hub_response.status_code == 201
                hub = hub_response.json()

                # 4. User connects branch office and remote worker to datacenter hub
                link1_response = await client.post(
                    f"/mesh/{mesh['id']}/link_to_hub",
                    json={"node_id": branch_node["id"], "hub_id": hub["id"]}
                )
                assert link1_response.status_code == 200

                link2_response = await client.post(
                    f"/mesh/{mesh['id']}/link_to_hub",
                    json={"node_id": remote_node["id"], "hub_id": hub["id"]}
                )
                assert link2_response.status_code == 200

                # 5. User verifies the final network topology
                final_mesh_response = await client.get(f"/mesh/{mesh['id']}")
                assert final_mesh_response.status_code == 200

                final_mesh = final_mesh_response.json()
                assert len(final_mesh["nodes"]) == 3
                assert len(final_mesh["hubs"]) == 1

                # Verify hub has both spokes
                hub_data = final_mesh["hubs"][0]
                assert len(hub_data["spokes"]) == 2
                spoke_names = [spoke["name"] for spoke in hub_data["spokes"]]
                assert "branch-office-nyc" in spoke_names
                assert "remote-worker-laptop" in spoke_names

        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_network_reconfiguration_workflow(self):
        """Test: User reconfigures network topology over time"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Initial setup: Create mesh with multiple datacenters
                mesh_response = await client.post("/mesh", json={"name": "multi-dc-network"})
                mesh = mesh_response.json()

                # Create nodes for different datacenters
                dc_east = await client.post(
                    f"/mesh/{mesh['id']}/node",
                    json={"name": "datacenter-east", "addrs": ["10.1.0.1"], "data": {}}
                )
                dc_east_node = dc_east.json()

                dc_west = await client.post(
                    f"/mesh/{mesh['id']}/node",
                    json={"name": "datacenter-west", "addrs": ["10.2.0.1"], "data": {}}
                )
                dc_west_node = dc_west.json()

                edge_device = await client.post(
                    f"/mesh/{mesh['id']}/node",
                    json={"name": "edge-device", "addrs": ["172.16.1.1"], "data": {}}
                )
                edge_node = edge_device.json()

                # Phase 1: Initially connect everything to east datacenter
                hub_east_response = await client.post(
                    f"/mesh/{mesh['id']}/hub",
                    json={"node_id": dc_east_node["id"]}
                )
                hub_east = hub_east_response.json()

                await client.post(
                    f"/mesh/{mesh['id']}/link_to_hub",
                    json={"node_id": dc_west_node["id"], "hub_id": hub_east["id"]}
                )

                await client.post(
                    f"/mesh/{mesh['id']}/link_to_hub",
                    json={"node_id": edge_node["id"], "hub_id": hub_east["id"]}
                )

                # Verify initial configuration
                hubs_response = await client.get(f"/mesh/{mesh['id']}/hub")
                hubs = hubs_response.json()
                assert len(hubs) == 1
                assert len(hubs[0]["spokes"]) == 2

                # Phase 2: Create west datacenter as second hub
                hub_west_response = await client.post(
                    f"/mesh/{mesh['id']}/hub",
                    json={"node_id": dc_west_node["id"]}
                )
                hub_west = hub_west_response.json()

                # This should automatically unlink west datacenter from east hub
                # since a node can't be both a hub and a spoke

                # Phase 3: Move edge device to west datacenter
                # First unlink from east
                await client.post(
                    f"/mesh/{mesh['id']}/unlink_from_hub",
                    json={"node_id": edge_node["id"], "hub_id": hub_east["id"]}
                )

                # Then link to west
                await client.post(
                    f"/mesh/{mesh['id']}/link_to_hub",
                    json={"node_id": edge_node["id"], "hub_id": hub_west["id"]}
                )

                # Verify final configuration
                final_hubs_response = await client.get(f"/mesh/{mesh['id']}/hub")
                final_hubs = final_hubs_response.json()
                assert len(final_hubs) == 2

                # Each hub should have the correct spokes
                hubs_by_name = {hub["name"]: hub for hub in final_hubs}
                assert len(hubs_by_name["datacenter-east"]["spokes"]) == 0
                assert len(hubs_by_name["datacenter-west"]["spokes"]) == 1
                assert hubs_by_name["datacenter-west"]["spokes"][0]["name"] == "edge-device"

        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_multi_mesh_environment(self):
        """Test: User manages multiple independent mesh networks"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create multiple meshes for different purposes
                production_mesh = await client.post("/mesh", json={"name": "production-network"})
                prod_mesh = production_mesh.json()

                staging_mesh = await client.post("/mesh", json={"name": "staging-network"})
                stage_mesh = staging_mesh.json()

                development_mesh = await client.post("/mesh", json={"name": "development-network"})
                dev_mesh = development_mesh.json()

                # Setup production environment (hub-spoke)
                prod_hub_node = await client.post(
                    f"/mesh/{prod_mesh['id']}/node",
                    json={"name": "prod-datacenter", "addrs": ["10.0.1.1"], "data": {}}
                )
                prod_hub_node = prod_hub_node.json()

                prod_worker1 = await client.post(
                    f"/mesh/{prod_mesh['id']}/node",
                    json={"name": "prod-worker-1", "addrs": ["10.0.1.10"], "data": {}}
                )
                prod_worker1 = prod_worker1.json()

                prod_hub = await client.post(
                    f"/mesh/{prod_mesh['id']}/hub",
                    json={"node_id": prod_hub_node["id"]}
                )
                prod_hub = prod_hub.json()

                await client.post(
                    f"/mesh/{prod_mesh['id']}/link_to_hub",
                    json={"node_id": prod_worker1["id"], "hub_id": prod_hub["id"]}
                )

                # Setup staging environment (different topology)
                stage_node1 = await client.post(
                    f"/mesh/{stage_mesh['id']}/node",
                    json={"name": "stage-server-1", "addrs": ["10.0.2.1"], "data": {}}
                )
                stage_node1 = stage_node1.json()

                stage_node2 = await client.post(
                    f"/mesh/{stage_mesh['id']}/node",
                    json={"name": "stage-server-2", "addrs": ["10.0.2.2"], "data": {}}
                )
                stage_node2 = stage_node2.json()

                # Setup development environment (minimal)
                dev_node = await client.post(
                    f"/mesh/{dev_mesh['id']}/node",
                    json={"name": "dev-laptop", "addrs": ["192.168.1.100"], "data": {}}
                )
                dev_node = dev_node.json()

                # Verify each mesh is independent
                all_meshes_response = await client.get("/mesh")
                all_meshes = all_meshes_response.json()
                assert len(all_meshes) == 3

                meshes_by_name = {mesh["name"]: mesh for mesh in all_meshes}

                # Production mesh should have 2 nodes, 1 hub with 1 spoke
                prod_mesh_data = meshes_by_name["production-network"]
                assert len(prod_mesh_data["nodes"]) == 2
                assert len(prod_mesh_data["hubs"]) == 1
                assert len(prod_mesh_data["hubs"][0]["spokes"]) == 1

                # Staging mesh should have 2 nodes, 0 hubs
                stage_mesh_data = meshes_by_name["staging-network"]
                assert len(stage_mesh_data["nodes"]) == 2
                assert len(stage_mesh_data["hubs"]) == 0

                # Development mesh should have 1 node, 0 hubs
                dev_mesh_data = meshes_by_name["development-network"]
                assert len(dev_mesh_data["nodes"]) == 1
                assert len(dev_mesh_data["hubs"]) == 0

                # Verify operations on one mesh don't affect others
                # Delete staging mesh
                await client.delete(f"/mesh/{stage_mesh['id']}")

                # Production and development should still exist
                remaining_meshes_response = await client.get("/mesh")
                remaining_meshes = remaining_meshes_response.json()
                assert len(remaining_meshes) == 2

                remaining_names = [mesh["name"] for mesh in remaining_meshes]
                assert "production-network" in remaining_names
                assert "development-network" in remaining_names
                assert "staging-network" not in remaining_names

        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self):
        """Test: User handles various error conditions gracefully"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # User tries to work with non-existent mesh
                fake_uuid = "12345678-1234-5678-1234-567812345678"

                # Should get clear error messages
                response = await client.get(f"/mesh/{fake_uuid}")
                assert response.status_code == 404
                error = response.json()
                assert "Mesh not found" in error["detail"]

                # Create a real mesh for further testing
                mesh_response = await client.post("/mesh", json={"name": "error-test-mesh"})
                mesh = mesh_response.json()

                # User tries to create hub from non-existent node
                response = await client.post(
                    f"/mesh/{mesh['id']}/hub",
                    json={"node_id": fake_uuid}
                )
                assert response.status_code == 404
                error = response.json()
                assert "Node not found" in error["detail"]

                # User creates a node and tries to make duplicate hubs
                node_response = await client.post(
                    f"/mesh/{mesh['id']}/node",
                    json={"name": "test-node", "addrs": ["192.168.1.1"], "data": {}}
                )
                node = node_response.json()

                # First hub creation should work
                hub_response = await client.post(
                    f"/mesh/{mesh['id']}/hub",
                    json={"node_id": node["id"]}
                )
                assert hub_response.status_code == 201

                # Second hub creation should fail with clear error
                duplicate_response = await client.post(
                    f"/mesh/{mesh['id']}/hub",
                    json={"node_id": node["id"]}
                )
                assert duplicate_response.status_code == 400
                error = duplicate_response.json()
                assert "already a hub" in error["detail"]

                # User tries to link non-existent nodes
                hub = hub_response.json()

                response = await client.post(
                    f"/mesh/{mesh['id']}/link_to_hub",
                    json={"node_id": fake_uuid, "hub_id": hub["id"]}
                )
                assert response.status_code == 404

                response = await client.post(
                    f"/mesh/{mesh['id']}/link_to_hub",
                    json={"node_id": node["id"], "hub_id": fake_uuid}
                )
                assert response.status_code == 404

                # All error responses should have consistent format
                # (status code + detail message in JSON)

        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_scale_test_workflow(self):
        """Test: Create a larger mesh network to verify scalability"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create a mesh for a medium-sized organization
                mesh_response = await client.post("/mesh", json={"name": "enterprise-mesh"})
                mesh = mesh_response.json()

                # Create multiple hubs (regional datacenters)
                regions = ["us-east", "us-west", "eu-central", "asia-pacific"]
                hubs = []

                for region in regions:
                    # Create datacenter node
                    dc_response = await client.post(
                        f"/mesh/{mesh['id']}/node",
                        json={"name": f"datacenter-{region}", "addrs": [f"10.{len(hubs)+1}.0.1"], "data": {}}
                    )
                    dc_node = dc_response.json()

                    # Make it a hub
                    hub_response = await client.post(
                        f"/mesh/{mesh['id']}/hub",
                        json={"node_id": dc_node["id"]}
                    )
                    hub = hub_response.json()
                    hubs.append(hub)

                # Create multiple edge nodes for each region
                for i, hub in enumerate(hubs):
                    region = regions[i]
                    for j in range(3):  # 3 edge nodes per region
                        edge_response = await client.post(
                            f"/mesh/{mesh['id']}/node",
                            json={
                                "name": f"edge-{region}-{j+1}",
                                "addrs": [f"172.{i+1}.{j+1}.1"],
                                "data": {}
                            }
                        )
                        edge_node = edge_response.json()

                        # Link to regional hub
                        await client.post(
                            f"/mesh/{mesh['id']}/link_to_hub",
                            json={"node_id": edge_node["id"], "hub_id": hub["id"]}
                        )

                # Verify final topology
                final_mesh_response = await client.get(f"/mesh/{mesh['id']}")
                final_mesh = final_mesh_response.json()

                # Should have 4 datacenters + 12 edge nodes = 16 total nodes
                assert len(final_mesh["nodes"]) == 16

                # Should have 4 hubs
                assert len(final_mesh["hubs"]) == 4

                # Each hub should have exactly 3 spokes
                for hub in final_mesh["hubs"]:
                    assert len(hub["spokes"]) == 3

                # Verify we can still query individual components efficiently
                hubs_response = await client.get(f"/mesh/{mesh['id']}/hub")
                assert hubs_response.status_code == 200
                hubs_data = hubs_response.json()
                assert len(hubs_data) == 4

        finally:
            await db_manager.teardown()