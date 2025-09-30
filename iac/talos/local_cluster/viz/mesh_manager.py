"""
Common mesh management library for both web UI and CLI interfaces.

This module extracts the core mesh, node, and hub management logic from the FastAPI endpoints
to enable reuse across different interfaces (web API, CLI, etc.) while maintaining the same
business logic and data access patterns.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models import (
    MeshDB, NodeDB, HubDB,
    MeshCreate, MeshResponse,
    NodeCreate, NodeResponse,
    HubCreate, HubResponse, HubBasicInfo,
    LinkRequest, HubLinkRequest
)
from utils import DatabaseHelper, QueryHelper


class MeshManager:
    """Core mesh management operations"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_mesh(self, mesh_create: MeshCreate) -> MeshResponse:
        """Create a new mesh network"""
        mesh_data = DatabaseHelper.create_mesh_data(mesh_create.name)
        db_mesh = MeshDB(**mesh_data)
        self.db.add(db_mesh)
        await self.db.commit()
        await self.db.refresh(db_mesh)
        return MeshResponse(id=db_mesh.id, name=db_mesh.name, nodes=[], hubs=[])

    async def get_mesh(self, mesh_id: UUID) -> Optional[MeshResponse]:
        """Get a specific mesh network by ID"""
        conditions = QueryHelper.mesh_by_id(mesh_id)
        result = await self.db.execute(
            select(MeshDB).where(*conditions).options(
                selectinload(MeshDB.nodes),
                selectinload(MeshDB.hubs).selectinload(HubDB.spokes),
                selectinload(MeshDB.hubs).selectinload(HubDB.connected_hubs)
            )
        )
        mesh = result.scalar_one_or_none()

        if not mesh:
            return None

        nodes = [NodeResponse(
            id=node.id,
            name=node.name,
            addrs=json.loads(node.addrs),
            data=json.loads(node.data) if node.data else {}
        ) for node in mesh.nodes]

        hubs = [HubResponse(
            id=hub.id,
            name=hub.name,
            node_id=hub.node_id,
            spokes=[NodeResponse(
                id=spoke.id,
                name=spoke.name,
                addrs=json.loads(spoke.addrs),
                data=json.loads(spoke.data) if spoke.data else {}
            ) for spoke in hub.spokes],
            connected_hubs=[HubBasicInfo(
                id=connected_hub.id,
                name=connected_hub.name,
                node_id=connected_hub.node_id
            ) for connected_hub in QueryHelper.get_all_connected_hubs(hub)]
        ) for hub in mesh.hubs]

        return MeshResponse(
            id=mesh.id,
            name=mesh.name,
            nodes=nodes,
            hubs=hubs
        )

    async def list_meshes(self) -> List[MeshResponse]:
        """List all mesh networks with their nodes and hubs"""
        result = await self.db.execute(
            select(MeshDB).options(
                selectinload(MeshDB.nodes),
                selectinload(MeshDB.hubs).selectinload(HubDB.spokes),
                selectinload(MeshDB.hubs).selectinload(HubDB.connected_hubs)
            )
        )
        meshes = result.scalars().all()

        response = []
        for mesh in meshes:
            nodes = [NodeResponse(
                id=node.id,
                name=node.name,
                addrs=json.loads(node.addrs),
                data=json.loads(node.data) if node.data else {}
            ) for node in mesh.nodes]

            hubs = [HubResponse(
                id=hub.id,
                name=hub.name,
                node_id=hub.node_id,
                spokes=[NodeResponse(
                    id=spoke.id,
                    name=spoke.name,
                    addrs=json.loads(spoke.addrs),
                    data=json.loads(spoke.data) if spoke.data else {}
                ) for spoke in hub.spokes],
                connected_hubs=[HubBasicInfo(
                    id=connected_hub.id,
                    name=connected_hub.name,
                    node_id=connected_hub.node_id
                ) for connected_hub in QueryHelper.get_all_connected_hubs(hub)]
            ) for hub in mesh.hubs]

            response.append(MeshResponse(
                id=mesh.id,
                name=mesh.name,
                nodes=nodes,
                hubs=hubs
            ))

        return response

    async def delete_mesh(self, mesh_id: UUID) -> bool:
        """Delete a mesh network and all associated nodes and hubs"""
        conditions = QueryHelper.mesh_by_id(mesh_id)
        result = await self.db.execute(select(MeshDB).where(*conditions))
        mesh = result.scalar_one_or_none()

        if not mesh:
            return False

        await self.db.delete(mesh)
        await self.db.commit()
        return True


