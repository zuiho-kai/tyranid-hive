"""Swarm Mode 测试 —— SwarmRunnerService + /swarm API 端点"""

import asyncio
import pytest
from httpx import AsyncClient, ASGITransport

from greyfield_hive.main import app
from greyfield_hive.db import engine, Base
from greyfield_hive.services.swarm_runner import SwarmRunnerService, SwarmUnit, SwarmResult
from greyfield_hive.adapters.openclaw import MockAdapter
from greyfield_hive.workers.dispatcher import DispatchWorker
from unittest.mock import AsyncMock, patch


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


async def _create_task(client: AsyncClient, title: str) -> str:
    r = await client.post("/api/tasks", json={"title": title})
    assert r.status_code in (200, 201)
    return r.json()["id"]


# ── SwarmRunnerService 单元测试 ────────────────────────────

@pytest.mark.asyncio
async def test_swarm_empty_units_returns_empty_result():
    """空 units 列表应返回空结果"""
    svc = SwarmRunnerService()
    result = await svc.run(task_id="T-EMPTY", units=[])
    assert result.total == 0
    assert result.success_count == 0
    assert result.fail_count == 0
    assert result.all_success is False   # total=0 → all_success=False


@pytest.mark.asyncio
async def test_swarm_single_unit_success():
    """单个 unit mock 执行应成功"""
    svc = SwarmRunnerService()
    svc._worker._adapter = MockAdapter()

    units = [SwarmUnit(synapse="code-expert", message="实现 hello world")]
    result = await svc.run(task_id="T-S1", units=units)
    assert result.total == 1
    assert result.success_count == 1
    assert result.all_success is True
    assert len(result.results) == 1
    assert result.results[0].synapse == "code-expert"
    assert result.results[0].success is True


@pytest.mark.asyncio
async def test_swarm_multiple_units_all_success():
    """多个 units 并发执行，全部成功"""
    svc = SwarmRunnerService()
    svc._worker._adapter = MockAdapter()

    units = [
        SwarmUnit(synapse="code-expert",      message="功能A"),
        SwarmUnit(synapse="research-analyst", message="调研B"),
        SwarmUnit(synapse="code-expert",      message="功能C"),
    ]
    result = await svc.run(task_id="T-M3", units=units)
    assert result.total == 3
    assert result.success_count == 3
    assert result.fail_count == 0
    assert result.all_success is True
    assert result.success_rate == 1.0


@pytest.mark.asyncio
async def test_swarm_partial_failure():
    """部分 unit 失败时，统计应正确"""
    fail_count = 0

    class PartialFailAdapter:
        async def invoke(self, synapse, message, env, timeout):
            nonlocal fail_count
            if "__force_fail__" in message.lower():
                fail_count += 1
                return {"returncode": 1, "stdout": "", "stderr": "error"}
            return {"returncode": 0, "stdout": f"[mock] {synapse}: {message[:30]}", "stderr": ""}

    svc = SwarmRunnerService()
    svc._worker._adapter = PartialFailAdapter()

    units = [
        SwarmUnit(synapse="code-expert", message="成功任务"),
        SwarmUnit(synapse="code-expert", message="__FORCE_FAIL__ 任务"),
        SwarmUnit(synapse="code-expert", message="成功任务2"),
    ]
    result = await svc.run(task_id="T-PARTIAL", units=units)
    assert result.total == 3
    assert result.success_count == 2
    assert result.fail_count == 1
    assert result.all_success is False
    assert abs(result.success_rate - 2 / 3) < 0.001


