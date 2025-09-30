from typing import List
from uuid import UUID
import json
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    MeshCreate, MeshResponse,
    NodeCreate, NodeResponse,
    HubCreate, HubResponse,
    LinkRequest, HubLinkRequest
)
from database import get_db, init_db
from mesh_manager import MeshNetworkManager
from logging_config import setup_web_logging, get_component_logger

app = FastAPI(
    title="Mesh Network API",
    description="API for managing mesh networks with nodes and hubs",
    version="1.0.0"
)

# Mount static files (commented out - no static directory exists)
# app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
async def startup_event():
    # Setup structured logging for web application
    setup_web_logging()
    logger = get_component_logger("web")
    logger.info("Starting mesh network web application")
    await init_db()
    logger.info("Database initialization complete")

# Initialize logger for web endpoints
logger = get_component_logger("web")

@app.get("/")
async def read_root():
    logger.debug("Serving web interface root page")
    return FileResponse("templates/index.html")

# Mesh endpoints
@app.post("/mesh", response_model=MeshResponse, status_code=status.HTTP_201_CREATED)
async def create_mesh(
    mesh: MeshCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new mesh network"""
    logger.info("Creating new mesh", extra={"mesh_name": mesh.name})
    manager = MeshNetworkManager(db)
    result = await manager.meshes.create_mesh(mesh)
    logger.info("Mesh created successfully", extra={"mesh_name": result.name, "mesh_id": str(result.id)})
    return result

@app.get("/mesh", response_model=List[MeshResponse])
async def list_meshes(db: AsyncSession = Depends(get_db)):
    """List all mesh networks with their nodes and hubs"""
    logger.debug("Listing all mesh networks")
    manager = MeshNetworkManager(db)
    result = await manager.meshes.list_meshes()
    logger.info("Listed mesh networks", extra={"mesh_count": len(result)})
    return result

@app.get("/mesh/{mesh_id}", response_model=MeshResponse)
async def get_mesh(mesh_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a specific mesh network by ID"""
    logger.debug("Getting mesh by ID", extra={"mesh_id": str(mesh_id)})
    manager = MeshNetworkManager(db)
    mesh = await manager.meshes.get_mesh(mesh_id)

    if not mesh:
        logger.warning("Mesh not found", extra={"mesh_id": str(mesh_id)})
        raise HTTPException(status_code=404, detail="Mesh not found")

    logger.info("Mesh retrieved successfully", extra={"mesh_id": str(mesh_id), "mesh_name": mesh.name})
    return mesh

@app.delete("/mesh/{mesh_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mesh(
    mesh_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete a mesh network and all associated nodes and hubs"""
    logger.info("Deleting mesh", extra={"mesh_id": str(mesh_id)})
    manager = MeshNetworkManager(db)
    success = await manager.meshes.delete_mesh(mesh_id)

    if not success:
        logger.warning("Attempted to delete non-existent mesh", extra={"mesh_id": str(mesh_id)})
        raise HTTPException(status_code=404, detail="Mesh not found")

    logger.info("Mesh deleted successfully", extra={"mesh_id": str(mesh_id)})

# Node endpoints
@app.post("/mesh/{mesh_id}/node", response_model=NodeResponse, status_code=status.HTTP_201_CREATED)
async def add_node_to_mesh(
    mesh_id: UUID,
    node: NodeCreate,
    db: AsyncSession = Depends(get_db)
):
    """Add a node to the mesh"""
    logger.info("Adding node to mesh", extra={
        "mesh_id": str(mesh_id),
        "node_name": node.name,
        "node_addrs": node.addrs
    })
    manager = MeshNetworkManager(db)
    result = await manager.nodes.add_node_to_mesh(mesh_id, node)

    if not result:
        logger.warning("Failed to add node - mesh not found", extra={
            "mesh_id": str(mesh_id),
            "node_name": node.name
        })
        raise HTTPException(status_code=404, detail="Mesh not found")

    logger.info("Node added successfully", extra={
        "mesh_id": str(mesh_id),
        "node_id": str(result.id),
        "node_name": result.name
    })
    return result

@app.delete("/mesh/{mesh_id}/node/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_node_from_mesh(
    mesh_id: UUID,
    node_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Remove a node from the mesh"""
    logger.info("Removing node from mesh", extra={
        "mesh_id": str(mesh_id),
        "node_id": str(node_id)
    })
    manager = MeshNetworkManager(db)
    success = await manager.nodes.remove_node_from_mesh(mesh_id, node_id)

    if not success:
        logger.warning("Failed to remove node - not found in mesh", extra={
            "mesh_id": str(mesh_id),
            "node_id": str(node_id)
        })
        raise HTTPException(status_code=404, detail="Node not found in this mesh")

    logger.info("Node removed successfully", extra={
        "mesh_id": str(mesh_id),
        "node_id": str(node_id)
    })

# Hub endpoints
@app.post("/mesh/{mesh_id}/hub", response_model=HubResponse, status_code=status.HTTP_201_CREATED)
async def create_hub(
    mesh_id: UUID,
    hub: HubCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a hub from an existing node"""
    logger.info("Creating hub from node", extra={
        "mesh_id": str(mesh_id),
        "node_id": str(hub.node_id)
    })
    manager = MeshNetworkManager(db)
    result = await manager.hubs.create_hub(mesh_id, hub)

    if "error" in result:
        logger.warning("Failed to create hub", extra={
            "mesh_id": str(mesh_id),
            "node_id": str(hub.node_id),
            "error": result["error"]
        })
        raise HTTPException(status_code=result["status_code"], detail=result["error"])

    logger.info("Hub created successfully", extra={
        "mesh_id": str(mesh_id),
        "hub_id": str(result["hub"].id),
        "hub_name": result["hub"].name
    })
    return result["hub"]

@app.get("/mesh/{mesh_id}/hub", response_model=List[HubResponse])
async def get_hubs(mesh_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get all hubs in the mesh with their connected spokes"""
    logger.debug("Getting hubs in mesh", extra={"mesh_id": str(mesh_id)})
    manager = MeshNetworkManager(db)
    result = await manager.hubs.get_hubs(mesh_id)
    logger.info("Retrieved hubs", extra={
        "mesh_id": str(mesh_id),
        "hub_count": len(result)
    })
    return result

@app.delete("/mesh/{mesh_id}/hub/{hub_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_hub(
    mesh_id: UUID,
    hub_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Remove hub status and break all spoke connections"""
    logger.info("Removing hub", extra={
        "mesh_id": str(mesh_id),
        "hub_id": str(hub_id)
    })
    manager = MeshNetworkManager(db)
    success = await manager.hubs.remove_hub(mesh_id, hub_id)

    if not success:
        logger.warning("Failed to remove hub - not found in mesh", extra={
            "mesh_id": str(mesh_id),
            "hub_id": str(hub_id)
        })
        raise HTTPException(status_code=404, detail="Hub not found in this mesh")

    logger.info("Hub removed successfully", extra={
        "mesh_id": str(mesh_id),
        "hub_id": str(hub_id)
    })

# Link management endpoints
@app.post("/mesh/{mesh_id}/link_to_hub", status_code=status.HTTP_200_OK)
async def link_node_to_hub(
    mesh_id: UUID,
    link: LinkRequest,
    db: AsyncSession = Depends(get_db)
):
    """Connect a node to a hub as a spoke"""
    logger.info("Linking node to hub", extra={
        "mesh_id": str(mesh_id),
        "node_id": str(link.node_id),
        "hub_id": str(link.hub_id)
    })
    manager = MeshNetworkManager(db)
    result = await manager.links.link_node_to_hub(mesh_id, link)

    if "error" in result:
        logger.warning("Failed to link node to hub", extra={
            "mesh_id": str(mesh_id),
            "node_id": str(link.node_id),
            "hub_id": str(link.hub_id),
            "error": result["error"]
        })
        raise HTTPException(status_code=result["status_code"], detail=result["error"])

    logger.info("Node linked to hub successfully", extra={
        "mesh_id": str(mesh_id),
        "node_id": str(link.node_id),
        "hub_id": str(link.hub_id)
    })
    return result

@app.post("/mesh/{mesh_id}/unlink_from_hub", status_code=status.HTTP_200_OK)
async def unlink_node_from_hub(
    mesh_id: UUID,
    link: LinkRequest,
    db: AsyncSession = Depends(get_db)
):
    """Disconnect a node from a hub"""
    logger.info("Unlinking node from hub", extra={
        "mesh_id": str(mesh_id),
        "node_id": str(link.node_id),
        "hub_id": str(link.hub_id)
    })
    manager = MeshNetworkManager(db)
    result = await manager.links.unlink_node_from_hub(mesh_id, link)

    if "error" in result:
        logger.warning("Failed to unlink node from hub", extra={
            "mesh_id": str(mesh_id),
            "node_id": str(link.node_id),
            "hub_id": str(link.hub_id),
            "error": result["error"]
        })
        raise HTTPException(status_code=result["status_code"], detail=result["error"])

    logger.info("Node unlinked from hub successfully", extra={
        "mesh_id": str(mesh_id),
        "node_id": str(link.node_id),
        "hub_id": str(link.hub_id)
    })
    return result

# Hub-to-hub connection endpoints
@app.post("/mesh/{mesh_id}/connect_hubs", status_code=status.HTTP_200_OK)
async def connect_hubs(
    mesh_id: UUID,
    hub_link: HubLinkRequest,
    db: AsyncSession = Depends(get_db)
):
    """Connect two hubs together to form complex network topology"""
    logger.info("Connecting hubs", extra={
        "mesh_id": str(mesh_id),
        "source_hub_id": str(hub_link.source_hub_id),
        "target_hub_id": str(hub_link.target_hub_id)
    })
    manager = MeshNetworkManager(db)
    result = await manager.links.connect_hubs(mesh_id, hub_link)

    if "error" in result:
        logger.warning("Failed to connect hubs", extra={
            "mesh_id": str(mesh_id),
            "source_hub_id": str(hub_link.source_hub_id),
            "target_hub_id": str(hub_link.target_hub_id),
            "error": result["error"]
        })
        raise HTTPException(status_code=result["status_code"], detail=result["error"])

    logger.info("Hubs connected successfully", extra={
        "mesh_id": str(mesh_id),
        "source_hub_id": str(hub_link.source_hub_id),
        "target_hub_id": str(hub_link.target_hub_id)
    })
    return result

@app.post("/mesh/{mesh_id}/disconnect_hubs", status_code=status.HTTP_200_OK)
async def disconnect_hubs(
    mesh_id: UUID,
    hub_link: HubLinkRequest,
    db: AsyncSession = Depends(get_db)
):
    """Disconnect two hubs from each other"""
    logger.info("Disconnecting hubs", extra={
        "mesh_id": str(mesh_id),
        "source_hub_id": str(hub_link.source_hub_id),
        "target_hub_id": str(hub_link.target_hub_id)
    })
    manager = MeshNetworkManager(db)
    result = await manager.links.disconnect_hubs(mesh_id, hub_link)

    if "error" in result:
        logger.warning("Failed to disconnect hubs", extra={
            "mesh_id": str(mesh_id),
            "source_hub_id": str(hub_link.source_hub_id),
            "target_hub_id": str(hub_link.target_hub_id),
            "error": result["error"]
        })
        raise HTTPException(status_code=result["status_code"], detail=result["error"])

    logger.info("Hubs disconnected successfully", extra={
        "mesh_id": str(mesh_id),
        "source_hub_id": str(hub_link.source_hub_id),
        "target_hub_id": str(hub_link.target_hub_id)
    })
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)