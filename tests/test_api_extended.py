"""扩展 API 测试 —— 覆盖 lessons / playbooks / synapse-detail / events / config_loader"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from greyfield_hive.main import app
from greyfield_hive.db import init_db, engine, Base
from greyfield_hive.config_loader import (
    load_synapse_config,
    load_gene,
    list_synapse_names,
)


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


# ── config_loader ──────────────────────────────────────────────────────────────

def test_list_synapse_names_includes_all():
    names = list_synapse_names()
    assert "overmind" in names
    assert "evolution-master" in names
    assert "code-expert" in names
    assert "research-analyst" in names
    assert "finance-scout" in names


def test_load_synapse_config_overmind():
    cfg = load_synapse_config("overmind")
    assert cfg is not None
    assert cfg["name"] == "overmind"
    assert cfg["tier"] == 1
    assert "planning" in cfg["domains"]


def test_load_synapse_config_missing_returns_none():
    assert load_synapse_config("no-such-synapse") is None


def test_load_gene_l2_overmind():
    gene = load_gene("L2_synapse_overmind")
    assert gene is not None
    assert "system_prompt" in gene


def test_load_gene_l2_all_present():
    for gid in ["L2_synapse_overmind", "L2_synapse_evolution", "L2_synapse_code",
                "L2_synapse_research", "L2_synapse_finance"]:
        g = load_gene(gid)
        assert g is not None, f"基因 {gid} 未找到"
        assert "system_prompt" in g


def test_load_gene_unknown_returns_none():
    assert load_gene("L2_no_such_gene") is None
    assert load_gene("L3_something") is None


# ── /api/synapses ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_synapse_list_has_tier(client):
    resp = await client.get("/api/synapses")
    assert resp.status_code == 200
    by_id = {s["id"]: s for s in resp.json()}
    # overmind 的 YAML 配置里 tier=1
    assert by_id["overmind"]["tier"] == 1


@pytest.mark.asyncio
async def test_synapse_detail_includes_config(client):
    resp = await client.get("/api/synapses/overmind")
    assert resp.status_code == 200
    data = resp.json()
    assert "config" in data
    assert data["config"]["tier"] == 1


@pytest.mark.asyncio
async def test_synapse_detail_includes_gene(client):
    resp = await client.get("/api/synapses/overmind")
    data = resp.json()
    assert "gene" in data
    assert "system_prompt" in data["gene"]


@pytest.mark.asyncio
async def test_synapse_detail_not_found(client):
    resp = await client.get("/api/synapses/ghost-synapse")
    assert resp.status_code == 404


# ── /api/lessons ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_and_list_lesson(client):
    resp = await client.post("/api/lessons", json={
        "domain": "code",
        "tags": ["python", "test"],
        "outcome": "success",
        "content": "asyncio 测试中使用文件型 SQLite 避免连接隔离问题",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["domain"] == "code"
    assert data["outcome"] == "success"

    list_resp = await client.get("/api/lessons")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


@pytest.mark.asyncio
async def test_list_lessons_filter_by_domain(client):
    await client.post("/api/lessons", json={"domain": "code", "outcome": "success", "content": "代码经验"})
    await client.post("/api/lessons", json={"domain": "finance", "outcome": "failure", "content": "财务教训"})

    resp = await client.get("/api/lessons?domain=code")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["domain"] == "code"


@pytest.mark.asyncio
async def test_search_lessons_get(client):
    await client.post("/api/lessons", json={"domain": "code", "tags": ["debug"], "outcome": "success", "content": "调试经验"})
    resp = await client.get("/api/lessons/search?query=debug&domain=code")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_delete_lesson(client):
    create = await client.post("/api/lessons", json={"domain": "code", "outcome": "success", "content": "临时测试"})
    lid = create.json()["id"]
    resp = await client.delete(f"/api/lessons/{lid}")
    assert resp.status_code == 204

    list_resp = await client.get("/api/lessons")
    assert all(l["id"] != lid for l in list_resp.json())


# ── /api/playbooks ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_and_list_playbook(client):
    resp = await client.post("/api/playbooks", json={
        "slug": "test-playbook",
        "title": "测试手册",
        "domain": "code",
        "content": "## 步骤\n1. 先读代码\n2. 再改\n3. 写测试",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "test-playbook"
    assert data["version"] == 1
    assert data["is_active"] is True

    list_resp = await client.get("/api/playbooks")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


@pytest.mark.asyncio
async def test_playbook_new_version_via_api(client):
    await client.post("/api/playbooks", json={
        "slug": "evolving-playbook", "title": "进化手册", "domain": "research", "content": "v1内容"
    })
    resp = await client.post("/api/playbooks/slug/evolving-playbook/versions", json={"content": "v2内容"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["version"] == 2
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_playbook_record_usage_via_api(client):
    create = await client.post("/api/playbooks", json={
        "slug": "usage-playbook", "title": "使用手册", "domain": "code", "content": "内容"
    })
    pb_id = create.json()["id"]
    resp = await client.post(f"/api/playbooks/{pb_id}/usage", json={"success": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["use_count"] == 1
    assert data["success_rate"] > 0


@pytest.mark.asyncio
async def test_playbook_filter_by_domain(client):
    await client.post("/api/playbooks", json={"slug": "p-code", "title": "代码手册", "domain": "code", "content": "c"})
    await client.post("/api/playbooks", json={"slug": "p-finance", "title": "财务手册", "domain": "finance", "content": "f"})
    resp = await client.get("/api/playbooks?domain=code")
    items = resp.json()
    assert all(p["domain"] == "code" for p in items)


# ── /api/events ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_events_endpoint(client):
    resp = await client.get("/api/events")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_events_after_task_create(client):
    await client.post("/api/tasks", json={"title": "触发事件战团"})
    resp = await client.get("/api/events")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) >= 1
    # HTTP events API 与 WS BusEvent 对齐：使用 event_id 字段
    assert "event_id" in events[0]
    topics = [e["topic"] for e in events]
    assert any("task" in t for t in topics)


# ── PATCH /api/tasks/{id} ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_task_title(client):
    create = await client.post("/api/tasks", json={"title": "原始标题", "priority": "normal"})
    task_id = create.json()["id"]
    resp = await client.patch(f"/api/tasks/{task_id}", json={"title": "更新后标题"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "更新后标题"
    assert resp.json()["priority"] == "normal"  # 未更新的字段保持不变


@pytest.mark.asyncio
async def test_patch_task_priority(client):
    create = await client.post("/api/tasks", json={"title": "战团", "priority": "normal"})
    task_id = create.json()["id"]
    resp = await client.patch(f"/api/tasks/{task_id}", json={"priority": "critical"})
    assert resp.status_code == 200
    assert resp.json()["priority"] == "critical"
    assert resp.json()["title"] == "战团"  # title 未变


@pytest.mark.asyncio
async def test_patch_task_not_found(client):
    resp = await client.patch("/api/tasks/NO-SUCH-TASK", json={"title": "x"})
    assert resp.status_code == 404


# ── events 字段对齐 ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_events_have_event_id_not_id(client):
    """HTTP events API 必须返回 event_id（与 WS BusEvent 字段对齐）"""
    await client.post("/api/tasks", json={"title": "事件对齐测试"})
    resp = await client.get("/api/events")
    events = resp.json()
    assert len(events) >= 1
    for e in events:
        assert "event_id" in e
        assert "id" not in e   # 旧字段不应出现
