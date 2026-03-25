"""POST /api/tasks/{id}/analyze 端点测试"""

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


# ── 辅助 ──────────────────────────────────────────────────

def _mock_overmind_result(
    summary="分析完毕",
    todos=None,
    risks=None,
    blockers=None,
    domain="coding",
    recommended_state="Planning",
):
    from greyfield_hive.agents.overmind_agent import OvermindResult
    return OvermindResult(
        summary=summary,
        todos=todos if todos is not None else ["子任务1", "子任务2"],
        risks=risks if risks is not None else ["风险A"],
        blockers=blockers if blockers is not None else [],
        domain=domain,
        recommended_state=recommended_state,
    )


# ── 404 ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_404_task(client):
    r = await client.post("/api/tasks/nonexistent/analyze")
    assert r.status_code == 404


# ── 503：LLM 不可用 ───────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_503_when_no_api_key(client):
    """未设置 API Key 时返回 503"""
    r = await client.post("/api/tasks", json={"title": "测试"})
    task_id = r.json()["id"]

    with patch("greyfield_hive.api.tasks.OvermindAgent") as MockAgent:
        instance = MockAgent.return_value
        instance.is_available.return_value = False

        r = await client.post(f"/api/tasks/{task_id}/analyze")

    assert r.status_code == 503
    assert "ANTHROPIC_API_KEY" in r.json()["detail"]


# ── 正常路径 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_returns_todos_and_analysis(client):
    """分析完成后应返回 todos 和 analysis 字段"""
    r = await client.post("/api/tasks", json={
        "title": "实现斐波那契函数",
        "description": "需要递推和记忆化两种版本",
    })
    task_id = r.json()["id"]

    mock_result = _mock_overmind_result(
        summary="实现两种斐波那契算法",
        todos=["实现递推版本", "实现记忆化版本", "编写测试"],
        risks=["递推版本可能栈溢出"],
        domain="coding",
        recommended_state="Planning",
    )

    with patch("greyfield_hive.api.tasks.OvermindAgent") as MockAgent:
        instance = MockAgent.return_value
        instance.is_available.return_value = True
        instance.analyze = AsyncMock(return_value=mock_result)

        r = await client.post(f"/api/tasks/{task_id}/analyze")

    assert r.status_code == 200
    data = r.json()
    assert "task" in data
    assert "analysis" in data
    assert data["analysis"]["summary"] == "实现两种斐波那契算法"
    assert data["analysis"]["domain"] == "coding"
    assert data["analysis"]["recommended_state"] == "Planning"
    assert len(data["analysis"]["todos"]) == 3
    assert len(data["analysis"]["risks"]) == 1


@pytest.mark.asyncio
async def test_analyze_injects_todos_into_task(client):
    """分析后 todos 应写入任务"""
    r = await client.post("/api/tasks", json={"title": "任务 X"})
    task_id = r.json()["id"]
    assert r.json()["todos"] == []

    mock_result = _mock_overmind_result(todos=["子任务A", "子任务B"])

    with patch("greyfield_hive.api.tasks.OvermindAgent") as MockAgent:
        instance = MockAgent.return_value
        instance.is_available.return_value = True
        instance.analyze = AsyncMock(return_value=mock_result)

        r = await client.post(f"/api/tasks/{task_id}/analyze")

    task_data = r.json()["task"]
    assert len(task_data["todos"]) == 2
    assert task_data["todos"][0]["title"] == "子任务A"
    assert task_data["todos"][0]["done"] is False


@pytest.mark.asyncio
async def test_analyze_adds_progress_entry(client):
    """分析后应有来自 overmind 的进度条目"""
    r = await client.post("/api/tasks", json={"title": "任务 Y"})
    task_id = r.json()["id"]

    mock_result = _mock_overmind_result(summary="分析摘要")

    with patch("greyfield_hive.api.tasks.OvermindAgent") as MockAgent:
        instance = MockAgent.return_value
        instance.is_available.return_value = True
        instance.analyze = AsyncMock(return_value=mock_result)

        r = await client.post(f"/api/tasks/{task_id}/analyze")

    task_data = r.json()["task"]
    progress_log = task_data.get("progress_log", [])
    assert any(
        entry.get("agent") == "overmind" and "分析完成" in entry.get("content", "")
        for entry in progress_log
    )


