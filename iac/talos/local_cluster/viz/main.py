from typing import List
from uuid import UUID
import json
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models import (
    MeshDB, NodeDB, HubDB,
    MeshCreate, MeshResponse,
    NodeCreate, NodeResponse,
    HubCreate, HubResponse,
    LinkRequest
)
from database import get_db, init_db
from utils import DatabaseHelper, QueryHelper

app = FastAPI(
    title="Mesh Network API",
    description="API for managing mesh networks with nodes and hubs",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
async def startup_event():
    await init_db()

@app.get("/")
async def read_root():
    return FileResponse("templates/index.html")

# Mesh endpoints
@app.post("/mesh", response_model=MeshResponse, status_code=status.HTTP_201_CREATED)
async def create_mesh(
    mesh: MeshCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new mesh network

    - **name**: The name of the mesh network

    Returns the created mesh with its UUID
    """
    mesh_data = DatabaseHelper.create_mesh_data(mesh.name)
    db_mesh = MeshDB(**mesh_data)
    db.add(db_mesh)
    await db.commit()
    await db.refresh(db_mesh)
    return MeshResponse(id=db_mesh.id, name=db_mesh.name, nodes=[], hubs=[])

@app.get("/mesh", response_model=List[MeshResponse])
async def list_meshes(db: AsyncSession = Depends(get_db)):
    """
    List all mesh networks

    Returns a list of all mesh networks with their nodes and hubs
    """
    result = await db.execute(
        select(MeshDB).options(
            selectinload(MeshDB.nodes),
            selectinload(MeshDB.hubs).selectinload(HubDB.spokes)
        )
    )
    meshes = result.scalars().all()

    response = []
    for mesh in meshes:
        nodes = [NodeResponse(
            id=node.id,
            name=node.name,
            addrs=json.loads(node.addrs)
        ) for node in mesh.nodes]

        hubs = [HubResponse(
            id=hub.id,
            name=hub.name,
            node_id=hub.node_id,
            spokes=[NodeResponse(
                id=spoke.id,
                name=spoke.name,
                addrs=json.loads(spoke.addrs)
            ) for spoke in hub.spokes]
        ) for hub in mesh.hubs]

        response.append(MeshResponse(
            id=mesh.id,
            name=mesh.name,
            nodes=nodes,
            hubs=hubs
        ))

    return response

@app.get("/mesh/{mesh_id}", response_model=MeshResponse)
async def get_mesh(mesh_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Get a specific mesh network by ID

    - **mesh_id**: UUID of the mesh to retrieve

    Returns the mesh with all its nodes and hubs
    """
    conditions = QueryHelper.mesh_by_id(mesh_id)
    result = await db.execute(
        select(MeshDB).where(*conditions).options(
            selectinload(MeshDB.nodes),
            selectinload(MeshDB.hubs).selectinload(HubDB.spokes)
        )
    )
    mesh = result.scalar_one_or_none()

    if not mesh:
        raise HTTPException(status_code=404, detail="Mesh not found")

    nodes = [NodeResponse(
        id=node.id,
        name=node.name,
        addrs=json.loads(node.addrs)
    ) for node in mesh.nodes]

    hubs = [HubResponse(
        id=hub.id,
        name=hub.name,
        node_id=hub.node_id,
        spokes=[NodeResponse(
            id=spoke.id,
            name=spoke.name,
            addrs=json.loads(spoke.addrs)
        ) for spoke in hub.spokes]
    ) for hub in mesh.hubs]

    return MeshResponse(
        id=mesh.id,
        name=mesh.name,
        nodes=nodes,
        hubs=hubs
    )

@app.delete("/mesh/{mesh_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mesh(
    mesh_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a mesh network

    - **mesh_id**: UUID of the mesh to delete

    This will also delete all associated nodes and hubs
    """
    conditions = QueryHelper.mesh_by_id(mesh_id)
    result = await db.execute(select(MeshDB).where(*conditions))
    mesh = result.scalar_one_or_none()

    if not mesh:
        raise HTTPException(status_code=404, detail="Mesh not found")

    await db.delete(mesh)
    await db.commit()

# Node endpoints
@app.post("/mesh/{mesh_id}/node", response_model=NodeResponse, status_code=status.HTTP_201_CREATED)
async def add_node_to_mesh(
    mesh_id: UUID,
    node: NodeCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Add a node to the pool for a given mesh

    - **mesh_id**: UUID of the mesh to add the node to
    - **name**: Name of the node
    - **addrs**: List of network addresses for the node

    Returns the created node with its UUID
    """
    # Check if mesh exists
    conditions = QueryHelper.mesh_by_id(mesh_id)
    result = await db.execute(select(MeshDB).where(*conditions))
    mesh = result.scalar_one_or_none()

    if not mesh:
        raise HTTPException(status_code=404, detail="Mesh not found")

    node_data = DatabaseHelper.create_node_data(
        name=node.name,
        addrs_json=json.dumps(node.addrs),
        mesh_id=mesh_id
    )
    db_node = NodeDB(**node_data)
    db.add(db_node)
    await db.commit()
    await db.refresh(db_node)

    return NodeResponse(
        id=db_node.id,
        name=db_node.name,
        addrs=json.loads(db_node.addrs)
    )

@app.delete("/mesh/{mesh_id}/node/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_node_from_mesh(
    mesh_id: UUID,
    node_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Remove a given node from the pool for a given mesh

    - **mesh_id**: UUID of the mesh
    - **node_id**: UUID of the node to remove

    This will also remove the node from any hubs it's connected to
    """
    conditions = QueryHelper.node_by_id_and_mesh(node_id, mesh_id)
    result = await db.execute(select(NodeDB).where(*conditions))
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(status_code=404, detail="Node not found in this mesh")

    await db.delete(node)
    await db.commit()

# Hub endpoints
@app.post("/mesh/{mesh_id}/hub", response_model=HubResponse, status_code=status.HTTP_201_CREATED)
async def create_hub(
    mesh_id: UUID,
    hub: HubCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Set an existing node as a communication hub

    - **mesh_id**: UUID of the mesh
    - **node_id**: UUID of the existing node to make a hub

    Returns the created hub with its UUID
    """
    # Check if mesh exists
    mesh_conditions = QueryHelper.mesh_by_id(mesh_id)
    result = await db.execute(select(MeshDB).where(*mesh_conditions))
    mesh = result.scalar_one_or_none()

    if not mesh:
        raise HTTPException(status_code=404, detail="Mesh not found")

    # Check if node exists in this mesh
    node_conditions = QueryHelper.node_by_id_and_mesh(hub.node_id, mesh_id)
    result = await db.execute(select(NodeDB).where(*node_conditions))
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(status_code=404, detail="Node not found in this mesh")

    # Check if hub already exists for this node
    hub_conditions = QueryHelper.hub_by_node_and_mesh(hub.node_id, mesh_id)
    result = await db.execute(select(HubDB).where(*hub_conditions))
    existing_hub = result.scalar_one_or_none()

    if existing_hub:
        raise HTTPException(status_code=400, detail="Node is already a hub")

    # If this node is currently linked as a spoke to any hubs, unlink it first
    # A node cannot be both a hub and a spoke
    all_hubs_conditions = QueryHelper.hubs_by_mesh(mesh_id)
    result = await db.execute(
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
        node_id=hub.node_id,
        mesh_id=mesh_id
    )
    db_hub = HubDB(**hub_data)
    db.add(db_hub)
    await db.commit()
    await db.refresh(db_hub)

    return HubResponse(
        id=db_hub.id,
        name=db_hub.name,
        node_id=db_hub.node_id,
        spokes=[]
    )

@app.get("/mesh/{mesh_id}/hub", response_model=List[HubResponse])
async def get_hubs(mesh_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Get the list of existing hubs for a given mesh

    - **mesh_id**: UUID of the mesh

    Returns all hubs in the mesh with their connected spokes
    """
    conditions = QueryHelper.hubs_by_mesh(mesh_id)
    result = await db.execute(
        select(HubDB).where(*conditions).options(
            selectinload(HubDB.spokes)
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
            addrs=json.loads(spoke.addrs)
        ) for spoke in hub.spokes]
    ) for hub in hubs]

@app.delete("/mesh/{mesh_id}/hub/{hub_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_hub(
    mesh_id: UUID,
    hub_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Remove the hub status from a node and break all links

    - **mesh_id**: UUID of the mesh
    - **hub_id**: UUID of the hub to remove

    This will break all connections between the hub and its spokes
    """
    conditions = QueryHelper.hub_by_id_and_mesh(hub_id, mesh_id)
    result = await db.execute(select(HubDB).where(*conditions))
    hub = result.scalar_one_or_none()

    if not hub:
        raise HTTPException(status_code=404, detail="Hub not found in this mesh")

    await db.delete(hub)
    await db.commit()

# Link management endpoints
@app.post("/mesh/{mesh_id}/link_to_hub", status_code=status.HTTP_200_OK)
async def link_node_to_hub(
    mesh_id: UUID,
    link: LinkRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Connect a node to a hub

    - **mesh_id**: UUID of the mesh
    - **node_id**: UUID of the node to connect
    - **hub_id**: UUID of the hub to connect to

    Creates a spoke connection from the node to the hub
    """
    # Check if hub exists in this mesh
    hub_conditions = QueryHelper.hub_by_id_and_mesh(link.hub_id, mesh_id)
    result = await db.execute(
        select(HubDB).where(*hub_conditions).options(
            selectinload(HubDB.spokes)
        )
    )
    hub = result.scalar_one_or_none()

    if not hub:
        raise HTTPException(status_code=404, detail="Hub not found in this mesh")

    # Check if node exists in this mesh
    node_conditions = QueryHelper.node_by_id_and_mesh(link.node_id, mesh_id)
    result = await db.execute(select(NodeDB).where(*node_conditions))
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(status_code=404, detail="Node not found in this mesh")

    # Check if already linked
    if node in hub.spokes:
        raise HTTPException(status_code=400, detail="Node is already linked to this hub")

    hub.spokes.append(node)
    await db.commit()

    return {"message": "Node linked to hub successfully"}

@app.post("/mesh/{mesh_id}/unlink_from_hub", status_code=status.HTTP_200_OK)
async def unlink_node_from_hub(
    mesh_id: UUID,
    link: LinkRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Disconnect a node from a hub

    - **mesh_id**: UUID of the mesh
    - **node_id**: UUID of the node to disconnect
    - **hub_id**: UUID of the hub to disconnect from

    Removes the spoke connection between the node and hub
    """
    # Check if hub exists in this mesh
    hub_conditions = QueryHelper.hub_by_id_and_mesh(link.hub_id, mesh_id)
    result = await db.execute(
        select(HubDB).where(*hub_conditions).options(
            selectinload(HubDB.spokes)
        )
    )
    hub = result.scalar_one_or_none()

    if not hub:
        raise HTTPException(status_code=404, detail="Hub not found in this mesh")

    # Check if node exists in this mesh
    node_conditions = QueryHelper.node_by_id_and_mesh(link.node_id, mesh_id)
    result = await db.execute(select(NodeDB).where(*node_conditions))
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(status_code=404, detail="Node not found in this mesh")

    # Check if linked
    if node not in hub.spokes:
        raise HTTPException(status_code=400, detail="Node is not linked to this hub")

    hub.spokes.remove(node)
    await db.commit()

    return {"message": "Node unlinked from hub successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)