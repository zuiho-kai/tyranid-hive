"""基因库 PATCH 测试 —— Lesson 更新 + Playbook 更新/归档/激活"""

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


# ── Lesson helpers ────────────────────────────────────────────────────────

async def _add_lesson(client, domain="coding", content="原始内容", outcome="success") -> dict:
    r = await client.post("/api/lessons", json={
        "domain": domain, "content": content, "outcome": outcome, "tags": ["tag1"],
    })
    assert r.status_code == 201
    return r.json()


# ── PATCH /api/lessons/{id} ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_lesson_content(client):
    """更新 lesson content"""
    lesson = await _add_lesson(client)
    r = await client.patch(f"/api/lessons/{lesson['id']}", json={"content": "修正后内容"})
    assert r.status_code == 200
    assert r.json()["content"] == "修正后内容"


@pytest.mark.asyncio
async def test_patch_lesson_outcome(client):
    """更新 lesson outcome"""
    lesson = await _add_lesson(client, outcome="unknown")
    r = await client.patch(f"/api/lessons/{lesson['id']}", json={"outcome": "failure"})
    assert r.status_code == 200
    assert r.json()["outcome"] == "failure"


@pytest.mark.asyncio
async def test_patch_lesson_domain(client):
    """更新 lesson domain"""
    lesson = await _add_lesson(client, domain="infra")
    r = await client.patch(f"/api/lessons/{lesson['id']}", json={"domain": "security"})
    assert r.status_code == 200
    assert r.json()["domain"] == "security"


@pytest.mark.asyncio
async def test_patch_lesson_tags(client):
    """更新 lesson tags（API 以逗号分隔字符串存储）"""
    lesson = await _add_lesson(client)
    r = await client.patch(f"/api/lessons/{lesson['id']}", json={"tags": ["new", "tags"]})
    assert r.status_code == 200
    # tags 在 DB 中以逗号分隔字符串存储
    assert r.json()["tags"] == "new,tags"


@pytest.mark.asyncio
async def test_patch_lesson_partial_only_changes_specified_fields(client):
    """部分更新只改指定字段"""
    lesson = await _add_lesson(client, domain="coding", content="原始内容", outcome="success")
    r = await client.patch(f"/api/lessons/{lesson['id']}", json={"content": "新内容"})
    data = r.json()
    assert data["content"] == "新内容"
    assert data["domain"] == "coding"     # 未改
    assert data["outcome"] == "success"   # 未改


@pytest.mark.asyncio
async def test_patch_lesson_not_found(client):
    """更新不存在的 lesson 返回 404"""
    r = await client.patch("/api/lessons/不存在的ID", json={"content": "x"})
    assert r.status_code == 404


# ── Playbook helpers ──────────────────────────────────────────────────────

async def _create_pb(client, slug="test-pb", title="测试手册", domain="coding") -> dict:
    r = await client.post("/api/playbooks", json={
        "slug": slug, "domain": domain, "title": title, "content": "原始内容",
    })
    assert r.status_code == 201
    return r.json()


# ── PATCH /api/playbooks/{pb_id} ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_playbook_title(client):
    """更新 playbook title"""
    pb = await _create_pb(client)
    r = await client.patch(f"/api/playbooks/{pb['id']}", json={"title": "新标题"})
    assert r.status_code == 200
    assert r.json()["title"] == "新标题"


@pytest.mark.asyncio
async def test_patch_playbook_content(client):
    """更新 playbook content"""
    pb = await _create_pb(client)
    r = await client.patch(f"/api/playbooks/{pb['id']}", json={"content": "更新后的手册内容"})
    assert r.status_code == 200
    assert r.json()["content"] == "更新后的手册内容"


@pytest.mark.asyncio
async def test_patch_playbook_domain(client):
    """更新 playbook domain"""
    pb = await _create_pb(client, domain="coding")
    r = await client.patch(f"/api/playbooks/{pb['id']}", json={"domain": "devops"})
    assert r.status_code == 200
    assert r.json()["domain"] == "devops"


@pytest.mark.asyncio
async def test_patch_playbook_not_found(client):
    """更新不存在的 playbook 返回 404"""
    r = await client.patch("/api/playbooks/不存在的ID", json={"title": "x"})
    assert r.status_code == 404


# ── POST /api/playbooks/{pb_id}/deactivate ────────────────────────────────

@pytest.mark.asyncio
async def test_deactivate_playbook(client):
    """归档后 is_active 变为 False"""
    pb = await _create_pb(client)
    assert pb["is_active"] is True
    r = await client.post(f"/api/playbooks/{pb['id']}/deactivate")
    assert r.status_code == 200
    assert r.json()["is_active"] is False


@pytest.mark.asyncio
async def test_deactivate_removes_from_active_list(client):
    """归档后不出现在活跃列表中"""
    pb = await _create_pb(client, slug="to-deactivate")
    await client.post(f"/api/playbooks/{pb['id']}/deactivate")
    r = await client.get("/api/playbooks")
    ids = [p["id"] for p in r.json()]
    assert pb["id"] not in ids


@pytest.mark.asyncio
async def test_deactivate_not_found(client):
    """归档不存在的 playbook 返回 404"""
    r = await client.post("/api/playbooks/不存在的ID/deactivate")
    assert r.status_code == 404


# ── POST /api/playbooks/{pb_id}/activate ─────────────────────────────────

@pytest.mark.asyncio
async def test_activate_playbook(client):
    """归档后重新激活 is_active 变回 True"""
    pb = await _create_pb(client)
    await client.post(f"/api/playbooks/{pb['id']}/deactivate")
    r = await client.post(f"/api/playbooks/{pb['id']}/activate")
    assert r.status_code == 200
    assert r.json()["is_active"] is True


@pytest.mark.asyncio
async def test_activate_reappears_in_list(client):
    """重新激活后出现在活跃列表中"""
    pb = await _create_pb(client, slug="re-activate-test")
    await client.post(f"/api/playbooks/{pb['id']}/deactivate")
    await client.post(f"/api/playbooks/{pb['id']}/activate")
    r = await client.get("/api/playbooks")
    ids = [p["id"] for p in r.json()]
    assert pb["id"] in ids


@pytest.mark.asyncio
async def test_activate_not_found(client):
    """激活不存在的 playbook 返回 404"""
    r = await client.post("/api/playbooks/不存在的ID/activate")
    assert r.status_code == 404
