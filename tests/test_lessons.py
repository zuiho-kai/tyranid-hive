"""Lessons Bank 测试"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from greyfield_hive.main import app
from greyfield_hive.db import engine, Base
from greyfield_hive.services.lessons_bank import LessonsBank, DecayRetrievalStrategy
from greyfield_hive.db import SessionLocal


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


# ── 单元测试：衰减公式 ─────────────────────────────────────

def test_decay_score_domain_exact():
    from greyfield_hive.models.lesson import Lesson
    from datetime import datetime, timezone
    strategy = DecayRetrievalStrategy()
    lesson = Lesson(domain="code", tags="python,debug", frequency=5, last_used=datetime.now(timezone.utc))
    score = strategy._score(lesson, "code", ["python"])
    assert score > 1.0  # domain_match=3.0, 命中标签


def test_decay_score_parent_domain():
    from greyfield_hive.models.lesson import Lesson
    from datetime import datetime, timezone
    strategy = DecayRetrievalStrategy()
    lesson = Lesson(domain="code", tags="", frequency=0, last_used=datetime.now(timezone.utc))
    score_child = strategy._score(lesson, "code/python", [])
    score_other = strategy._score(lesson, "finance", [])
    assert score_child > score_other  # 父域命中(2.0) > 无关(1.0)


def test_decay_score_new_lesson_nonzero():
    from greyfield_hive.models.lesson import Lesson
    from datetime import datetime, timezone
    strategy = DecayRetrievalStrategy()
    lesson = Lesson(domain="code", tags="", frequency=0, last_used=datetime.now(timezone.utc))
    score = strategy._score(lesson, "code", [])
    assert score > 0  # (1 + log(1+0)) = 1.0，不为零


# ── API 集成测试 ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_lesson(client):
    resp = await client.post("/api/lessons", json={
        "domain": "code",
        "content": "调用 API 时需要加超时参数，否则会无限等待",
        "outcome": "failure",
        "tags": ["api", "timeout"],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["domain"] == "code"
    assert data["outcome"] == "failure"
    assert data["frequency"] == 0


@pytest.mark.asyncio
async def test_search_lessons(client):
    # 写入两条
    await client.post("/api/lessons", json={"domain": "code", "content": "Python 超时", "outcome": "failure", "tags": ["python"]})
    await client.post("/api/lessons", json={"domain": "finance", "content": "股票数据格式", "outcome": "success", "tags": ["stock"]})

    resp = await client.post("/api/lessons/search", json={"domain": "code", "tags": ["python"], "top_k": 5})
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    # code 域的应该排在前面
    assert results[0]["domain"] == "code"


@pytest.mark.asyncio
async def test_frequency_increments_on_search(client):
    add = await client.post("/api/lessons", json={"domain": "code", "content": "test", "outcome": "success"})
    lesson_id = add.json()["id"]

    await client.post("/api/lessons/search", json={"domain": "code", "top_k": 5})

    get = await client.get(f"/api/lessons/{lesson_id}")
    assert get.json()["frequency"] == 1


@pytest.mark.asyncio
async def test_purge_expired(client):
    from datetime import datetime, timezone, timedelta
    # 写入一条，然后直接测 API（不手动修改时间）
    await client.post("/api/lessons", json={"domain": "code", "content": "old", "outcome": "success"})
    resp = await client.delete("/api/lessons/expired?days=365")
    assert resp.status_code == 200
    # 新写的未过期，应该删 0 条
    assert resp.json()["deleted"] == 0
