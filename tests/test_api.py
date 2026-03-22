"""API 集成测试 —— 使用 httpx.AsyncClient + ASGITransport"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from greyfield_hive.main import app
from greyfield_hive.db import init_db, engine, Base


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """每个测试前重置数据库（文件型 SQLite，避免 :memory: 连接隔离问题）"""
    # drop_all + create_all 在同一个 connection 内执行
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "synapse_active"


@pytest.mark.asyncio
async def test_create_task(client):
    resp = await client.post("/api/tasks", json={"title": "测试战团", "priority": "high"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "测试战团"
    assert data["state"] == "Incubating"
    assert data["id"].startswith("BT-")


@pytest.mark.asyncio
async def test_list_tasks(client):
    await client.post("/api/tasks", json={"title": "战团A"})
    await client.post("/api/tasks", json={"title": "战团B"})
    resp = await client.get("/api/tasks")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_task(client):
    create = await client.post("/api/tasks", json={"title": "战团C"})
    task_id = create.json()["id"]
    resp = await client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == task_id


@pytest.mark.asyncio
async def test_valid_transition(client):
    create = await client.post("/api/tasks", json={"title": "战团D"})
    task_id = create.json()["id"]
    resp = await client.post(
        f"/api/tasks/{task_id}/transition",
        json={"new_state": "Planning", "agent": "overmind"},
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "Planning"


@pytest.mark.asyncio
async def test_invalid_transition(client):
    create = await client.post("/api/tasks", json={"title": "战团E"})
    task_id = create.json()["id"]
    # Incubating 不能直接跳到 Complete
    resp = await client.post(
        f"/api/tasks/{task_id}/transition",
        json={"new_state": "Complete", "agent": "test"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_synapses(client):
    resp = await client.get("/api/synapses")
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert "overmind" in ids
    assert "code-expert" in ids


@pytest.mark.asyncio
async def test_task_not_found(client):
    resp = await client.get("/api/tasks/NOT-EXIST")
    assert resp.status_code == 404
