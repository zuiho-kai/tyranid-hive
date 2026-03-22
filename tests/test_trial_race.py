"""Trial Race 赛马机制测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from greyfield_hive.main import app
from greyfield_hive.db import engine, Base
from greyfield_hive.services.trial_race import (
    TrialRaceService,
    TrialResult,
    SynapseResult,
    _pick_winner,
)


# ── 数据库 fixture ────────────────────────────────────────

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


# ── _pick_winner ──────────────────────────────────────────

def test_pick_winner_a_success_b_failure():
    a = SynapseResult("code-expert",    0, "done", "", True)
    b = SynapseResult("research-analyst", 1, "",   "error", False)
    assert _pick_winner(a, b) == "code-expert"

def test_pick_winner_b_success_a_failure():
    a = SynapseResult("code-expert",    1, "", "error", False)
    b = SynapseResult("research-analyst", 0, "done", "", True)
    assert _pick_winner(a, b) == "research-analyst"

def test_pick_winner_both_fail():
    a = SynapseResult("code-expert",    1, "", "err", False)
    b = SynapseResult("research-analyst", 1, "", "err", False)
    assert _pick_winner(a, b) is None

def test_pick_winner_both_success_longer_stdout_wins():
    a = SynapseResult("code-expert",    0, "短", "", True)
    b = SynapseResult("research-analyst", 0, "这是一个更长的输出，包含更多信息", "", True)
    assert _pick_winner(a, b) == "research-analyst"

def test_pick_winner_both_success_equal_stdout():
    a = SynapseResult("code-expert",    0, "abc", "", True)
    b = SynapseResult("research-analyst", 0, "xyz", "", True)
    # same length → a wins (>=)
    assert _pick_winner(a, b) == "code-expert"


# ── TrialRaceService ──────────────────────────────────────

@pytest.mark.asyncio
async def test_trial_race_picks_winner():
    """成功的 synapse 应被选为胜者"""
    svc = TrialRaceService()

    async def mock_invoke(synapse, message, task_id, trace_id, timeout=300):
        if synapse == "code-expert":
            return {"returncode": 0, "stdout": "任务完成", "stderr": ""}
        else:
            return {"returncode": 1, "stdout": "", "stderr": "failed"}

    with patch.object(svc._worker, "_invoke_agent", side_effect=mock_invoke), \
         patch.object(svc._worker, "_build_enriched_message", side_effect=lambda s, m, t, d: m), \
         patch.object(svc._worker, "_persist_progress", new_callable=AsyncMock), \
         patch.object(svc._worker, "_write_outcome_lesson", new_callable=AsyncMock):

        result = await svc.run(
            task_id="T001",
            synapse_a="code-expert",
            synapse_b="research-analyst",
            message="实现一个功能",
        )

    assert result.winner == "code-expert"
    assert result.results["code-expert"].success is True
    assert result.results["research-analyst"].success is False


@pytest.mark.asyncio
async def test_trial_race_no_winner_both_fail():
    """双方均失败时 winner 为 None"""
    svc = TrialRaceService()

    async def mock_invoke(synapse, message, task_id, trace_id, timeout=300):
        return {"returncode": 1, "stdout": "", "stderr": "error"}

    with patch.object(svc._worker, "_invoke_agent", side_effect=mock_invoke), \
         patch.object(svc._worker, "_build_enriched_message", side_effect=lambda s, m, t, d: m), \
         patch.object(svc._worker, "_persist_progress", new_callable=AsyncMock), \
         patch.object(svc._worker, "_write_outcome_lesson", new_callable=AsyncMock):

        result = await svc.run(
            task_id="T002",
            synapse_a="code-expert",
            synapse_b="research-analyst",
            message="实现功能",
        )

    assert result.winner is None


@pytest.mark.asyncio
async def test_trial_race_writes_lesson_for_winner():
    """胜者应触发 _write_outcome_lesson"""
    svc = TrialRaceService()

    async def mock_invoke(synapse, message, task_id, trace_id, timeout=300):
        return {"returncode": 0, "stdout": "完成", "stderr": ""}

    mock_write = AsyncMock()

    with patch.object(svc._worker, "_invoke_agent", side_effect=mock_invoke), \
         patch.object(svc._worker, "_build_enriched_message", side_effect=lambda s, m, t, d: m), \
         patch.object(svc._worker, "_persist_progress", new_callable=AsyncMock), \
         patch.object(svc._worker, "_write_outcome_lesson", mock_write):

        result = await svc.run(
            task_id="T003",
            synapse_a="code-expert",
            synapse_b="research-analyst",
            message="完成任务",
            domain="coding",
        )

    mock_write.assert_called_once()
    call_kwargs = mock_write.call_args.kwargs
    assert call_kwargs["task_id"] == "T003"
    assert call_kwargs["domain"] == "coding"
    assert call_kwargs["synapse"] == result.winner


@pytest.mark.asyncio
async def test_trial_race_persists_both_progress():
    """双方结果都应写入 progress_log"""
    svc = TrialRaceService()

    async def mock_invoke(synapse, message, task_id, trace_id, timeout=300):
        return {"returncode": 0, "stdout": "done", "stderr": ""}

    mock_persist = AsyncMock()

    with patch.object(svc._worker, "_invoke_agent", side_effect=mock_invoke), \
         patch.object(svc._worker, "_build_enriched_message", side_effect=lambda s, m, t, d: m), \
         patch.object(svc._worker, "_persist_progress", mock_persist), \
         patch.object(svc._worker, "_write_outcome_lesson", new_callable=AsyncMock):

        await svc.run(
            task_id="T004",
            synapse_a="code-expert",
            synapse_b="overmind",
            message="测试任务",
        )

    assert mock_persist.call_count == 2
    called_synapses = {c.args[1] for c in mock_persist.call_args_list}
    assert "code-expert" in called_synapses
    assert "overmind" in called_synapses


# ── API 端点 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trial_endpoint_requires_two_synapses(client):
    """synapses 数量不为 2 时应返回 400"""
    r = await client.post("/api/tasks", json={"title": "测试任务"})
    task_id = r.json()["id"]

    r = await client.post(f"/api/tasks/{task_id}/trial", json={
        "synapses": ["code-expert"],
        "message": "做点事",
    })
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_trial_endpoint_404_task(client):
    """任务不存在时应返回 404"""
    r = await client.post("/api/tasks/nonexistent/trial", json={
        "synapses": ["code-expert", "research-analyst"],
        "message": "做点事",
    })
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_trial_endpoint_returns_result(client):
    """正常赛马应返回包含 winner / results 的 JSON"""
    r = await client.post("/api/tasks", json={"title": "赛马测试"})
    task_id = r.json()["id"]

    mock_result_a = {"returncode": 0, "stdout": "代码专家完成任务，输出内容丰富", "stderr": ""}
    mock_result_b = {"returncode": 1, "stdout": "", "stderr": "failed"}

    async def mock_invoke(synapse, message, task_id, trace_id, timeout=300):
        return mock_result_a if synapse == "code-expert" else mock_result_b

    with patch(
        "greyfield_hive.services.trial_race.DispatchWorker._invoke_agent",
        side_effect=mock_invoke,
    ), patch(
        "greyfield_hive.services.trial_race.DispatchWorker._build_enriched_message",
        side_effect=lambda s, m, t, d: m,
    ), patch(
        "greyfield_hive.services.trial_race.DispatchWorker._persist_progress",
        new_callable=AsyncMock,
    ), patch(
        "greyfield_hive.services.trial_race.DispatchWorker._write_outcome_lesson",
        new_callable=AsyncMock,
    ):
        r = await client.post(f"/api/tasks/{task_id}/trial", json={
            "synapses": ["code-expert", "research-analyst"],
            "message": "实现功能 X",
        })

    assert r.status_code == 200
    data = r.json()
    assert data["task_id"] == task_id
    assert data["winner"] == "code-expert"
    assert "code-expert" in data["results"]
    assert "research-analyst" in data["results"]
    assert data["results"]["code-expert"]["success"] is True
    assert data["results"]["research-analyst"]["success"] is False
