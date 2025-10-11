from typing import List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Column, String, ForeignKey, Table, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import uuid

Base = declarative_base()

# Association table for many-to-many relationship between hubs and nodes
hub_node_association = Table(
    'hub_nodes',
    Base.metadata,
    Column('hub_id', String(36), ForeignKey('hubs.id')),
    Column('node_id', String(36), ForeignKey('nodes.id'))
)

# Association table for many-to-many relationship between hubs (hub-to-hub connections)
hub_hub_association = Table(
    'hub_connections',
    Base.metadata,
    Column('source_hub_id', String(36), ForeignKey('hubs.id')),
    Column('target_hub_id', String(36), ForeignKey('hubs.id'))
)

class NodeDB(Base):
    __tablename__ = 'nodes'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    addrs = Column(String, nullable=False)  # JSON string of addresses
    data = Column(String, nullable=True, default='{}')  # JSON string for arbitrary data
    mesh_id = Column(String(36), ForeignKey('meshes.id'))

    mesh = relationship("MeshDB", back_populates="nodes")
    connected_hubs = relationship("HubDB", secondary=hub_node_association, back_populates="spokes")

class HubDB(Base):
    __tablename__ = 'hubs'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    node_id = Column(String(36), ForeignKey('nodes.id'))
    mesh_id = Column(String(36), ForeignKey('meshes.id'))

    node = relationship("NodeDB")
    mesh = relationship("MeshDB", back_populates="hubs")
    spokes = relationship("NodeDB", secondary=hub_node_association, back_populates="connected_hubs")

    # Hub-to-hub connections (bidirectional many-to-many)
    connected_hubs = relationship(
        "HubDB",
        secondary=hub_hub_association,
        primaryjoin=id == hub_hub_association.c.source_hub_id,
        secondaryjoin=id == hub_hub_association.c.target_hub_id
    )

class MeshDB(Base):
    __tablename__ = 'meshes'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)

    nodes = relationship("NodeDB", back_populates="mesh")
    hubs = relationship("HubDB", back_populates="mesh")

# Pydantic models for API
class NodeCreate(BaseModel):
    name: str
    addrs: List[str]
    data: Optional[dict] = {}

class NodeDataUpdate(BaseModel):
    data: dict

class NodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    addrs: List[str]
    data: dict = {}

class HubCreate(BaseModel):
    node_id: UUID

class HubResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    node_id: UUID
    spokes: List[NodeResponse] = []
    connected_hubs: List['HubBasicInfo'] = []

class HubBasicInfo(BaseModel):
    """Basic hub info to avoid circular references in hub connections"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    node_id: UUID

# Update HubResponse to use the forward reference
HubResponse.model_rebuild()

class MeshCreate(BaseModel):
    name: str

class MeshResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    nodes: List[NodeResponse] = []
    hubs: List[HubResponse] = []

class LinkRequest(BaseModel):
    node_id: UUID
    hub_id: UUID

class HubLinkRequest(BaseModel):
    source_hub_id: UUID
    target_hub_id: UUID

# Database setup
DATABASE_URL = "sqlite+aiosqlite:///./mesh.db"
engine = create_engine(DATABASE_URL.replace("+aiosqlite", ""))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    Base.metadata.create_all(bind=engine)