"""
Base test utilities for the mesh API tests
"""

import tempfile
import os
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from main import app
from models import Base
from database import get_db


class TestDatabaseManager:
    """Manages test database lifecycle"""

    def __init__(self):
        self.temp_db_file = None
        self.engine = None
        self.SessionLocal = None

    async def setup(self):
        """Create temporary database and set up engine"""
        # Create temporary file
        fd, self.temp_db_file = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        # Create async engine
        test_database_url = f"sqlite+aiosqlite:///{self.temp_db_file}"
        self.engine = create_async_engine(test_database_url, echo=False)
        self.SessionLocal = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

        # Create tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Override database dependency
        async def override_get_db():
            async with self.SessionLocal() as session:
                try:
                    yield session
                finally:
                    await session.close()

        app.dependency_overrides[get_db] = override_get_db

    async def teardown(self):
        """Clean up database and files"""
        # Clean up override
        if get_db in app.dependency_overrides:
            del app.dependency_overrides[get_db]

        # Close engine
        if self.engine:
            await self.engine.dispose()

        # Remove temp file
        if self.temp_db_file and os.path.exists(self.temp_db_file):
            os.unlink(self.temp_db_file)


class TestClient:
    """Manages test client lifecycle"""

    def __init__(self):
        self.client = None

    async def __aenter__(self):
        self.client = AsyncClient(app=app, base_url="http://test")
        await self.client.__aenter__()
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.__aexit__(exc_type, exc_val, exc_tb)


async def create_test_mesh(client: AsyncClient, name: str = "test-mesh") -> dict:
    """Helper to create a test mesh"""
    response = await client.post("/mesh", json={"name": name})
    assert response.status_code == 201
    return response.json()


async def create_test_node(client: AsyncClient, mesh_id: str, name: str = "test-node",
                          addrs: list = None, data: dict = None) -> dict:
    """Helper to create a test node"""
    if addrs is None:
        addrs = ["192.168.1.1"]
    if data is None:
        data = {}

    response = await client.post(
        f"/mesh/{mesh_id}/node",
        json={"name": name, "addrs": addrs, "data": data}
    )
    assert response.status_code == 201
    return response.json()


async def create_test_hub(client: AsyncClient, mesh_id: str, node_id: str) -> dict:
    """Helper to create a test hub"""
    response = await client.post(
        f"/mesh/{mesh_id}/hub",
        json={"node_id": node_id}
    )
    assert response.status_code == 201
    return response.json()