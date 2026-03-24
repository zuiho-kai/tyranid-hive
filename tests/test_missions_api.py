import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from greyfield_hive.main import app
from greyfield_hive.db import engine, Base


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
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
async def test_submit_mission_creates_task_with_mode_and_run_metadata(client: AsyncClient):
    response = await client.post(
        "/api/missions",
        json={
            "title": "Build a parser",
            "description": "Run this as a chain task",
            "priority": "high",
            "mode": "chain",
            "chain_stages": ["code-expert", "research-analyst"],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["task"]["title"] == "Build a parser"
    assert body["task"]["exec_mode"] == "chain"
    assert body["task"]["meta"]["chain_stages"] == ["code-expert", "research-analyst"]
    assert body["task"]["meta"]["mode_source"] == "user"
    assert body["task"]["meta"]["skip_consolidation"] is True
    assert body["run"]["started"] is True
    assert body["run"]["entrypoint"] == "task.created"


@pytest.mark.asyncio
async def test_submit_mission_rejects_invalid_mode_shape(client: AsyncClient):
    response = await client.post(
        "/api/missions",
        json={
            "title": "Broken trial task",
            "mode": "trial",
            "trial_candidates": ["code-expert"],
        },
    )

    assert response.status_code == 422
