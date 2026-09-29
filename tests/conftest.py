import os
import pytest
import aiosqlite
from httpx import AsyncClient, ASGITransport

os.environ["DB_PATH"] = ":memory:"

from src.main import app
from src.database import get_db, create_schema


@pytest.fixture
async def client():
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await create_schema(conn)

    async def _override_get_db():
        yield conn

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await conn.close()
