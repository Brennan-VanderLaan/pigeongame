"""
Utility functions for the mesh visualization API
"""

from typing import Union
from uuid import UUID


def to_uuid_str(value: Union[str, UUID]) -> str:
    """
    Convert UUID or UUID string to string format for database storage.

    Args:
        value: UUID object or string representation

    Returns:
        String representation of UUID
    """
    if isinstance(value, UUID):
        return str(value)
    return str(value)  # Ensure it's a string even if already string


def ensure_uuid_strings(**kwargs) -> dict:
    """
    Convert any UUID objects in kwargs to strings.

    Args:
        **kwargs: Keyword arguments that may contain UUID objects

    Returns:
        Dictionary with all UUID objects converted to strings
    """
    result = {}
    for key, value in kwargs.items():
        if isinstance(value, UUID):
            result[key] = str(value)
        else:
            result[key] = value
    return result


class DatabaseHelper:
    """Helper class for database operations with proper UUID handling"""

    @staticmethod
    def create_node_data(name: str, addrs_json: str, mesh_id: Union[str, UUID]) -> dict:
        """Create properly formatted data for NodeDB creation"""
        return {
            "name": name,
            "addrs": addrs_json,
            "mesh_id": to_uuid_str(mesh_id)
        }

    @staticmethod
    def create_hub_data(name: str, node_id: Union[str, UUID], mesh_id: Union[str, UUID]) -> dict:
        """Create properly formatted data for HubDB creation"""
        return {
            "name": name,
            "node_id": to_uuid_str(node_id),
            "mesh_id": to_uuid_str(mesh_id)
        }

    @staticmethod
    def create_mesh_data(name: str) -> dict:
        """Create properly formatted data for MeshDB creation"""
        return {"name": name}


class QueryHelper:
    """Helper class for database queries with proper UUID handling"""

    @staticmethod
    def mesh_by_id(mesh_id: Union[str, UUID]) -> tuple:
        """Create query condition for mesh by ID"""
        from models import MeshDB
        return (MeshDB.id == to_uuid_str(mesh_id),)

    @staticmethod
    def node_by_id_and_mesh(node_id: Union[str, UUID], mesh_id: Union[str, UUID]) -> tuple:
        """Create query condition for node by ID and mesh"""
        from models import NodeDB
        return (
            NodeDB.id == to_uuid_str(node_id),
            NodeDB.mesh_id == to_uuid_str(mesh_id)
        )

    @staticmethod
    def hub_by_id_and_mesh(hub_id: Union[str, UUID], mesh_id: Union[str, UUID]) -> tuple:
        """Create query condition for hub by ID and mesh"""
        from models import HubDB
        return (
            HubDB.id == to_uuid_str(hub_id),
            HubDB.mesh_id == to_uuid_str(mesh_id)
        )

    @staticmethod
    def hub_by_node_and_mesh(node_id: Union[str, UUID], mesh_id: Union[str, UUID]) -> tuple:
        """Create query condition for hub by node ID and mesh"""
        from models import HubDB
        return (
            HubDB.node_id == to_uuid_str(node_id),
            HubDB.mesh_id == to_uuid_str(mesh_id)
        )

    @staticmethod
    def hubs_by_mesh(mesh_id: Union[str, UUID]) -> tuple:
        """Create query condition for all hubs in mesh"""
        from models import HubDB
        return (HubDB.mesh_id == to_uuid_str(mesh_id),)