class NodeManager:
    """Core node management operations"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def add_node_to_mesh(self, mesh_id: UUID, node_create: NodeCreate) -> Optional[NodeResponse]:
        """Add a node to the mesh"""
        # Check if mesh exists
        conditions = QueryHelper.mesh_by_id(mesh_id)
        result = await self.db.execute(select(MeshDB).where(*conditions))
        mesh = result.scalar_one_or_none()

        if not mesh:
            return None

        node_data = DatabaseHelper.create_node_data(
            name=node_create.name,
            addrs_json=json.dumps(node_create.addrs),
            data_json=json.dumps(node_create.data),
            mesh_id=mesh_id
        )
        db_node = NodeDB(**node_data)
        self.db.add(db_node)
        await self.db.commit()
        await self.db.refresh(db_node)

        return NodeResponse(
            id=db_node.id,
            name=db_node.name,
            addrs=json.loads(db_node.addrs),
            data=json.loads(db_node.data) if db_node.data else {}
        )

    async def remove_node_from_mesh(self, mesh_id: UUID, node_id: UUID) -> bool:
        """Remove a node from the mesh"""
        conditions = QueryHelper.node_by_id_and_mesh(node_id, mesh_id)
        result = await self.db.execute(select(NodeDB).where(*conditions))
        node = result.scalar_one_or_none()

        if not node:
            return False

        await self.db.delete(node)
        await self.db.commit()
        return True


class HubManager:
    """Core hub management operations"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_hub(self, mesh_id: UUID, hub_create: HubCreate) -> Optional[Dict[str, Any]]:
        """Create a hub from an existing node"""
        # Check if mesh exists
        mesh_conditions = QueryHelper.mesh_by_id(mesh_id)
        result = await self.db.execute(select(MeshDB).where(*mesh_conditions))
        mesh = result.scalar_one_or_none()

        if not mesh:
            return {"error": "Mesh not found", "status_code": 404}

        # Check if node exists in this mesh
        node_conditions = QueryHelper.node_by_id_and_mesh(hub_create.node_id, mesh_id)
        result = await self.db.execute(select(NodeDB).where(*node_conditions))
        node = result.scalar_one_or_none()

        if not node:
            return {"error": "Node not found in this mesh", "status_code": 404}

        # Check if hub already exists for this node
        hub_conditions = QueryHelper.hub_by_node_and_mesh(hub_create.node_id, mesh_id)
        result = await self.db.execute(select(HubDB).where(*hub_conditions))
        existing_hub = result.scalar_one_or_none()

        if existing_hub:
            return {"error": "Node is already a hub", "status_code": 400}

        # If this node is currently linked as a spoke to any hubs, unlink it first
        # A node cannot be both a hub and a spoke
        all_hubs_conditions = QueryHelper.hubs_by_mesh(mesh_id)
        result = await self.db.execute(
            select(HubDB).where(*all_hubs_conditions).options(
                selectinload(HubDB.spokes)
            )
        )
        all_hubs = result.scalars().all()

        for existing_hub in all_hubs:
            if node in existing_hub.spokes:
                existing_hub.spokes.remove(node)

        hub_data = DatabaseHelper.create_hub_data(
            name=node.name,
            node_id=hub_create.node_id,
            mesh_id=mesh_id
        )
        db_hub = HubDB(**hub_data)
        self.db.add(db_hub)
        await self.db.commit()
        await self.db.refresh(db_hub)

        return {
            "hub": HubResponse(
                id=db_hub.id,
                name=db_hub.name,
                node_id=db_hub.node_id,
                spokes=[],
                connected_hubs=[]
            )
        }

    async def get_hubs(self, mesh_id: UUID) -> List[HubResponse]:
        """Get all hubs in the mesh with their connected spokes"""
        conditions = QueryHelper.hubs_by_mesh(mesh_id)
        result = await self.db.execute(
            select(HubDB).where(*conditions).options(
                selectinload(HubDB.spokes),
                selectinload(HubDB.connected_hubs)
            )
        )
        hubs = result.scalars().all()

        return [HubResponse(
            id=hub.id,
            name=hub.name,
            node_id=hub.node_id,
            spokes=[NodeResponse(
                id=spoke.id,
                name=spoke.name,
                addrs=json.loads(spoke.addrs),
                data=json.loads(spoke.data) if spoke.data else {}
            ) for spoke in hub.spokes],
            connected_hubs=[HubBasicInfo(
                id=connected_hub.id,
                name=connected_hub.name,
                node_id=connected_hub.node_id
            ) for connected_hub in QueryHelper.get_all_connected_hubs(hub)]
        ) for hub in hubs]

    async def remove_hub(self, mesh_id: UUID, hub_id: UUID) -> bool:
        """Remove hub status and break all spoke connections"""
        conditions = QueryHelper.hub_by_id_and_mesh(hub_id, mesh_id)
        result = await self.db.execute(select(HubDB).where(*conditions))
        hub = result.scalar_one_or_none()

        if not hub:
            return False

        await self.db.delete(hub)
        await self.db.commit()
        return True


