"""Chain Mode 顺序多 Agent 协作测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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


# ── ChainRunnerService 单元测试 ─────────────────────────────

def _make_raw(returncode=0, stdout="完成输出", stderr=""):
    return {"returncode": returncode, "stdout": stdout, "stderr": stderr, "elapsed_sec": 0.1}


@pytest.mark.asyncio
async def test_chain_sequential_order():
    """各阶段按顺序执行，前一阶段输出拼入后一阶段消息"""
    from greyfield_hive.services.chain_runner import ChainRunnerService

    call_log = []

    async def fake_invoke(synapse, message, task_id, trace_id=""):
        call_log.append((synapse, message))
        return _make_raw(stdout=f"[{synapse}] 执行结果")

    svc = ChainRunnerService()
    svc._worker._build_enriched_message = AsyncMock(side_effect=lambda s, m, t, d: m)
    svc._worker._invoke_agent = fake_invoke
    svc._worker._persist_progress = AsyncMock()
    svc._worker._write_outcome_lesson = AsyncMock()

    result = await svc.run(
        task_id="T1",
        synapses=["code-expert", "research-analyst"],
        message="原始任务",
        domain="coding",
    )

    assert len(result.results) == 2
    # 第二阶段的消息应包含第一阶段输出
    _, msg_b = call_log[1]
    assert "[code-expert]" in msg_b
    assert "原始任务" in msg_b


@pytest.mark.asyncio
async def test_chain_all_success():
    """全部阶段成功时，ChainResult.success = True"""
    from greyfield_hive.services.chain_runner import ChainRunnerService

    svc = ChainRunnerService()
    svc._worker._build_enriched_message = AsyncMock(side_effect=lambda s, m, t, d: m)
    svc._worker._invoke_agent = AsyncMock(return_value=_make_raw(returncode=0, stdout="OK"))
    svc._worker._persist_progress = AsyncMock()
    svc._worker._write_outcome_lesson = AsyncMock()

    result = await svc.run("T1", ["a", "b", "c"], "任务", domain="general")

    assert result.success is True
    assert len(result.results) == 3
    assert result.final_output == "OK"


@pytest.mark.asyncio
async def test_chain_fail_fast():
    """某阶段失败时，后续阶段不再执行"""
    from greyfield_hive.services.chain_runner import ChainRunnerService

    invoke_calls = []

    async def fake_invoke(synapse, message, task_id, trace_id=""):
        invoke_calls.append(synapse)
        if synapse == "stage-b":
            return _make_raw(returncode=1, stdout="error", stderr="失败了")
        return _make_raw(returncode=0, stdout="OK")

    svc = ChainRunnerService()
    svc._worker._build_enriched_message = AsyncMock(side_effect=lambda s, m, t, d: m)
    svc._worker._invoke_agent = fake_invoke
    svc._worker._persist_progress = AsyncMock()
    svc._worker._write_outcome_lesson = AsyncMock()

    result = await svc.run("T1", ["stage-a", "stage-b", "stage-c"], "任务")

    # stage-c 不应该被调用
    assert "stage-c" not in invoke_calls
    assert result.success is False
    assert len(result.results) == 2  # a 和 b 都有结果，c 没有


@pytest.mark.asyncio
async def test_chain_final_output_is_last_stdout():
    """final_output 等于最后一个成功阶段的 stdout"""
    from greyfield_hive.services.chain_runner import ChainRunnerService

    outputs = {"a": "输出A", "b": "输出B"}

    async def fake_invoke(synapse, message, task_id, trace_id=""):
        return _make_raw(stdout=outputs[synapse])

    svc = ChainRunnerService()
    svc._worker._build_enriched_message = AsyncMock(side_effect=lambda s, m, t, d: m)
    svc._worker._invoke_agent = fake_invoke
    svc._worker._persist_progress = AsyncMock()
    svc._worker._write_outcome_lesson = AsyncMock()

    result = await svc.run("T1", ["a", "b"], "任务")
    assert result.final_output == "输出B"


@pytest.mark.asyncio
async def test_chain_empty_synapses():
    """空 synapses 列表直接返回空结果"""
    from greyfield_hive.services.chain_runner import ChainRunnerService

    svc = ChainRunnerService()
    result = await svc.run("T1", [], "任务")

    assert result.success is True
    assert result.results == []
    assert result.final_output == ""


@pytest.mark.asyncio
async def test_chain_writes_progress_per_stage():
    """每个阶段执行后都写入 progress_log"""
    from greyfield_hive.services.chain_runner import ChainRunnerService

    svc = ChainRunnerService()
    svc._worker._build_enriched_message = AsyncMock(side_effect=lambda s, m, t, d: m)
    svc._worker._invoke_agent = AsyncMock(return_value=_make_raw(stdout="OK"))
    svc._worker._persist_progress = AsyncMock()
    svc._worker._write_outcome_lesson = AsyncMock()

    await svc.run("T1", ["a", "b"], "任务")
    assert svc._worker._persist_progress.call_count == 2


@pytest.mark.asyncio
async def test_chain_lesson_written_on_success():
    """全链成功时写入最后一阶段的经验"""
    from greyfield_hive.services.chain_runner import ChainRunnerService

    svc = ChainRunnerService()
    svc._worker._build_enriched_message = AsyncMock(side_effect=lambda s, m, t, d: m)
    svc._worker._invoke_agent = AsyncMock(return_value=_make_raw(stdout="OK"))
    svc._worker._persist_progress = AsyncMock()
    svc._worker._write_outcome_lesson = AsyncMock()

    await svc.run("T1", ["a", "b"], "任务", domain="coding")
    # 至少写了一次 lesson
    assert svc._worker._write_outcome_lesson.call_count >= 1


# ── API 端点测试 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chain_404_task(client):
    r = await client.post("/api/tasks/nonexistent/chain", json={
        "synapses": ["code-expert", "research-analyst"],
        "message": "测试",
    })
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_chain_400_too_few_synapses(client):
    r = await client.post("/api/tasks\", json={\"title\": \"测试\"}")
    # 先创建任务
    r = await client.post("/api/tasks", json={"title": "测试任务"})
    task_id = r.json()["id"]

    r = await client.post(f"/api/tasks/{task_id}/chain", json={
        "synapses": ["only-one"],
        "message": "测试",
    })
    assert r.status_code == 400
    assert "两个" in r.json()["detail"] or "至少" in r.json()["detail"]


@pytest.mark.asyncio
async def test_chain_returns_results(client):
    """正常返回 chain 结果结构"""
    r = await client.post("/api/tasks", json={"title": "Chain 测试任务"})
    task_id = r.json()["id"]

    from greyfield_hive.services.chain_runner import ChainRunnerService, ChainResult, ChainStageResult

    mock_result = ChainResult(
        task_id=task_id,
        results=[
            ChainStageResult(synapse="code-expert", returncode=0, stdout="代码完成", stderr="", success=True),
            ChainStageResult(synapse="research-analyst", returncode=0, stdout="研究完成", stderr="", success=True),
        ],
        success=True,
        final_output="研究完成",
    )

    with patch("greyfield_hive.api.tasks.ChainRunnerService") as MockSvc:
        instance = MockSvc.return_value
        instance.run = AsyncMock(return_value=mock_result)
        r = await client.post(f"/api/tasks/{task_id}/chain", json={
            "synapses": ["code-expert", "research-analyst"],
            "message": "实现功能 X",
        })

    assert r.status_code == 200
    data = r.json()
    assert "task_id" in data
    assert "results" in data
    assert data["success"] is True
    assert data["final_output"] == "研究完成"
    assert len(data["results"]) == 2


@pytest.mark.asyncio
async def test_chain_fail_reflected_in_response(client):
    """失败时 success=False 反映在响应中"""
    r = await client.post("/api/tasks", json={"title": "Chain 失败测试"})
    task_id = r.json()["id"]

    from greyfield_hive.services.chain_runner import ChainRunnerService, ChainResult, ChainStageResult

    mock_result = ChainResult(
        task_id=task_id,
        results=[
            ChainStageResult(synapse="code-expert", returncode=1, stdout="", stderr="错误", success=False),
        ],
        success=False,
        final_output="",
    )

    with patch("greyfield_hive.api.tasks.ChainRunnerService") as MockSvc:
        instance = MockSvc.return_value
        instance.run = AsyncMock(return_value=mock_result)
        r = await client.post(f"/api/tasks/{task_id}/chain", json={
            "synapses": ["code-expert", "research-analyst"],
            "message": "任务",
        })

    assert r.status_code == 200
    assert r.json()["success"] is False


# ── CLI 测试 ────────────────────────────────────────────────

def test_cli_chain_command():
    """tasks chain：正常返回时显示执行链结果"""
    from typer.testing import CliRunner
    from unittest.mock import MagicMock, patch
    from greyfield_hive.cli import app as cli_app

    runner = CliRunner()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "task_id": "T001",
        "success": True,
        "final_output": "最终输出内容",
        "results": [
            {"synapse": "code-expert", "returncode": 0, "success": True, "stdout": "代码完成"},
            {"synapse": "research-analyst", "returncode": 0, "success": True, "stdout": "研究完成"},
        ],
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("greyfield_hive.cli.httpx") as mock_httpx:
        mock_httpx.post.return_value = mock_resp
        mock_httpx.ConnectError = Exception
        mock_httpx.HTTPStatusError = Exception
        result = runner.invoke(cli_app, [
            "tasks", "chain", "T001",
            "--synapses", "code-expert,research-analyst",
            "--message", "实现功能",
        ])

    assert result.exit_code == 0
    assert "code-expert" in result.output
    assert "research-analyst" in result.output


def test_cli_chain_invalid_synapses():
    """tasks chain：synapses 少于 2 个时报错"""
    from typer.testing import CliRunner
    from greyfield_hive.cli import app as cli_app

    runner = CliRunner()
    result = runner.invoke(cli_app, [
        "tasks", "chain", "T001",
        "--synapses", "only-one",
    ])
    assert result.exit_code != 0
