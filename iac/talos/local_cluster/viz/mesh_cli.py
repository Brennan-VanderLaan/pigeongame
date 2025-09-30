#!/usr/bin/env python3
"""
Mesh Network CLI - kubectl-style interface for managing mesh networks

Usage:
    python mesh_cli.py <verb> <noun> [name] [options]

Examples:
    python mesh_cli.py get meshes
    python mesh_cli.py create mesh production-network
    python mesh_cli.py get nodes --mesh production-network
    python mesh_cli.py create node datacenter-1 --mesh production-network --addrs 10.1.0.1 --data '{"role":"hub"}'
    python mesh_cli.py create hub datacenter-1 --mesh production-network
    python mesh_cli.py apply link --node web-server --hub datacenter-1 --mesh production-network
"""

import argparse
import asyncio
import json
import sys
from typing import Dict, Any, Optional, List
from uuid import UUID
# import uvloop  # Optional performance improvement

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from database import AsyncSessionLocal, init_db
from mesh_manager import MeshNetworkManager
from models import MeshCreate, NodeCreate, HubCreate, LinkRequest, HubLinkRequest, Base
from logging_config import setup_cli_logging, get_component_logger


class MeshCLI:
    """Main CLI class for mesh network operations"""

    def __init__(self, database_url: Optional[str] = None):
        self.manager: Optional[MeshNetworkManager] = None
        self.logger = get_component_logger("cli")
        self.database_url = database_url
        self.custom_engine = None
        self.custom_session_local = None

    async def setup(self):
        """Initialize database connection"""
        self.logger.debug("Initializing database connection")

        if self.database_url:
            # Use custom database URL
            self.logger.debug(f"Using custom database: {self.database_url}")
            self.custom_engine = create_async_engine(self.database_url, echo=False)
            self.custom_session_local = sessionmaker(
                self.custom_engine, class_=AsyncSession, expire_on_commit=False
            )
            # Create tables for custom database
            async with self.custom_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        else:
            # Use default database
            await init_db()

        self.logger.debug("Database initialization complete")
        # We'll create the manager per command to ensure proper session handling

    def get_session_local(self):
        """Get the appropriate session local based on configuration"""
        if self.custom_session_local:
            return self.custom_session_local
        return AsyncSessionLocal

    async def cleanup(self):
        """Clean up resources"""
        if self.custom_engine:
            await self.custom_engine.dispose()

    def print_table(self, data: List[Dict[str, Any]], headers: List[str]):
        """Print data in table format"""
        if not data:
            print("No resources found.")
            return

        # Calculate column widths
        widths = {}
        for header in headers:
            widths[header] = len(header)
            for row in data:
                value = str(row.get(header, ''))
                widths[header] = max(widths[header], len(value))

        # Print header
        header_line = "  ".join(h.ljust(widths[h]) for h in headers)
        print(header_line)
        print("-" * len(header_line))

        # Print rows
        for row in data:
            row_line = "  ".join(str(row.get(h, '')).ljust(widths[h]) for h in headers)
            print(row_line)

    def print_json(self, data: Any):
        """Print data in JSON format"""
        print(json.dumps(data, indent=2, default=str))

    def error_exit(self, message: str, code: int = 1):
        """Print error and exit with code"""
        self.logger.error(f"CLI error (exit code {code}): {message}")
        print(f"Error: {message}", file=sys.stderr)
        sys.exit(code)

    async def find_mesh_by_name(self, name: str) -> Optional[UUID]:
        """Find mesh ID by name"""
        self.logger.debug(f"Looking up mesh by name: {name}")
        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)
            meshes = await manager.meshes.list_meshes()
            for mesh in meshes:
                if mesh.name == name:
                    self.logger.debug(f"Found mesh {name} with ID {mesh.id}")
                    return mesh.id
        self.logger.debug(f"Mesh {name} not found")
        return None

    async def find_node_by_name(self, mesh_id: UUID, name: str) -> Optional[UUID]:
        """Find node ID by name within a mesh"""
        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)
            mesh = await manager.meshes.get_mesh(mesh_id)
            if mesh:
                for node in mesh.nodes:
                    if node.name == name:
                        return node.id
        return None

    async def find_hub_by_name(self, mesh_id: UUID, name: str) -> Optional[UUID]:
        """Find hub ID by name within a mesh"""
        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)
            hubs = await manager.hubs.get_hubs(mesh_id)
            for hub in hubs:
                if hub.name == name:
                    return hub.id
        return None

    # Node commands
    async def get_nodes(self, args):
        """List nodes in a mesh"""
        mesh_id = await self.find_mesh_by_name(args.mesh)
        if not mesh_id:
            self.error_exit(f"Mesh '{args.mesh}' not found", 404)

        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)
            mesh = await manager.meshes.get_mesh(mesh_id)

            if args.output == 'json':
                self.print_json([{
                    'name': node.name,
                    'id': str(node.id),
                    'addrs': node.addrs,
                    'data': node.data
                } for node in mesh.nodes])
            else:
                data = [{
                    'NAME': node.name,
                    'ADDRESSES': ', '.join(node.addrs),
                    'DATA': json.dumps(node.data) if node.data else '',
                    'ID': str(node.id)[:8] + '...'
                } for node in mesh.nodes]
                self.print_table(data, ['NAME', 'ADDRESSES', 'DATA', 'ID'])

    async def get_node(self, args):
        """Get specific node details"""
        mesh_id = await self.find_mesh_by_name(args.mesh)
        if not mesh_id:
            self.error_exit(f"Mesh '{args.mesh}' not found", 404)

        node_id = await self.find_node_by_name(mesh_id, args.name)
        if not node_id:
            self.error_exit(f"Node '{args.name}' not found in mesh '{args.mesh}'", 404)

        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)
            mesh = await manager.meshes.get_mesh(mesh_id)
            node = next((n for n in mesh.nodes if n.id == node_id), None)

            if args.output == 'json':
                self.print_json({
                    'name': node.name,
                    'id': str(node.id),
                    'addrs': node.addrs,
                    'data': node.data
                })
            else:
                print(f"Name: {node.name}")
                print(f"ID: {node.id}")
                print(f"Addresses: {', '.join(node.addrs)}")
                if node.data:
                    print(f"Data: {json.dumps(node.data, indent=2)}")

    async def create_node(self, args):
        """Create a new node in a mesh"""
        mesh_id = await self.find_mesh_by_name(args.mesh)
        if not mesh_id:
            self.error_exit(f"Mesh '{args.mesh}' not found", 404)

        # Check if node already exists
        existing_id = await self.find_node_by_name(mesh_id, args.name)
        if existing_id:
            self.error_exit(f"Node '{args.name}' already exists in mesh '{args.mesh}'", 409)

        # Parse addresses
        addrs = [addr.strip() for addr in args.addrs.split(',')]

        # Parse JSON data
        data = {}
        if args.data:
            try:
                data = json.loads(args.data)
            except json.JSONDecodeError as e:
                self.error_exit(f"Invalid JSON in --data: {e}", 400)

        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)
            node_create = NodeCreate(name=args.name, addrs=addrs, data=data)
            node = await manager.nodes.add_node_to_mesh(mesh_id, node_create)

            if args.output == 'json':
                self.print_json({
                    'name': node.name,
                    'id': str(node.id),
                    'addrs': node.addrs,
                    'data': node.data
                })
            else:
                print(f"Node '{node.name}' created successfully in mesh '{args.mesh}'")

    async def delete_node(self, args):
        """Delete a node from a mesh"""
        mesh_id = await self.find_mesh_by_name(args.mesh)
        if not mesh_id:
            self.error_exit(f"Mesh '{args.mesh}' not found", 404)

        node_id = await self.find_node_by_name(mesh_id, args.name)
        if not node_id:
            self.error_exit(f"Node '{args.name}' not found in mesh '{args.mesh}'", 404)

        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)
            success = await manager.nodes.remove_node_from_mesh(mesh_id, node_id)

            if success:
                if args.output != 'json':
                    print(f"Node '{args.name}' deleted successfully from mesh '{args.mesh}'")
            else:
                self.error_exit(f"Failed to delete node '{args.name}'", 500)

    async def describe_node(self, args):
        """Describe a node in detail"""
        await self.get_node(args)  # Same as get node for now

    # Hub commands
    async def get_hubs(self, args):
        """List hubs in a mesh"""
        mesh_id = await self.find_mesh_by_name(args.mesh)
        if not mesh_id:
            self.error_exit(f"Mesh '{args.mesh}' not found", 404)

        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)
            hubs = await manager.hubs.get_hubs(mesh_id)

            if args.output == 'json':
                self.print_json([{
                    'name': hub.name,
                    'id': str(hub.id),
                    'node_id': str(hub.node_id),
                    'spokes': len(hub.spokes),
                    'connected_hubs': len(hub.connected_hubs)
                } for hub in hubs])
            else:
                data = [{
                    'NAME': hub.name,
                    'SPOKES': len(hub.spokes),
                    'CONNECTIONS': len(hub.connected_hubs),
                    'NODE_ID': str(hub.node_id)[:8] + '...',
                    'ID': str(hub.id)[:8] + '...'
                } for hub in hubs]
                self.print_table(data, ['NAME', 'SPOKES', 'CONNECTIONS', 'NODE_ID', 'ID'])

    async def get_hub(self, args):
        """Get specific hub details"""
        mesh_id = await self.find_mesh_by_name(args.mesh)
        if not mesh_id:
            self.error_exit(f"Mesh '{args.mesh}' not found", 404)

        hub_id = await self.find_hub_by_name(mesh_id, args.name)
        if not hub_id:
            self.error_exit(f"Hub '{args.name}' not found in mesh '{args.mesh}'", 404)

        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)
            hubs = await manager.hubs.get_hubs(mesh_id)
            hub = next((h for h in hubs if h.id == hub_id), None)

            if args.output == 'json':
                self.print_json({
                    'name': hub.name,
                    'id': str(hub.id),
                    'node_id': str(hub.node_id),
                    'spokes': [{'name': s.name, 'id': str(s.id)} for s in hub.spokes],
                    'connected_hubs': [{'name': ch.name, 'id': str(ch.id)} for ch in hub.connected_hubs]
                })
            else:
                print(f"Name: {hub.name}")
                print(f"ID: {hub.id}")
                print(f"Node ID: {hub.node_id}")
                print(f"Spokes ({len(hub.spokes)}):")
                for spoke in hub.spokes:
                    print(f"  - {spoke.name}")
                print(f"Connected Hubs ({len(hub.connected_hubs)}):")
                for ch in hub.connected_hubs:
                    print(f"  - {ch.name}")

    async def create_hub(self, args):
        """Create a hub from an existing node"""
        mesh_id = await self.find_mesh_by_name(args.mesh)
        if not mesh_id:
            self.error_exit(f"Mesh '{args.mesh}' not found", 404)

        node_id = await self.find_node_by_name(mesh_id, args.name)
        if not node_id:
            self.error_exit(f"Node '{args.name}' not found in mesh '{args.mesh}'", 404)

        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)
            hub_create = HubCreate(node_id=node_id)
            result = await manager.hubs.create_hub(mesh_id, hub_create)

            if "error" in result:
                self.error_exit(result["error"], result["status_code"])

            hub = result["hub"]
            if args.output == 'json':
                self.print_json({
                    'name': hub.name,
                    'id': str(hub.id),
                    'node_id': str(hub.node_id)
                })
            else:
                print(f"Hub '{hub.name}' created successfully from node '{args.name}' in mesh '{args.mesh}'")

    async def delete_hub(self, args):
        """Delete a hub"""
        mesh_id = await self.find_mesh_by_name(args.mesh)
        if not mesh_id:
            self.error_exit(f"Mesh '{args.mesh}' not found", 404)

        hub_id = await self.find_hub_by_name(mesh_id, args.name)
        if not hub_id:
            self.error_exit(f"Hub '{args.name}' not found in mesh '{args.mesh}'", 404)

        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)
            success = await manager.hubs.remove_hub(mesh_id, hub_id)

            if success:
                if args.output != 'json':
                    print(f"Hub '{args.name}' deleted successfully from mesh '{args.mesh}'")
            else:
                self.error_exit(f"Failed to delete hub '{args.name}'", 500)

    # Link management commands
    async def apply_link(self, args):
        """Apply a node-to-hub link"""
        mesh_id = await self.find_mesh_by_name(args.mesh)
        if not mesh_id:
            self.error_exit(f"Mesh '{args.mesh}' not found", 404)

        node_id = await self.find_node_by_name(mesh_id, args.node)
        if not node_id:
            self.error_exit(f"Node '{args.node}' not found in mesh '{args.mesh}'", 404)

        hub_id = await self.find_hub_by_name(mesh_id, args.hub)
        if not hub_id:
            self.error_exit(f"Hub '{args.hub}' not found in mesh '{args.mesh}'", 404)

        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)
            link_request = LinkRequest(node_id=node_id, hub_id=hub_id)
            result = await manager.links.link_node_to_hub(mesh_id, link_request)

            if "error" in result:
                self.error_exit(result["error"], result["status_code"])

            if args.output == 'json':
                self.print_json(result)
            else:
                print(f"Node '{args.node}' linked to hub '{args.hub}' in mesh '{args.mesh}'")

    async def delete_link(self, args):
        """Delete a node-to-hub link"""
        mesh_id = await self.find_mesh_by_name(args.mesh)
        if not mesh_id:
            self.error_exit(f"Mesh '{args.mesh}' not found", 404)

        node_id = await self.find_node_by_name(mesh_id, args.node)
        if not node_id:
            self.error_exit(f"Node '{args.node}' not found in mesh '{args.mesh}'", 404)

        hub_id = await self.find_hub_by_name(mesh_id, args.hub)
        if not hub_id:
            self.error_exit(f"Hub '{args.hub}' not found in mesh '{args.mesh}'", 404)

        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)
            link_request = LinkRequest(node_id=node_id, hub_id=hub_id)
            result = await manager.links.unlink_node_from_hub(mesh_id, link_request)

            if "error" in result:
                self.error_exit(result["error"], result["status_code"])

            if args.output == 'json':
                self.print_json(result)
            else:
                print(f"Node '{args.node}' unlinked from hub '{args.hub}' in mesh '{args.mesh}'")

    async def apply_hub_link(self, args):
        """Apply a hub-to-hub connection"""
        mesh_id = await self.find_mesh_by_name(args.mesh)
        if not mesh_id:
            self.error_exit(f"Mesh '{args.mesh}' not found", 404)

        source_hub_id = await self.find_hub_by_name(mesh_id, args.source_hub)
        if not source_hub_id:
            self.error_exit(f"Source hub '{args.source_hub}' not found in mesh '{args.mesh}'", 404)

        target_hub_id = await self.find_hub_by_name(mesh_id, args.target_hub)
        if not target_hub_id:
            self.error_exit(f"Target hub '{args.target_hub}' not found in mesh '{args.mesh}'", 404)

        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)
            hub_link_request = HubLinkRequest(source_hub_id=source_hub_id, target_hub_id=target_hub_id)
            result = await manager.links.connect_hubs(mesh_id, hub_link_request)

            if "error" in result:
                self.error_exit(result["error"], result["status_code"])

            if args.output == 'json':
                self.print_json(result)
            else:
                print(f"Hub '{args.source_hub}' connected to hub '{args.target_hub}' in mesh '{args.mesh}'")

    async def delete_hub_link(self, args):
        """Delete a hub-to-hub connection"""
        mesh_id = await self.find_mesh_by_name(args.mesh)
        if not mesh_id:
            self.error_exit(f"Mesh '{args.mesh}' not found", 404)

        source_hub_id = await self.find_hub_by_name(mesh_id, args.source_hub)
        if not source_hub_id:
            self.error_exit(f"Source hub '{args.source_hub}' not found in mesh '{args.mesh}'", 404)

        target_hub_id = await self.find_hub_by_name(mesh_id, args.target_hub)
        if not target_hub_id:
            self.error_exit(f"Target hub '{args.target_hub}' not found in mesh '{args.mesh}'", 404)

        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)
            hub_link_request = HubLinkRequest(source_hub_id=source_hub_id, target_hub_id=target_hub_id)
            result = await manager.links.disconnect_hubs(mesh_id, hub_link_request)

            if "error" in result:
                self.error_exit(result["error"], result["status_code"])

            if args.output == 'json':
                self.print_json(result)
            else:
                print(f"Hub '{args.source_hub}' disconnected from hub '{args.target_hub}' in mesh '{args.mesh}'")

    # Mesh commands
    async def get_meshes(self, args):
        """List all meshes"""
        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)
            meshes = await manager.meshes.list_meshes()

            if args.output == 'json':
                self.print_json([{
                    'name': mesh.name,
                    'id': str(mesh.id),
                    'nodes': len(mesh.nodes),
                    'hubs': len(mesh.hubs)
                } for mesh in meshes])
            else:
                data = [{
                    'NAME': mesh.name,
                    'NODES': len(mesh.nodes),
                    'HUBS': len(mesh.hubs),
                    'ID': str(mesh.id)[:8] + '...'
                } for mesh in meshes]
                self.print_table(data, ['NAME', 'NODES', 'HUBS', 'ID'])

    async def get_mesh(self, args):
        """Get specific mesh details"""
        mesh_id = await self.find_mesh_by_name(args.name)
        if not mesh_id:
            self.error_exit(f"Mesh '{args.name}' not found", 404)

        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)
            mesh = await manager.meshes.get_mesh(mesh_id)

            if args.output == 'json':
                self.print_json({
                    'name': mesh.name,
                    'id': str(mesh.id),
                    'nodes': [{'name': n.name, 'id': str(n.id), 'addrs': n.addrs, 'data': n.data} for n in mesh.nodes],
                    'hubs': [{'name': h.name, 'id': str(h.id), 'node_id': str(h.node_id), 'spokes': len(h.spokes)} for h in mesh.hubs]
                })
            else:
                print(f"Name: {mesh.name}")
                print(f"ID: {mesh.id}")
                print(f"Nodes: {len(mesh.nodes)}")
                print(f"Hubs: {len(mesh.hubs)}")

    async def create_mesh(self, args):
        """Create a new mesh"""
        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)

            # Check if mesh already exists
            existing_id = await self.find_mesh_by_name(args.name)
            if existing_id:
                self.error_exit(f"Mesh '{args.name}' already exists", 409)

            mesh_create = MeshCreate(name=args.name)
            mesh = await manager.meshes.create_mesh(mesh_create)

            if args.output == 'json':
                self.print_json({'name': mesh.name, 'id': str(mesh.id)})
            else:
                print(f"Mesh '{mesh.name}' created successfully")

    async def delete_mesh(self, args):
        """Delete a mesh"""
        mesh_id = await self.find_mesh_by_name(args.name)
        if not mesh_id:
            self.error_exit(f"Mesh '{args.name}' not found", 404)

        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)
            success = await manager.meshes.delete_mesh(mesh_id)

            if success:
                if args.output != 'json':
                    print(f"Mesh '{args.name}' deleted successfully")
            else:
                self.error_exit(f"Failed to delete mesh '{args.name}'", 500)

    async def describe_mesh(self, args):
        """Describe a mesh in detail"""
        mesh_id = await self.find_mesh_by_name(args.name)
        if not mesh_id:
            self.error_exit(f"Mesh '{args.name}' not found", 404)

        async with self.get_session_local()() as db:
            manager = MeshNetworkManager(db)
            mesh = await manager.meshes.get_mesh(mesh_id)

            if args.output == 'json':
                self.print_json({
                    'name': mesh.name,
                    'id': str(mesh.id),
                    'nodes': [{'name': n.name, 'id': str(n.id), 'addrs': n.addrs, 'data': n.data} for n in mesh.nodes],
                    'hubs': [{
                        'name': h.name,
                        'id': str(h.id),
                        'node_id': str(h.node_id),
                        'spokes': [{'name': s.name, 'id': str(s.id)} for s in h.spokes],
                        'connected_hubs': [{'name': ch.name, 'id': str(ch.id)} for ch in h.connected_hubs]
                    } for h in mesh.hubs]
                })
            else:
                print(f"Name: {mesh.name}")
                print(f"ID: {mesh.id}")
                print(f"\nNodes ({len(mesh.nodes)}):")
                for node in mesh.nodes:
                    print(f"  - {node.name} ({', '.join(node.addrs)})")
                    if node.data:
                        print(f"    Data: {json.dumps(node.data)}")

                print(f"\nHubs ({len(mesh.hubs)}):")
                for hub in mesh.hubs:
                    print(f"  - {hub.name} ({len(hub.spokes)} spokes)")
                    for spoke in hub.spokes:
                        print(f"    └─ {spoke.name}")
                    if hub.connected_hubs:
                        print(f"    Connected to: {', '.join(ch.name for ch in hub.connected_hubs)}")

