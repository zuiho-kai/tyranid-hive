"""基因库导出/导入 API 测试 —— GET /api/genes/export + POST /api/genes/import"""

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


# ── export ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_empty(client):
    """空库时 export 返回空 lessons + playbooks"""
    r = await client.get("/api/genes/export")
    assert r.status_code == 200
    data = r.json()
    assert data["lessons_count"] == 0
    assert data["playbooks_count"] == 0
    assert data["lessons"] == []
    assert data["playbooks"] == []
    assert "exported_at" in data


@pytest.mark.asyncio
async def test_export_includes_lessons(client):
    """export 包含已创建的 lesson"""
    await client.post("/api/lessons", json={
        "domain": "testing", "content": "内容", "outcome": "success", "tags": ["t1"]
    })
    r = await client.get("/api/genes/export")
    assert r.status_code == 200
    data = r.json()
    assert data["lessons_count"] == 1
    lesson = data["lessons"][0]
    assert lesson["domain"] == "testing"
    assert lesson["content"] == "内容"
    assert lesson["tags"] == ["t1"]


@pytest.mark.asyncio
async def test_export_includes_active_playbooks(client):
    """export 包含 is_active=True 的 playbook"""
    await client.post("/api/playbooks", json={
        "slug": "deploy-guide", "domain": "ops",
        "title": "部署指南", "content": "# 步骤"
    })
    r = await client.get("/api/genes/export")
    assert r.status_code == 200
    data = r.json()
    assert data["playbooks_count"] == 1
    pb = data["playbooks"][0]
    assert pb["slug"] == "deploy-guide"
    assert pb["title"] == "部署指南"


@pytest.mark.asyncio
async def test_export_bundle_structure(client):
    """export bundle 字段齐全"""
    r = await client.get("/api/genes/export")
    data = r.json()
    required_keys = {"exported_at", "lessons_count", "playbooks_count", "lessons", "playbooks"}
    assert required_keys.issubset(data.keys())


# ── import ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_import_empty_bundle(client):
    """空 bundle 导入成功，均为 0"""
    r = await client.post("/api/genes/import", json={"lessons": [], "playbooks": []})
    assert r.status_code == 200
    data = r.json()
    assert data["lessons_added"] == 0
    assert data["playbooks_added"] == 0
    assert data["playbooks_skipped"] == 0


@pytest.mark.asyncio
async def test_import_lessons(client):
    """导入 lessons 全部追加"""
    payload = {
        "lessons": [
            {"domain": "arch", "content": "保持解耦", "outcome": "success", "tags": ["a"]},
            {"domain": "ops",  "content": "先备份",   "outcome": "success", "tags": []},
        ],
        "playbooks": []
    }
    r = await client.post("/api/genes/import", json=payload)
    assert r.status_code == 200
    assert r.json()["lessons_added"] == 2

    # 确认写入数据库
    r2 = await client.get("/api/lessons")
    assert len(r2.json()) == 2


@pytest.mark.asyncio
async def test_import_playbooks_new(client):
    """新 playbook 正常导入"""
    payload = {
        "lessons": [],
        "playbooks": [
            {"slug": "hotfix", "domain": "ops", "title": "紧急修复", "content": "# 步骤"}
        ]
    }
    r = await client.post("/api/genes/import", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["playbooks_added"] == 1
    assert data["playbooks_skipped"] == 0


@pytest.mark.asyncio
async def test_import_playbook_skip_existing_slug(client):
    """slug 已存在时跳过，不重复创建"""
    await client.post("/api/playbooks", json={
        "slug": "hotfix", "domain": "ops", "title": "原标题", "content": "原内容"
    })
    payload = {
        "lessons": [],
        "playbooks": [
            {"slug": "hotfix", "domain": "ops", "title": "新标题", "content": "新内容"}
        ]
    }
    r = await client.post("/api/genes/import", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["playbooks_added"] == 0
    assert data["playbooks_skipped"] == 1

    # 确认原内容未被覆盖
    r2 = await client.get("/api/playbooks/slug/hotfix")
    assert r2.json()["title"] == "原标题"


@pytest.mark.asyncio
async def test_import_mixed(client):
    """混合导入：部分 playbook 新增、部分跳过，lessons 全部追加"""
    await client.post("/api/playbooks", json={
        "slug": "existing", "domain": "d", "title": "已存在", "content": "c"
    })
    payload = {
        "lessons": [
            {"domain": "x", "content": "l1", "outcome": "success"},
            {"domain": "y", "content": "l2", "outcome": "failure"},
        ],
        "playbooks": [
            {"slug": "existing", "domain": "d", "title": "x",     "content": "x"},
            {"slug": "new-one",  "domain": "d", "title": "新的", "content": "c"},
        ]
    }
    r = await client.post("/api/genes/import", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["lessons_added"] == 2
    assert data["playbooks_added"] == 1
    assert data["playbooks_skipped"] == 1


@pytest.mark.asyncio
async def test_export_import_roundtrip(client):
    """export → import 到新实例的往返一致性"""
    # 创建原始数据
    await client.post("/api/lessons", json={
        "domain": "rt", "content": "往返测试", "outcome": "success", "tags": ["rt"]
    })
    await client.post("/api/playbooks", json={
        "slug": "rt-pb", "domain": "rt", "title": "往返手册", "content": "# RT"
    })

    # 导出
    export_r = await client.get("/api/genes/export")
    bundle = export_r.json()

    # 清库
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # 导入
    import_r = await client.post("/api/genes/import", json={
        "lessons": bundle["lessons"],
        "playbooks": bundle["playbooks"]
    })
    assert import_r.status_code == 200
    data = import_r.json()
    assert data["lessons_added"] == 1
    assert data["playbooks_added"] == 1

    # 验证
    lessons_r = await client.get("/api/lessons")
    assert len(lessons_r.json()) == 1
    assert lessons_r.json()[0]["content"] == "往返测试"