class LinkManager:
    """Core link management operations"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def link_node_to_hub(self, mesh_id: UUID, link: LinkRequest) -> Optional[Dict[str, Any]]:
        """Connect a node to a hub as a spoke"""
        # Check if hub exists in this mesh
        hub_conditions = QueryHelper.hub_by_id_and_mesh(link.hub_id, mesh_id)
        result = await self.db.execute(
            select(HubDB).where(*hub_conditions).options(
                selectinload(HubDB.spokes)
            )
        )
        hub = result.scalar_one_or_none()

        if not hub:
            return {"error": "Hub not found in this mesh", "status_code": 404}

        # Check if node exists in this mesh
        node_conditions = QueryHelper.node_by_id_and_mesh(link.node_id, mesh_id)
        result = await self.db.execute(select(NodeDB).where(*node_conditions))
        node = result.scalar_one_or_none()

        if not node:
            return {"error": "Node not found in this mesh", "status_code": 404}

        # Check if node is trying to link to itself as a hub
        if str(hub.node_id) == str(link.node_id):
            return {"error": "A node cannot be linked to itself as a hub", "status_code": 400}

        # Check if already linked
        if node in hub.spokes:
            return {"error": "Node is already linked to this hub", "status_code": 400}

        hub.spokes.append(node)
        await self.db.commit()

        return {"message": "Node linked to hub successfully"}

    async def unlink_node_from_hub(self, mesh_id: UUID, link: LinkRequest) -> Optional[Dict[str, Any]]:
        """Disconnect a node from a hub"""
        # Check if hub exists in this mesh
        hub_conditions = QueryHelper.hub_by_id_and_mesh(link.hub_id, mesh_id)
        result = await self.db.execute(
            select(HubDB).where(*hub_conditions).options(
                selectinload(HubDB.spokes)
            )
        )
        hub = result.scalar_one_or_none()

        if not hub:
            return {"error": "Hub not found in this mesh", "status_code": 404}

        # Check if node exists in this mesh
        node_conditions = QueryHelper.node_by_id_and_mesh(link.node_id, mesh_id)
        result = await self.db.execute(select(NodeDB).where(*node_conditions))
        node = result.scalar_one_or_none()

        if not node:
            return {"error": "Node not found in this mesh", "status_code": 404}

        # Check if linked
        if node not in hub.spokes:
            return {"error": "Node is not linked to this hub", "status_code": 400}

        hub.spokes.remove(node)
        await self.db.commit()

        return {"message": "Node unlinked from hub successfully"}

    async def connect_hubs(self, mesh_id: UUID, hub_link: HubLinkRequest) -> Optional[Dict[str, Any]]:
        """Connect two hubs together to form complex network topology"""
        # Validate that both hubs exist in the mesh
        source_hub_conditions = QueryHelper.hub_by_id_and_mesh(hub_link.source_hub_id, mesh_id)
        result = await self.db.execute(
            select(HubDB).where(*source_hub_conditions).options(
                selectinload(HubDB.connected_hubs)
            )
        )
        source_hub = result.scalar_one_or_none()

        if not source_hub:
            return {"error": "Source hub not found in this mesh", "status_code": 404}

        target_hub_conditions = QueryHelper.hub_by_id_and_mesh(hub_link.target_hub_id, mesh_id)
        result = await self.db.execute(
            select(HubDB).where(*target_hub_conditions).options(
                selectinload(HubDB.connected_hubs)
            )
        )
        target_hub = result.scalar_one_or_none()

        if not target_hub:
            return {"error": "Target hub not found in this mesh", "status_code": 404}

        # Prevent self-connection
        if source_hub.id == target_hub.id:
            return {"error": "A hub cannot connect to itself", "status_code": 400}

        # Check if connection already exists (either direction)
        if target_hub in source_hub.connected_hubs or source_hub in target_hub.connected_hubs:
            return {"error": "Hubs are already connected", "status_code": 400}

        # Create bidirectional connection (hubs connect to each other)
        source_hub.connected_hubs.append(target_hub)
        target_hub.connected_hubs.append(source_hub)

        await self.db.commit()

        return {"message": "Hubs connected successfully"}

    async def disconnect_hubs(self, mesh_id: UUID, hub_link: HubLinkRequest) -> Optional[Dict[str, Any]]:
        """Disconnect two hubs from each other"""
        # Validate that both hubs exist in the mesh
        source_hub_conditions = QueryHelper.hub_by_id_and_mesh(hub_link.source_hub_id, mesh_id)
        result = await self.db.execute(
            select(HubDB).where(*source_hub_conditions).options(
                selectinload(HubDB.connected_hubs)
            )
        )
        source_hub = result.scalar_one_or_none()

        if not source_hub:
            return {"error": "Source hub not found in this mesh", "status_code": 404}

        target_hub_conditions = QueryHelper.hub_by_id_and_mesh(hub_link.target_hub_id, mesh_id)
        result = await self.db.execute(
            select(HubDB).where(*target_hub_conditions).options(
                selectinload(HubDB.connected_hubs)
            )
        )
        target_hub = result.scalar_one_or_none()

        if not target_hub:
            return {"error": "Target hub not found in this mesh", "status_code": 404}

        # Check if connection exists (either direction)
        if target_hub not in source_hub.connected_hubs and source_hub not in target_hub.connected_hubs:
            return {"error": "Hubs are not connected", "status_code": 400}

        # Remove bidirectional connection
        if target_hub in source_hub.connected_hubs:
            source_hub.connected_hubs.remove(target_hub)
        if source_hub in target_hub.connected_hubs:
            target_hub.connected_hubs.remove(source_hub)

        await self.db.commit()

        return {"message": "Hubs disconnected successfully"}


class MeshNetworkManager:
    """
    Combined manager that provides access to all mesh network operations.
    This is the main interface that should be used by both the web API and CLI.
    """

    def __init__(self, db_session: AsyncSession):
        self.mesh_manager = MeshManager(db_session)
        self.node_manager = NodeManager(db_session)
        self.hub_manager = HubManager(db_session)
        self.link_manager = LinkManager(db_session)

    @property
    def meshes(self) -> MeshManager:
        """Access mesh operations"""
        return self.mesh_manager

    @property
    def nodes(self) -> NodeManager:
        """Access node operations"""
        return self.node_manager

    @property
    def hubs(self) -> HubManager:
        """Access hub operations"""
        return self.hub_manager

    @property
    def links(self) -> LinkManager:
        """Access link operations"""
        return self.link_manager