def create_parser():
    """Create the argument parser with kubectl-style commands"""
    parser = argparse.ArgumentParser(
        description="Mesh Network CLI - kubectl-style interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s get meshes
  %(prog)s --output json get meshes
  %(prog)s create mesh production-network
  %(prog)s get mesh production-network
  %(prog)s -v get nodes --mesh production-network
  %(prog)s --quiet create node web-server --mesh production-network --addrs 192.168.1.10
  %(prog)s apply link --node web-server --hub datacenter-1 --mesh production-network
        """
    )

    parser.add_argument(
        '--output', '-o',
        choices=['table', 'json'],
        default='table',
        help='Output format (default: table)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='count',
        default=0,
        help='Increase verbosity (-v for debug, -vv for debug + SQL logs)'
    )

    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress all logs except errors'
    )

    parser.add_argument(
        '--database', '--db',
        type=str,
        help='Database URL (default: sqlite+aiosqlite:///./mesh.db)'
    )

    subparsers = parser.add_subparsers(dest='verb', help='Available verbs')

    # GET commands
    get_parser = subparsers.add_parser('get', help='Get resources')
    get_subparsers = get_parser.add_subparsers(dest='noun', help='Resource types')

    # get meshes
    get_meshes_parser = get_subparsers.add_parser('meshes', help='List all meshes')

    # get mesh <name>
    get_mesh_parser = get_subparsers.add_parser('mesh', help='Get specific mesh')
    get_mesh_parser.add_argument('name', help='Mesh name')

    # get nodes --mesh <mesh>
    get_nodes_parser = get_subparsers.add_parser('nodes', help='List nodes in a mesh')
    get_nodes_parser.add_argument('--mesh', required=True, help='Mesh name')

    # get node <name> --mesh <mesh>
    get_node_parser = get_subparsers.add_parser('node', help='Get specific node')
    get_node_parser.add_argument('name', help='Node name')
    get_node_parser.add_argument('--mesh', required=True, help='Mesh name')

    # get hubs --mesh <mesh>
    get_hubs_parser = get_subparsers.add_parser('hubs', help='List hubs in a mesh')
    get_hubs_parser.add_argument('--mesh', required=True, help='Mesh name')

    # get hub <name> --mesh <mesh>
    get_hub_parser = get_subparsers.add_parser('hub', help='Get specific hub')
    get_hub_parser.add_argument('name', help='Hub name')
    get_hub_parser.add_argument('--mesh', required=True, help='Mesh name')

    # CREATE commands
    create_parser = subparsers.add_parser('create', help='Create resources')
    create_subparsers = create_parser.add_subparsers(dest='noun', help='Resource types')

    # create mesh <name>
    create_mesh_parser = create_subparsers.add_parser('mesh', help='Create a mesh')
    create_mesh_parser.add_argument('name', help='Mesh name')

    # create node <name> --mesh <mesh> --addrs <addrs> [--data <json>]
    create_node_parser = create_subparsers.add_parser('node', help='Create a node')
    create_node_parser.add_argument('name', help='Node name')
    create_node_parser.add_argument('--mesh', required=True, help='Mesh name')
    create_node_parser.add_argument('--addrs', required=True, help='Comma-separated addresses')
    create_node_parser.add_argument('--data', help='JSON data for the node')

    # create hub <name> --mesh <mesh>
    create_hub_parser = create_subparsers.add_parser('hub', help='Create a hub from existing node')
    create_hub_parser.add_argument('name', help='Node name to convert to hub')
    create_hub_parser.add_argument('--mesh', required=True, help='Mesh name')

    # DELETE commands
    delete_parser = subparsers.add_parser('delete', help='Delete resources')
    delete_subparsers = delete_parser.add_subparsers(dest='noun', help='Resource types')

    # delete mesh <name>
    delete_mesh_parser = delete_subparsers.add_parser('mesh', help='Delete a mesh')
    delete_mesh_parser.add_argument('name', help='Mesh name')

    # delete node <name> --mesh <mesh>
    delete_node_parser = delete_subparsers.add_parser('node', help='Delete a node')
    delete_node_parser.add_argument('name', help='Node name')
    delete_node_parser.add_argument('--mesh', required=True, help='Mesh name')

    # delete hub <name> --mesh <mesh>
    delete_hub_parser = delete_subparsers.add_parser('hub', help='Delete a hub')
    delete_hub_parser.add_argument('name', help='Hub name')
    delete_hub_parser.add_argument('--mesh', required=True, help='Mesh name')

    # DESCRIBE commands
    describe_parser = subparsers.add_parser('describe', help='Describe resources in detail')
    describe_subparsers = describe_parser.add_subparsers(dest='noun', help='Resource types')

    # describe mesh <name>
    describe_mesh_parser = describe_subparsers.add_parser('mesh', help='Describe a mesh')
    describe_mesh_parser.add_argument('name', help='Mesh name')

    # describe node <name> --mesh <mesh>
    describe_node_parser = describe_subparsers.add_parser('node', help='Describe a node')
    describe_node_parser.add_argument('name', help='Node name')
    describe_node_parser.add_argument('--mesh', required=True, help='Mesh name')

    # describe hub <name> --mesh <mesh>
    describe_hub_parser = describe_subparsers.add_parser('hub', help='Describe a hub')
    describe_hub_parser.add_argument('name', help='Hub name')
    describe_hub_parser.add_argument('--mesh', required=True, help='Mesh name')

    # APPLY commands (kubectl-style for applying links)
    apply_parser = subparsers.add_parser('apply', help='Apply configurations')
    apply_subparsers = apply_parser.add_subparsers(dest='noun', help='Configuration types')

    # apply link --node <node> --hub <hub> --mesh <mesh>
    apply_link_parser = apply_subparsers.add_parser('link', help='Apply node-to-hub link')
    apply_link_parser.add_argument('--node', required=True, help='Node name')
    apply_link_parser.add_argument('--hub', required=True, help='Hub name')
    apply_link_parser.add_argument('--mesh', required=True, help='Mesh name')

    # apply hub-link --source-hub <hub1> --target-hub <hub2> --mesh <mesh>
    apply_hub_link_parser = apply_subparsers.add_parser('hub-link', help='Apply hub-to-hub connection')
    apply_hub_link_parser.add_argument('--source-hub', required=True, help='Source hub name')
    apply_hub_link_parser.add_argument('--target-hub', required=True, help='Target hub name')
    apply_hub_link_parser.add_argument('--mesh', required=True, help='Mesh name')

    # Additional DELETE commands for links
    # delete link --node <node> --hub <hub> --mesh <mesh>
    delete_link_parser = delete_subparsers.add_parser('link', help='Delete node-to-hub link')
    delete_link_parser.add_argument('--node', required=True, help='Node name')
    delete_link_parser.add_argument('--hub', required=True, help='Hub name')
    delete_link_parser.add_argument('--mesh', required=True, help='Mesh name')

    # delete hub-link --source-hub <hub1> --target-hub <hub2> --mesh <mesh>
    delete_hub_link_parser = delete_subparsers.add_parser('hub-link', help='Delete hub-to-hub connection')
    delete_hub_link_parser.add_argument('--source-hub', required=True, help='Source hub name')
    delete_hub_link_parser.add_argument('--target-hub', required=True, help='Target hub name')
    delete_hub_link_parser.add_argument('--mesh', required=True, help='Mesh name')

    return parser

async def main():
    """Main CLI entry point"""
    # Use uvloop for better async performance (optional)
    # uvloop.install()

    parser = create_parser()
    args = parser.parse_args()

    # Setup logging based on CLI arguments
    setup_cli_logging(verbose=args.verbose, quiet=args.quiet)

    if not args.verb:
        parser.print_help()
        sys.exit(1)

    cli = MeshCLI(database_url=args.database)
    await cli.setup()

    try:
        # Route to appropriate command handler
        if args.verb == 'get':
            if args.noun == 'meshes':
                await cli.get_meshes(args)
            elif args.noun == 'mesh':
                await cli.get_mesh(args)
            elif args.noun == 'nodes':
                await cli.get_nodes(args)
            elif args.noun == 'node':
                await cli.get_node(args)
            elif args.noun == 'hubs':
                await cli.get_hubs(args)
            elif args.noun == 'hub':
                await cli.get_hub(args)
            else:
                parser.print_help()
                sys.exit(1)
        elif args.verb == 'create':
            if args.noun == 'mesh':
                await cli.create_mesh(args)
            elif args.noun == 'node':
                await cli.create_node(args)
            elif args.noun == 'hub':
                await cli.create_hub(args)
            else:
                parser.print_help()
                sys.exit(1)
        elif args.verb == 'delete':
            if args.noun == 'mesh':
                await cli.delete_mesh(args)
            elif args.noun == 'node':
                await cli.delete_node(args)
            elif args.noun == 'hub':
                await cli.delete_hub(args)
            elif args.noun == 'link':
                await cli.delete_link(args)
            elif args.noun == 'hub-link':
                await cli.delete_hub_link(args)
            else:
                parser.print_help()
                sys.exit(1)
        elif args.verb == 'describe':
            if args.noun == 'mesh':
                await cli.describe_mesh(args)
            elif args.noun == 'node':
                await cli.describe_node(args)
            elif args.noun == 'hub':
                await cli.get_hub(args)  # Same as get hub for now
            else:
                parser.print_help()
                sys.exit(1)
        elif args.verb == 'apply':
            if args.noun == 'link':
                await cli.apply_link(args)
            elif args.noun == 'hub-link':
                await cli.apply_hub_link(args)
            else:
                parser.print_help()
                sys.exit(1)
        else:
            parser.print_help()
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await cli.cleanup()

if __name__ == '__main__':
    asyncio.run(main())