@pytest.mark.asyncio
async def test_analyze_empty_todos_still_returns_analysis(client):
    """即使 LLM 返回空 todos，分析结果仍应返回"""
    r = await client.post("/api/tasks", json={"title": "简单任务"})
    task_id = r.json()["id"]

    mock_result = _mock_overmind_result(todos=[], risks=[])

    with patch("greyfield_hive.api.tasks.OvermindAgent") as MockAgent:
        instance = MockAgent.return_value
        instance.is_available.return_value = True
        instance.analyze = AsyncMock(return_value=mock_result)

        r = await client.post(f"/api/tasks/{task_id}/analyze")

    assert r.status_code == 200
    assert r.json()["analysis"]["todos"] == []


# ── CLI ───────────────────────────────────────────────────

def test_cli_analyze_command():
    """tasks analyze：200 时应显示分析结果"""
    from typer.testing import CliRunner
    from unittest.mock import MagicMock, patch
    from greyfield_hive.cli import app as cli_app

    runner = CliRunner()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "task": {"id": "T001"},
        "analysis": {
            "summary": "任务分析完毕",
            "domain": "coding",
            "recommended_state": "Planning",
            "todos": ["子任务1"],
            "risks": ["风险1"],
        },
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("greyfield_hive.cli.httpx") as mock_httpx:
        mock_httpx.post.return_value = mock_resp
        mock_httpx.ConnectError = Exception
        mock_httpx.HTTPStatusError = Exception
        result = runner.invoke(cli_app, ["tasks", "analyze", "T001"])

    assert result.exit_code == 0
    assert "分析完成" in result.output
    assert "任务分析完毕" in result.output
    assert "子任务1" in result.output


def test_cli_analyze_503():
    """tasks analyze：503 时显示 LLM 不可用"""
    from typer.testing import CliRunner
    from unittest.mock import MagicMock, patch
    from greyfield_hive.cli import app as cli_app

    runner = CliRunner()
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.json.return_value = {"detail": "未设置 ANTHROPIC_API_KEY"}

    with patch("greyfield_hive.cli.httpx") as mock_httpx:
        mock_httpx.post.return_value = mock_resp
        mock_httpx.ConnectError = Exception
        mock_httpx.HTTPStatusError = Exception
        result = runner.invoke(cli_app, ["tasks", "analyze", "T001"])

    assert result.exit_code != 0
    assert "不可用" in result.output or "ANTHROPIC" in result.output


def test_cli_trial_command():
    """tasks trial：正常返回时显示胜者"""
    from typer.testing import CliRunner
    from unittest.mock import MagicMock, patch
    from greyfield_hive.cli import app as cli_app

    runner = CliRunner()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "task_id": "T001",
        "winner": "code-expert",
        "tie": False,
        "results": {
            "code-expert":    {"returncode": 0, "success": True},
            "research-analyst": {"returncode": 1, "success": False},
        },
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("greyfield_hive.cli.httpx") as mock_httpx:
        mock_httpx.post.return_value = mock_resp
        mock_httpx.ConnectError = Exception
        mock_httpx.HTTPStatusError = Exception
        result = runner.invoke(cli_app, ["tasks", "trial", "T001"])

    assert result.exit_code == 0
    assert "code-expert" in result.output
    assert "胜者" in result.output


def test_cli_trial_invalid_synapses():
    """tasks trial：synapses 数量不为 2 时应报错"""
    from typer.testing import CliRunner
    from greyfield_hive.cli import app as cli_app

    runner = CliRunner()
    result = runner.invoke(cli_app, ["tasks", "trial", "T001", "--synapses", "only-one"])
    assert result.exit_code != 0
    assert "两个" in result.output
