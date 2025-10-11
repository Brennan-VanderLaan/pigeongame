"""
Tests for node data field functionality
"""

import pytest
import json
from tests.test_base import DatabaseManager, ApiClient, create_test_mesh


class TestNodeDataField:
    """Tests for the data field in nodes"""

    @pytest.mark.asyncio
    async def test_node_creation_with_simple_data(self):
        """Test creating a node with simple JSON data"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "data-test-mesh")

                # Create node with simple data
                node_data = {
                    "name": "test-node",
                    "addrs": ["192.168.1.1"],
                    "data": {"environment": "production", "region": "us-east"}
                }

                response = await client.post(f"/mesh/{mesh['id']}/node", json=node_data)
                assert response.status_code == 201

                node = response.json()
                assert node["name"] == "test-node"
                assert node["data"]["environment"] == "production"
                assert node["data"]["region"] == "us-east"
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_node_creation_with_empty_data(self):
        """Test creating a node with empty data"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "empty-data-mesh")

                # Create node with empty data
                node_data = {
                    "name": "empty-data-node",
                    "addrs": ["192.168.1.2"],
                    "data": {}
                }

                response = await client.post(f"/mesh/{mesh['id']}/node", json=node_data)
                assert response.status_code == 201

                node = response.json()
                assert node["data"] == {}
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_node_creation_without_data_field(self):
        """Test creating a node without specifying data field (should default to empty)"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "no-data-mesh")

                # Create node without data field
                node_data = {
                    "name": "no-data-node",
                    "addrs": ["192.168.1.3"]
                }

                response = await client.post(f"/mesh/{mesh['id']}/node", json=node_data)
                assert response.status_code == 201

                node = response.json()
                assert node["data"] == {}
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_node_creation_with_complex_data(self):
        """Test creating a node with complex nested JSON data"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "complex-data-mesh")

                # Create node with complex nested data
                complex_data = {
                    "server_config": {
                        "cpu_cores": 16,
                        "memory_gb": 64,
                        "storage": {
                            "type": "SSD",
                            "capacity_gb": 1000
                        },
                        "network": {
                            "interfaces": [
                                {"name": "eth0", "speed": "10Gbps"},
                                {"name": "eth1", "speed": "1Gbps"}
                            ],
                            "vlans": [100, 200, 300]
                        }
                    },
                    "deployment_info": {
                        "deployed_at": "2024-01-01T00:00:00Z",
                        "version": "1.2.3",
                        "tags": ["production", "critical", "database"]
                    }
                }

                node_data = {
                    "name": "complex-node",
                    "addrs": ["192.168.1.4", "10.0.0.1"],
                    "data": complex_data
                }

                response = await client.post(f"/mesh/{mesh['id']}/node", json=node_data)
                assert response.status_code == 201

                node = response.json()
                assert node["data"]["server_config"]["cpu_cores"] == 16
                assert node["data"]["server_config"]["storage"]["type"] == "SSD"
                assert len(node["data"]["server_config"]["network"]["interfaces"]) == 2
                assert node["data"]["deployment_info"]["tags"] == ["production", "critical", "database"]
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_node_data_persistence(self):
        """Test that node data persists correctly when retrieving mesh"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "persistence-test-mesh")

                # Create node with data
                test_data = {
                    "persistence": True,
                    "test_value": 42,
                    "nested": {"key": "value"}
                }

                node_data = {
                    "name": "persistent-node",
                    "addrs": ["192.168.1.5"],
                    "data": test_data
                }

                response = await client.post(f"/mesh/{mesh['id']}/node", json=node_data)
                assert response.status_code == 201
                created_node = response.json()

                # Retrieve mesh and verify data persisted
                response = await client.get(f"/mesh/{mesh['id']}")
                assert response.status_code == 200

                retrieved_mesh = response.json()
                assert len(retrieved_mesh["nodes"]) == 1

                retrieved_node = retrieved_mesh["nodes"][0]
                assert retrieved_node["id"] == created_node["id"]
                assert retrieved_node["data"]["persistence"] == True
                assert retrieved_node["data"]["test_value"] == 42
                assert retrieved_node["data"]["nested"]["key"] == "value"
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_large_data_payload(self):
        """Test creating a node with a large JSON payload"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "large-data-mesh")

                # Create a large data payload (simulating a configuration file or log data)
                large_data = {
                    "configuration": {},
                    "logs": [],
                    "metrics": {}
                }

                # Add lots of configuration entries
                for i in range(100):
                    large_data["configuration"][f"config_key_{i}"] = f"config_value_{i}"

                # Add log entries
                for i in range(50):
                    large_data["logs"].append({
                        "timestamp": f"2024-01-01T{i:02d}:00:00Z",
                        "level": "INFO" if i % 2 == 0 else "WARN",
                        "message": f"Log message number {i} with some additional context"
                    })

                # Add metrics
                for i in range(25):
                    large_data["metrics"][f"metric_{i}"] = {
                        "value": i * 10.5,
                        "unit": "bytes" if i % 2 == 0 else "seconds",
                        "collected_at": f"2024-01-01T{i:02d}:30:00Z"
                    }

                node_data = {
                    "name": "large-data-node",
                    "addrs": ["192.168.1.6"],
                    "data": large_data
                }

                response = await client.post(f"/mesh/{mesh['id']}/node", json=node_data)
                assert response.status_code == 201

                node = response.json()
                assert len(node["data"]["configuration"]) == 100
                assert len(node["data"]["logs"]) == 50
                assert len(node["data"]["metrics"]) == 25
                assert node["data"]["configuration"]["config_key_0"] == "config_value_0"
                assert node["data"]["logs"][0]["level"] == "INFO"
                assert node["data"]["metrics"]["metric_0"]["value"] == 0.0
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_node_data_in_hub_operations(self):
        """Test that node data is preserved in hub operations"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "hub-data-mesh")

                # Create hub node with data
                hub_data = {
                    "role": "hub",
                    "capacity": "high",
                    "datacenter": "primary"
                }

                hub_node_data = {
                    "name": "hub-node",
                    "addrs": ["192.168.1.10"],
                    "data": hub_data
                }

                response = await client.post(f"/mesh/{mesh['id']}/node", json=hub_node_data)
                hub_node = response.json()

                # Create spoke node with data
                spoke_data = {
                    "role": "spoke",
                    "service": "web-server",
                    "environment": "production"
                }

                spoke_node_data = {
                    "name": "spoke-node",
                    "addrs": ["192.168.1.11"],
                    "data": spoke_data
                }

                response = await client.post(f"/mesh/{mesh['id']}/node", json=spoke_node_data)
                spoke_node = response.json()

                # Create hub
                response = await client.post(
                    f"/mesh/{mesh['id']}/hub",
                    json={"node_id": hub_node["id"]}
                )
                assert response.status_code == 201
                hub = response.json()

                # Link spoke to hub
                response = await client.post(
                    f"/mesh/{mesh['id']}/link_to_hub",
                    json={"node_id": spoke_node["id"], "hub_id": hub["id"]}
                )
                assert response.status_code == 200

                # Verify data is preserved in hub operations
                response = await client.get(f"/mesh/{mesh['id']}/hub")
                assert response.status_code == 200

                hubs = response.json()
                assert len(hubs) == 1

                retrieved_hub = hubs[0]
                assert len(retrieved_hub["spokes"]) == 1

                # Check spoke data is preserved
                spoke = retrieved_hub["spokes"][0]
                assert spoke["data"]["role"] == "spoke"
                assert spoke["data"]["service"] == "web-server"
                assert spoke["data"]["environment"] == "production"
        finally:
            await db_manager.teardown()

    @pytest.mark.asyncio
    async def test_node_data_edge_cases(self):
        """Test edge cases for node data field"""
        db_manager = DatabaseManager()
        await db_manager.setup()

        try:
            async with ApiClient() as client:
                # Create mesh
                mesh = await create_test_mesh(client, "edge-case-mesh")

                # Test with special characters and unicode
                special_data = {
                    "unicode_text": "Hello 世界 🌍",
                    "special_chars": "!@#$%^&*()_+-=[]{}|;':\",./<>?",
                    "escaped_json": "{\"nested\": \"value\"}",
                    "numbers": {
                        "integer": 42,
                        "float": 3.14159,
                        "negative": -100,
                        "zero": 0
                    },
                    "booleans": {
                        "true_val": True,
                        "false_val": False
                    },
                    "null_value": None,
                    "empty_structures": {
                        "empty_object": {},
                        "empty_array": [],
                        "empty_string": ""
                    }
                }

                node_data = {
                    "name": "edge-case-node",
                    "addrs": ["192.168.1.7"],
                    "data": special_data
                }

                response = await client.post(f"/mesh/{mesh['id']}/node", json=node_data)
                assert response.status_code == 201

                node = response.json()
                assert node["data"]["unicode_text"] == "Hello 世界 🌍"
                assert node["data"]["special_chars"] == "!@#$%^&*()_+-=[]{}|;':\",./<>?"
                assert node["data"]["numbers"]["integer"] == 42
                assert node["data"]["numbers"]["float"] == 3.14159
                assert node["data"]["booleans"]["true_val"] == True
                assert node["data"]["booleans"]["false_val"] == False
                assert node["data"]["null_value"] is None
                assert node["data"]["empty_structures"]["empty_object"] == {}
                assert node["data"]["empty_structures"]["empty_array"] == []
                assert node["data"]["empty_structures"]["empty_string"] == ""
        finally:
            await db_manager.teardown()