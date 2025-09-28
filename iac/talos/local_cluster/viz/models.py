from typing import List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, ForeignKey, Table, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import uuid

Base = declarative_base()

# Association table for many-to-many relationship between hubs and nodes
hub_node_association = Table(
    'hub_nodes',
    Base.metadata,
    Column('hub_id', String(36), ForeignKey('hubs.id')),
    Column('node_id', String(36), ForeignKey('nodes.id'))
)

class NodeDB(Base):
    __tablename__ = 'nodes'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    addrs = Column(String, nullable=False)  # JSON string of addresses
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

class NodeResponse(BaseModel):
    id: UUID
    name: str
    addrs: List[str]

    class Config:
        from_attributes = True

class HubCreate(BaseModel):
    node_id: UUID

class HubResponse(BaseModel):
    id: UUID
    name: str
    node_id: UUID
    spokes: List[NodeResponse] = []

    class Config:
        from_attributes = True

class MeshCreate(BaseModel):
    name: str

class MeshResponse(BaseModel):
    id: UUID
    name: str
    nodes: List[NodeResponse] = []
    hubs: List[HubResponse] = []

    class Config:
        from_attributes = True

class LinkRequest(BaseModel):
    node_id: UUID
    hub_id: UUID

# Database setup
DATABASE_URL = "sqlite+aiosqlite:///./mesh.db"
engine = create_engine(DATABASE_URL.replace("+aiosqlite", ""))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    Base.metadata.create_all(bind=engine)