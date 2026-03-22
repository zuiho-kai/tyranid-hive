"""自动结晶测试 —— record_usage 触发 + auto-crystallize 扫描端点"""

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


# ── 辅助 ─────────────────────────────────────────────────────────────────

async def _create_pb(client, slug="pb-test", domain="coding", title="手册") -> dict:
    r = await client.post("/api/playbooks", json={
        "slug": slug, "domain": domain, "title": title,
        "content": "手册内容",
    })
    assert r.status_code == 201
    return r.json()


async def _record(client, pb_id: str, success: bool) -> dict:
    r = await client.post(f"/api/playbooks/{pb_id}/usage", json={"success": success})
    assert r.status_code == 200
    return r.json()


# ── record_usage 自动结晶（use_count 阈值 = 10，success_rate ≥ 0.8）─────

@pytest.mark.asyncio
async def test_record_usage_no_auto_crystallize_below_threshold(client):
    """use_count < 10 时不应自动结晶"""
    pb = await _create_pb(client)
    # 连续成功记录 9 次（EMA 收敛后 success_rate 会高，但 use_count 仍 <10）
    for _ in range(9):
        await _record(client, pb["id"], True)
    r = await client.get(f"/api/playbooks/{pb['id']}")
    assert r.json()["crystallized"] is False
    assert r.json()["use_count"] == 9


@pytest.mark.asyncio
async def test_record_usage_auto_crystallize_on_threshold(client):
    """use_count 达到 10 且 success_rate ≥ 0.8 时自动结晶"""
    pb = await _create_pb(client)
    # 足够多次成功，让 success_rate 收敛到高值
    for _ in range(20):
        data = await _record(client, pb["id"], True)
    assert data["use_count"] == 20
    assert data["crystallized"] is True
    assert data["success_rate"] >= 0.8


@pytest.mark.asyncio
async def test_record_usage_no_auto_crystallize_low_success_rate(client):
    """use_count 足够但 success_rate 低时不应自动结晶"""
    pb = await _create_pb(client)
    # 全部失败 —— success_rate 接近 0
    for _ in range(15):
        data = await _record(client, pb["id"], False)
    assert data["crystallized"] is False
    assert data["success_rate"] < 0.8


@pytest.mark.asyncio
async def test_record_usage_already_crystallized_stays_true(client):
    """已结晶的 Playbook 再次 record_usage 后 crystallized 仍为 True"""
    pb = await _create_pb(client)
    for _ in range(20):
        await _record(client, pb["id"], True)
    # 再记录一次
    data = await _record(client, pb["id"], True)
    assert data["crystallized"] is True


@pytest.mark.asyncio
async def test_record_usage_crystallize_when_both_thresholds_met(client):
    """use_count >= 10 且 success_rate >= 0.8 同时满足时结晶

    EMA alpha=0.1，全成功时 success_rate 收敛需 ~16 次才达 0.8。
    在第 16 次之前 use_count 已 >=10 但 success_rate 不足，
    在第 16 次时两个条件同时满足，触发结晶。
    """
    pb = await _create_pb(client)
    # 前 15 次全成功：use_count >=10，但 success_rate ~0.79 < 0.8
    for i in range(15):
        d = await _record(client, pb["id"], True)
    # EMA 15 次后约 0.79，不满足 >= 0.8
    assert d["crystallized"] is False
    assert d["use_count"] == 15
    # 第 16 次：success_rate 终于超过 0.8（约 0.814），触发结晶
    d = await _record(client, pb["id"], True)
    assert d["use_count"] == 16
    assert d["crystallized"] is True


# ── POST /api/playbooks/auto-crystallize 批量扫描 ─────────────────────────

@pytest.mark.asyncio
async def test_auto_crystallize_empty(client):
    """无 Playbook 时应返回 crystallized=0"""
    r = await client.post("/api/playbooks/auto-crystallize")
    assert r.status_code == 200
    assert r.json()["crystallized"] == 0
    assert r.json()["playbooks"] == []


@pytest.mark.asyncio
async def test_auto_crystallize_scans_eligible(client):
    """满足阈值的 Playbook 应被批量结晶"""
    pb = await _create_pb(client, slug="auto-pb")
    for _ in range(20):
        await _record(client, pb["id"], True)
    # 重置 crystallized=False 来模拟待扫描状态（直接再建一条新手册）
    pb2 = await _create_pb(client, slug="auto-pb2", title="手册2")
    for _ in range(20):
        await _record(client, pb2["id"], True)

    # 注意：上面的 record_usage 已经触发了自动结晶，
    # 所以 auto-crystallize 扫描时不会再次改动（避免重复）
    r = await client.post("/api/playbooks/auto-crystallize")
    assert r.status_code == 200
    assert r.json()["crystallized"] == 0  # 已经结晶了，不重复处理


@pytest.mark.asyncio
async def test_auto_crystallize_custom_threshold(client):
    """可通过参数降低阈值，让低 use_count 的 Playbook 也结晶"""
    pb = await _create_pb(client, slug="low-threshold")
    for _ in range(3):
        await _record(client, pb["id"], True)
    # 默认阈值=10，不会结晶
    assert (await client.get(f"/api/playbooks/{pb['id']}")).json()["crystallized"] is False

    # 用自定义阈值 use_count=3, success_rate=0.2 触发结晶
    # （3 次全成功 EMA ≈ 0.271，>= 0.2 可结晶）
    r = await client.post("/api/playbooks/auto-crystallize?use_count=3&success_rate=0.2")
    assert r.status_code == 200
    data = r.json()
    assert data["crystallized"] == 1
    assert data["playbooks"][0]["id"] == pb["id"]


@pytest.mark.asyncio
async def test_auto_crystallize_skips_inactive(client):
    """已归档的 Playbook（is_active=False）不应被批量结晶"""
    pb = await _create_pb(client, slug="inactive-pb")
    # 先归档
    await client.post(f"/api/playbooks/{pb['id']}/deactivate")
    # 用最低阈值尝试结晶（use_count=1 是允许的最低值）
    r = await client.post("/api/playbooks/auto-crystallize?use_count=1&success_rate=0.0")
    assert r.status_code == 200
    assert r.json()["crystallized"] == 0
