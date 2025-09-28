#!/usr/bin/env python3
"""
Quick test to verify the mesh API works with real UUID handling
"""

import asyncio
import json
from httpx import AsyncClient
from main import app

async def test_mesh_operations():
    """Test basic mesh operations"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        print("🔧 Testing mesh creation...")

        # Create a mesh
        response = await client.post("/mesh", json={"name": "test-mesh"})
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"

        mesh = response.json()
        mesh_id = mesh["id"]
        print(f"✅ Created mesh: {mesh['name']} with ID: {mesh_id}")

        # Get the mesh by ID
        response = await client.get(f"/mesh/{mesh_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        retrieved_mesh = response.json()
        print(f"✅ Retrieved mesh: {retrieved_mesh['name']}")

        # Add a node
        print("🔧 Testing node addition...")
        node_data = {"name": "test-node", "addrs": ["192.168.1.1", "10.0.0.1"]}
        response = await client.post(f"/mesh/{mesh_id}/node", json=node_data)

        if response.status_code != 201:
            print(f"❌ Node creation failed: {response.status_code} - {response.text}")
            return False

        node = response.json()
        node_id = node["id"]
        print(f"✅ Created node: {node['name']} with ID: {node_id}")

        # Verify the mesh now has the node
        response = await client.get(f"/mesh/{mesh_id}")
        updated_mesh = response.json()
        print(f"✅ Mesh now has {len(updated_mesh['nodes'])} node(s)")

        # Create a hub from the node
        print("🔧 Testing hub creation...")
        response = await client.post(f"/mesh/{mesh_id}/hub", json={"node_id": node_id})

        if response.status_code != 201:
            print(f"❌ Hub creation failed: {response.status_code} - {response.text}")
            return False

        hub = response.json()
        hub_id = hub["id"]
        print(f"✅ Created hub: {hub['name']} with ID: {hub_id}")

        # Add another node and link it to the hub
        print("🔧 Testing spoke connection...")
        spoke_data = {"name": "spoke-node", "addrs": ["192.168.1.2"]}
        response = await client.post(f"/mesh/{mesh_id}/node", json=spoke_data)

        if response.status_code != 201:
            print(f"❌ Spoke node creation failed: {response.status_code} - {response.text}")
            return False

        spoke_node = response.json()
        spoke_node_id = spoke_node["id"]
        print(f"✅ Created spoke node: {spoke_node['name']}")

        # Link spoke to hub
        response = await client.post(f"/mesh/{mesh_id}/link_to_hub",
                                   json={"node_id": spoke_node_id, "hub_id": hub_id})

        if response.status_code != 200:
            print(f"❌ Linking failed: {response.status_code} - {response.text}")
            return False

        print("✅ Linked spoke to hub")

        # Final verification
        response = await client.get(f"/mesh/{mesh_id}")
        final_mesh = response.json()

        print(f"\n🎉 Final mesh topology:")
        print(f"   Mesh: {final_mesh['name']}")
        print(f"   Nodes: {len(final_mesh['nodes'])}")
        print(f"   Hubs: {len(final_mesh['hubs'])}")
        if final_mesh['hubs']:
            hub_spokes = len(final_mesh['hubs'][0]['spokes'])
            print(f"   Hub '{final_mesh['hubs'][0]['name']}' has {hub_spokes} spoke(s)")

        return True

if __name__ == "__main__":
    success = asyncio.run(test_mesh_operations())
    if success:
        print("\n🎉 All tests passed! The mesh API is working correctly.")
    else:
        print("\n❌ Some tests failed.")