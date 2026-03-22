"""综合统计仪表盘 —— timeline 端点测试"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

from greyfield_hive.main import app
from greyfield_hive.db import engine, Base, SessionLocal
from greyfield_hive.models.task import Task, TaskState
from greyfield_hive.models.lesson import Lesson


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


@pytest.fixture
async def db_session():
    async with SessionLocal() as db:
        yield db


# ── 辅助 ──────────────────────────────────────────────────

async def _create_task_at(db, days_ago: int, state: str = "Incubating"):
    ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
    task = Task(
        title=f"任务 {days_ago}天前",
        state=TaskState(state),
        priority="normal",
        creator="test",
        created_at=ts,
        updated_at=ts,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def _create_lesson_at(db, days_ago: int, outcome: str = "success"):
    ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
    lesson = Lesson(
        domain="coding",
        content=f"经验 {days_ago}天前",
        outcome=outcome,
        created_at=ts,
        updated_at=ts,
        last_used=ts,
    )
    db.add(lesson)
    await db.commit()
    return lesson


# ── timeline API 测试 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_timeline_returns_expected_structure(client):
    """GET /api/stats/timeline 应返回正确结构"""
    r = await client.get("/api/stats/timeline")
    assert r.status_code == 200
    data = r.json()
    assert "days" in data
    assert "points" in data
    assert isinstance(data["points"], list)


@pytest.mark.asyncio
async def test_timeline_default_30_days(client):
    """默认返回 30 天数据"""
    r = await client.get("/api/stats/timeline")
    data = r.json()
    assert data["days"] == 30
    assert len(data["points"]) == 30


@pytest.mark.asyncio
async def test_timeline_custom_days(client):
    """支持 ?days=7 参数"""
    r = await client.get("/api/stats/timeline?days=7")
    data = r.json()
    assert data["days"] == 7
    assert len(data["points"]) == 7


@pytest.mark.asyncio
async def test_timeline_point_structure(client):
    """每个 point 应包含 date, tasks_created, tasks_completed, lessons_added, net_biomass"""
    r = await client.get("/api/stats/timeline?days=3")
    data = r.json()
    for point in data["points"]:
        assert "date" in point
        assert "tasks_created" in point
        assert "tasks_completed" in point
        assert "lessons_added" in point
        assert "net_biomass" in point


@pytest.mark.asyncio
async def test_timeline_counts_tasks(db_session, client):
    """正确统计各天创建的任务数"""
    await _create_task_at(db_session, days_ago=0)  # 今天
    await _create_task_at(db_session, days_ago=0)  # 今天再一个
    await _create_task_at(db_session, days_ago=2)  # 2天前

    r = await client.get("/api/stats/timeline?days=7")
    data = r.json()

    # 找今天的 point
    today_points = [p for p in data["points"] if p["tasks_created"] > 0]
    total_created = sum(p["tasks_created"] for p in data["points"])
    assert total_created == 3


@pytest.mark.asyncio
async def test_timeline_counts_completed_tasks(db_session, client):
    """正确统计完成任务数"""
    await _create_task_at(db_session, days_ago=1, state="Complete")
    await _create_task_at(db_session, days_ago=1, state="Complete")
    await _create_task_at(db_session, days_ago=1, state="Incubating")

    r = await client.get("/api/stats/timeline?days=7")
    data = r.json()
    total_completed = sum(p["tasks_completed"] for p in data["points"])
    assert total_completed == 2


@pytest.mark.asyncio
async def test_timeline_counts_lessons(db_session, client):
    """正确统计经验条数"""
    await _create_lesson_at(db_session, days_ago=0)
    await _create_lesson_at(db_session, days_ago=0)
    await _create_lesson_at(db_session, days_ago=3)

    r = await client.get("/api/stats/timeline?days=7")
    data = r.json()
    total_lessons = sum(p["lessons_added"] for p in data["points"])
    assert total_lessons == 3


@pytest.mark.asyncio
async def test_timeline_net_biomass_is_cumulative(db_session, client):
    """net_biomass 是累计完成任务数（不递减）"""
    await _create_task_at(db_session, days_ago=2, state="Complete")
    await _create_task_at(db_session, days_ago=1, state="Complete")

    r = await client.get("/api/stats/timeline?days=5")
    data = r.json()
    points = data["points"]
    # net_biomass 应单调不递减
    for i in range(1, len(points)):
        assert points[i]["net_biomass"] >= points[i-1]["net_biomass"]


@pytest.mark.asyncio
async def test_timeline_days_clamped(client):
    """days 参数边界：最小 1，最大 90（FastAPI Query 校验返回 422）"""
    r1 = await client.get("/api/stats/timeline?days=0")
    assert r1.status_code == 422

    r2 = await client.get("/api/stats/timeline?days=91")
    assert r2.status_code == 422


@pytest.mark.asyncio
async def test_evolution_status_in_overview(client):
    """GET /api/evolution/status 应正确聚合域统计"""
    # 先写入经验
    await client.post("/api/lessons", json={"domain": "coding", "content": "经验1", "outcome": "success"})
    await client.post("/api/lessons", json={"domain": "coding", "content": "经验2", "outcome": "failure"})

    r = await client.get("/api/evolution/status")
    assert r.status_code == 200
    data = r.json()
    assert "threshold" in data
    assert "domains" in data
    coding_domain = next((d for d in data["domains"] if d["domain"] == "coding"), None)
    assert coding_domain is not None
    assert coding_domain["total"] == 2
    assert coding_domain["success_count"] == 1
