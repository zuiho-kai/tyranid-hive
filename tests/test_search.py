"""任务全文搜索测试 —— GET /api/tasks?q=keyword"""

import pytest
from httpx import AsyncClient, ASGITransport

from greyfield_hive.main import app
from greyfield_hive.db import engine, Base


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


# ── 数据准备辅助 ────────────────────────────────────────────────────────

async def _seed(client, tasks: list[dict]) -> list[dict]:
    created = []
    for t in tasks:
        r = await client.post("/api/tasks", json=t)
        assert r.status_code == 201
        created.append(r.json())
    return created


# ── 搜索 title ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_by_title_exact_word(client):
    """关键词匹配 title 中的词"""
    await _seed(client, [
        {"title": "修复登录 bug", "description": ""},
        {"title": "实现支付功能", "description": ""},
        {"title": "修复注册流程", "description": ""},
    ])
    resp = await client.get("/api/tasks?q=修复")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 2
    titles = {t["title"] for t in results}
    assert "修复登录 bug" in titles
    assert "修复注册流程" in titles


@pytest.mark.asyncio
async def test_search_by_title_case_insensitive(client):
    """大小写不敏感搜索"""
    await _seed(client, [
        {"title": "Deploy to Production"},
        {"title": "Write Tests"},
    ])
    resp = await client.get("/api/tasks?q=deploy")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["title"] == "Deploy to Production"


# ── 搜索 description ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_by_description(client):
    """关键词匹配 description"""
    await _seed(client, [
        {"title": "战团A", "description": "需要修复数据库连接池泄漏"},
        {"title": "战团B", "description": "优化前端渲染性能"},
    ])
    resp = await client.get("/api/tasks?q=数据库")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["title"] == "战团A"


@pytest.mark.asyncio
async def test_search_matches_title_or_description(client):
    """关键词在 title 或 description 任一匹配均返回"""
    await _seed(client, [
        {"title": "安全审计", "description": "检查认证漏洞"},
        {"title": "性能测试", "description": "安全相关的压测"},
        {"title": "UI 改版", "description": "用户界面优化"},
    ])
    resp = await client.get("/api/tasks?q=安全")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 2
    titles = {t["title"] for t in results}
    assert "安全审计" in titles
    assert "性能测试" in titles


# ── 搜索 id ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_by_task_id_prefix(client):
    """可以用任务 ID 的一部分搜索"""
    created = await _seed(client, [{"title": "测试战团"}])
    task_id = created[0]["id"]
    # 用 ID 的后 6 位搜索
    suffix = task_id[-6:]
    resp = await client.get(f"/api/tasks?q={suffix}")
    assert resp.status_code == 200
    results = resp.json()
    assert any(t["id"] == task_id for t in results)


# ── 无结果 ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_no_match_returns_empty(client):
    """无匹配时返回空列表"""
    await _seed(client, [{"title": "战团A"}, {"title": "战团B"}])
    resp = await client.get("/api/tasks?q=完全不存在的词汇xyz")
    assert resp.status_code == 200
    assert resp.json() == []


# ── 组合过滤 ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_combined_with_state_filter(client):
    """q + state 组合过滤"""
    created = await _seed(client, [
        {"title": "修复生产bug"},
        {"title": "修复测试bug"},
    ])
    # 手动流转第一个任务到 Planning
    await client.post(
        f"/api/tasks/{created[0]['id']}/transition",
        json={"new_state": "Planning", "agent": "test"},
    )
    resp = await client.get("/api/tasks?q=修复&state=Planning")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["state"] == "Planning"
    assert "修复" in results[0]["title"]


@pytest.mark.asyncio
async def test_search_combined_with_priority_filter(client):
    """q + priority 组合过滤"""
    await _seed(client, [
        {"title": "高优任务", "priority": "high"},
        {"title": "高优任务2", "priority": "normal"},
    ])
    resp = await client.get("/api/tasks?q=高优&priority=high")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["priority"] == "high"


# ── 边界情况 ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_empty_q_returns_all(client):
    """空 q 参数等效于不过滤"""
    await _seed(client, [{"title": "战团A"}, {"title": "战团B"}, {"title": "战团C"}])
    resp = await client.get("/api/tasks?q=")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_search_whitespace_q_returns_all(client):
    """空白 q 不触发搜索（API 侧 falsy 判断）"""
    await _seed(client, [{"title": "战团A"}, {"title": "战团B"}])
    resp = await client.get("/api/tasks?q=  ")
    # 空格字符串 falsy → 返回全部
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_search_partial_word_match(client):
    """子串匹配（LIKE %keyword%）"""
    await _seed(client, [
        {"title": "优化数据库查询性能"},
        {"title": "数据分析报告"},
        {"title": "纯 UI 改版"},
    ])
    resp = await client.get("/api/tasks?q=数据")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 2
