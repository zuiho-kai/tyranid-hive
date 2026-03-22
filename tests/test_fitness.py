"""适存度系统测试 —— FitnessService + /api/fitness 端点"""

import pytest
from httpx import AsyncClient, ASGITransport

from greyfield_hive.main import app
from greyfield_hive.db import engine, Base, SessionLocal
from greyfield_hive.services.fitness_service import FitnessService, DECAY


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── FitnessService 单元测试 ────────────────────────────────

@pytest.mark.asyncio
async def test_record_execution_success():
    """成功记录战功 — 返回至少 1 条 KillMark"""
    async with SessionLocal() as db:
        svc = FitnessService(db)
        marks = await svc.record_execution(
            synapse_id="code-expert",
            task_id="T-001",
            domain="coding",
            success=True,
            score=1.0,
        )
        await db.commit()

    assert len(marks) >= 1
    assert all(m.synapse_id == "code-expert" for m in marks)
    assert all(m.biomass_delta > 0 for m in marks)


@pytest.mark.asyncio
async def test_record_execution_failure_reduces_biomass():
    """失败战功的 biomass_delta 应小于同等 score 的成功战功"""
    async with SessionLocal() as db:
        svc = FitnessService(db)
        success_marks = await svc.record_execution(
            synapse_id="code-expert", task_id=None, domain="coding",
            success=True, score=1.0,
        )
        fail_marks = await svc.record_execution(
            synapse_id="research-analyst", task_id=None, domain="research",
            success=False, score=1.0,
        )
        await db.commit()

    success_delta = sum(m.biomass_delta for m in success_marks)
    fail_delta    = sum(m.biomass_delta for m in fail_marks)
    assert fail_delta < success_delta


@pytest.mark.asyncio
async def test_compute_fitness_new_synapse():
    """无战功的 synapse 适存度为 0"""
    async with SessionLocal() as db:
        svc = FitnessService(db)
        score = await svc.compute_fitness("unknown-synapse")

    assert score.fitness == 0.0
    assert score.mark_count == 0
    assert score.success_count == 0
    assert score.fail_count == 0


@pytest.mark.asyncio
async def test_compute_fitness_accumulates():
    """多次执行后适存度应 > 0"""
    async with SessionLocal() as db:
        svc = FitnessService(db)
        for _ in range(3):
            await svc.record_execution(
                synapse_id="code-expert", task_id=None, domain="coding",
                success=True, score=1.0,
            )
        await db.commit()

    async with SessionLocal() as db:
        svc = FitnessService(db)
        score = await svc.compute_fitness("code-expert")

    assert score.fitness > 0
    assert score.mark_count > 0
    assert score.fail_count == 0
    assert score.success_count == score.mark_count


@pytest.mark.asyncio
async def test_success_rate_calculation():
    """success_rate = success_count / (success_count + fail_count)"""
    async with SessionLocal() as db:
        svc = FitnessService(db)
        await svc.record_execution("test-syn", None, "general", True,  1.0)
        await svc.record_execution("test-syn", None, "general", True,  1.0)
        await svc.record_execution("test-syn", None, "general", False, 1.0)
        await db.commit()

    async with SessionLocal() as db:
        svc = FitnessService(db)
        score = await svc.compute_fitness("test-syn")

    assert score.success_count == 2
    assert score.fail_count    == 1
    assert abs(score.success_rate - 2/3) < 0.001


@pytest.mark.asyncio
async def test_leaderboard_returns_sorted():
    """排行榜应按 fitness 降序排列"""
    async with SessionLocal() as db:
        svc = FitnessService(db)
        # code-expert 5 次，research-analyst 1 次
        for _ in range(5):
            await svc.record_execution("code-expert", None, "coding", True, 1.0)
        await svc.record_execution("research-analyst", None, "research", True, 1.0)
        await db.commit()

    async with SessionLocal() as db:
        svc = FitnessService(db)
        lb = await svc.get_leaderboard(limit=10)

    assert len(lb) == 2
    assert lb[0].synapse_id == "code-expert"
    assert lb[0].fitness > lb[1].fitness


@pytest.mark.asyncio
async def test_leaderboard_limit():
    """排行榜 limit 生效"""
    async with SessionLocal() as db:
        svc = FitnessService(db)
        for i in range(5):
            await svc.record_execution(f"syn-{i}", None, "general", True, 1.0)
        await db.commit()

    async with SessionLocal() as db:
        svc = FitnessService(db)
        lb = await svc.get_leaderboard(limit=3)

    assert len(lb) == 3


@pytest.mark.asyncio
async def test_get_synapse_history():
    """get_synapse_history 应返回最近 N 条记录"""
    async with SessionLocal() as db:
        svc = FitnessService(db)
        for _ in range(5):
            await svc.record_execution("code-expert", None, "coding", True, 1.0)
        await db.commit()

    async with SessionLocal() as db:
        svc = FitnessService(db)
        history = await svc.get_synapse_history("code-expert", limit=3)

    assert len(history) == 3


# ── API 端点测试 ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_leaderboard_empty(client):
    """空数据库下排行榜返回空列表"""
    r = await client.get("/api/fitness/leaderboard")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["scores"] == []


@pytest.mark.asyncio
async def test_api_record_and_leaderboard(client):
    """手动记录战功后，排行榜应包含该 synapse"""
    r = await client.post("/api/fitness/record", json={
        "synapse_id": "code-expert",
        "task_id":    "T-API-001",
        "domain":     "coding",
        "success":    True,
        "score":      0.9,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["synapse_id"] == "code-expert"
    assert data["recorded"] >= 1

    r2 = await client.get("/api/fitness/leaderboard")
    assert r2.status_code == 200
    lb = r2.json()
    assert lb["total"] >= 1
    assert lb["scores"][0]["synapse_id"] == "code-expert"


@pytest.mark.asyncio
async def test_api_synapse_fitness_detail(client):
    """GET /api/fitness/{synapse_id} 应返回 fitness + recent_marks"""
    await client.post("/api/fitness/record", json={
        "synapse_id": "research-analyst",
        "domain":     "research",
        "success":    True,
        "score":      1.0,
    })

    r = await client.get("/api/fitness/research-analyst")
    assert r.status_code == 200
    data = r.json()
    assert data["synapse_id"] == "research-analyst"
    assert data["fitness"] > 0
    assert isinstance(data["recent_marks"], list)
    assert len(data["recent_marks"]) >= 1


@pytest.mark.asyncio
async def test_api_record_invalid_score(client):
    """score 超出范围时应返回 400"""
    r = await client.post("/api/fitness/record", json={
        "synapse_id": "code-expert",
        "score":      1.5,
    })
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_api_new_synapse_fitness(client):
    """无战功的 synapse 查询适存度应返回 0"""
    r = await client.get("/api/fitness/no-such-synapse")
    assert r.status_code == 200
    data = r.json()
    assert data["fitness"] == 0.0
    assert data["mark_count"] == 0


@pytest.mark.asyncio
async def test_api_leaderboard_limit(client):
    """排行榜 limit 参数生效"""
    for i in range(5):
        await client.post("/api/fitness/record", json={
            "synapse_id": f"syn-{i}",
            "domain":     "general",
            "success":    True,
            "score":      1.0,
        })

    r = await client.get("/api/fitness/leaderboard?limit=3")
    assert r.status_code == 200
    data = r.json()
    assert len(data["scores"]) == 3