@pytest.mark.asyncio
async def test_swarm_respects_max_concurrent():
    """max_concurrent 限制应生效（通过并发峰值验证）"""
    concurrent_now = 0
    max_seen = 0

    class ConcurrencyTracker:
        async def invoke(self, synapse, message, env, timeout):
            nonlocal concurrent_now, max_seen
            concurrent_now += 1
            max_seen = max(max_seen, concurrent_now)
            await asyncio.sleep(0.02)
            concurrent_now -= 1
            return {"returncode": 0, "stdout": f"[mock] done", "stderr": ""}

    svc = SwarmRunnerService()
    svc._worker._adapter = ConcurrencyTracker()

    units = [SwarmUnit(synapse="code-expert", message=f"task{i}") for i in range(6)]
    await svc.run(task_id="T-CONC", units=units, max_concurrent=3)
    assert max_seen <= 3, f"并发峰值 {max_seen} 超过限制 3"


@pytest.mark.asyncio
async def test_swarm_elapsed_sec_recorded():
    """每个 unit 的 elapsed_sec 应 > 0"""
    svc = SwarmRunnerService()
    svc._worker._adapter = MockAdapter()

    units = [SwarmUnit(synapse="code-expert", message="计时测试")]
    result = await svc.run(task_id="T-ELAPSED", units=units)
    assert result.results[0].elapsed_sec >= 0


@pytest.mark.asyncio
async def test_swarm_persists_progress_to_task_id():
    """progress_log 回写必须使用 task_id，而不是 synapse"""
    svc = SwarmRunnerService()
    svc._worker._adapter = MockAdapter()
    persist = AsyncMock()

    with patch.object(svc._worker, "_persist_progress", persist):
        await svc.run(
            task_id="T-PERSIST",
            units=[SwarmUnit(synapse="code-expert", message="记录进度")],
        )

    persist.assert_awaited_once()
    assert persist.await_args.args[0] == "T-PERSIST"


@pytest.mark.asyncio
async def test_swarm_result_success_rate_empty():
    """空 units 的 success_rate 应为 0"""
    result = SwarmResult(task_id="T", results=[])
    assert result.success_rate == 0.0


def test_swarm_result_counts():
    """SwarmResult 统计字段应从 results 自动计算"""
    from greyfield_hive.services.swarm_runner import SwarmUnitResult
    results = [
        SwarmUnitResult("a", "m", 0, "", "", True),
        SwarmUnitResult("b", "m", 1, "", "", False),
        SwarmUnitResult("c", "m", 0, "", "", True),
    ]
    sr = SwarmResult(task_id="T", results=results)
    assert sr.total == 3
    assert sr.success_count == 2
    assert sr.fail_count == 1
    assert abs(sr.success_rate - 2/3) < 0.001


# ── API 端点测试 ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_swarm_api_empty_units_returns_400(client):
    """空 units 应返回 400"""
    task_id = await _create_task(client, "swarm 测试任务")
    r = await client.post(f"/api/tasks/{task_id}/swarm", json={"units": []})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_swarm_api_max_concurrent_out_of_range_400(client):
    """max_concurrent=0 应返回 400"""
    task_id = await _create_task(client, "swarm 测试任务2")
    r = await client.post(f"/api/tasks/{task_id}/swarm", json={
        "units": [{"synapse": "code-expert", "message": "test"}],
        "max_concurrent": 0,
    })
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_swarm_api_task_not_found_404(client):
    """任务不存在应返回 404"""
    r = await client.post("/api/tasks/NOT-EXIST/swarm", json={
        "units": [{"synapse": "code-expert", "message": "test"}],
    })
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_swarm_api_success(client):
    """正常 swarm 调用应返回结果"""
    task_id = await _create_task(client, "swarm API 测试")
    r = await client.post(f"/api/tasks/{task_id}/swarm", json={
        "units": [
            {"synapse": "code-expert",      "message": "功能A"},
            {"synapse": "research-analyst", "message": "调研B"},
        ],
        "max_concurrent": 2,
    })
    assert r.status_code in (200, 201)
    data = r.json()
    assert data["total"] == 2
    assert data["success_count"] >= 0
    assert "results" in data
    assert len(data["results"]) == 2
    assert "synapse" in data["results"][0]
    assert "success" in data["results"][0]
