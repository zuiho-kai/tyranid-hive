"""CLI 测试 —— 使用 typer.testing.CliRunner + unittest.mock 模拟 HTTP 调用"""

import json
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from greyfield_hive.cli import app

runner = CliRunner()


# ── 辅助函数 ───────────────────────────────────────────────────────────────

def mock_get(return_value: dict | list):
    """创建一个 _get 的 mock，返回指定数据"""
    m = MagicMock(return_value=return_value)
    return patch("greyfield_hive.cli._get", m)


def mock_post(return_value: dict):
    m = MagicMock(return_value=return_value)
    return patch("greyfield_hive.cli._post", m)


# ── health ─────────────────────────────────────────────────────────────────

def test_health_synapse_active():
    """health 命令：状态 synapse_active 应显示绿色状态"""
    with mock_get({
        "status": "synapse_active",
        "service": "tyranid-hive",
        "version": "0.1.0",
        "db": "ok",
        "workers": "ok",
    }):
        result = runner.invoke(app, ["health"])
    assert result.exit_code == 0
    assert "synapse_active" in result.output
    assert "tyranid-hive" in result.output
    assert "0.1.0" in result.output


def test_health_degraded():
    """health 命令：状态 degraded 也应正常输出"""
    with mock_get({
        "status": "degraded",
        "service": "tyranid-hive",
        "version": "0.1.0",
        "db": "ok",
        "workers": "stopped",
    }):
        result = runner.invoke(app, ["health"])
    assert result.exit_code == 0
    assert "degraded" in result.output


# ── stats ──────────────────────────────────────────────────────────────────

def test_stats_shows_counts():
    """stats 命令：应显示各状态统计"""
    with mock_get({
        "total": 5,
        "active": 3,
        "complete": 2,
        "cancelled": 0,
        "by_state": {"Incubating": 1, "Executing": 2, "Complete": 2},
    }):
        result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0
    assert "5" in result.output
    assert "Incubating" in result.output
    assert "Executing" in result.output


def test_stats_empty():
    """stats 命令：空数据库也应正常输出"""
    with mock_get({
        "total": 0, "active": 0, "complete": 0, "cancelled": 0, "by_state": {}
    }):
        result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0
    assert "0" in result.output


# ── tasks list ─────────────────────────────────────────────────────────────

def test_tasks_list_shows_table():
    """tasks list：应显示任务列表表格"""
    with mock_get([
        {
            "id": "BT-001", "title": "测试战团A", "state": "Incubating",
            "priority": "high", "assignee_synapse": None,
            "updated_at": "2024-01-01T10:00:00",
        },
        {
            "id": "BT-002", "title": "测试战团B", "state": "Executing",
            "priority": "normal", "assignee_synapse": "overmind",
            "updated_at": "2024-01-02T10:00:00",
        },
    ]):
        result = runner.invoke(app, ["tasks", "list"])
    assert result.exit_code == 0
    assert "BT-001" in result.output
    assert "BT-002" in result.output
    assert "测试战团A" in result.output
    assert "Incubating" in result.output
    assert "Executing" in result.output
    assert "2 条" in result.output


def test_tasks_list_empty():
    """tasks list：无任务时提示没有匹配"""
    with mock_get([]):
        result = runner.invoke(app, ["tasks", "list"])
    assert result.exit_code == 0
    assert "没有" in result.output


def test_tasks_list_with_state_filter():
    """tasks list --state Executing：应传递 state 参数给 _get"""
    with patch("greyfield_hive.cli._get", MagicMock(return_value=[])) as mock:
        result = runner.invoke(app, ["tasks", "list", "--state", "Executing"])
    assert result.exit_code == 0
    mock.assert_called_once()
    call_kwargs = mock.call_args
    # 确认 params 包含 state=Executing
    params = call_kwargs[0][1] if len(call_kwargs[0]) > 1 else call_kwargs[1].get("params", {})
    assert params.get("state") == "Executing"


def test_tasks_list_with_priority_filter():
    """tasks list --priority high：应传递 priority 参数"""
    with patch("greyfield_hive.cli._get", MagicMock(return_value=[])) as mock:
        runner.invoke(app, ["tasks", "list", "--priority", "high"])
    args, kwargs = mock.call_args
    params = args[1] if len(args) > 1 else kwargs.get("params", {})
    assert params.get("priority") == "high"


# ── tasks show ─────────────────────────────────────────────────────────────

def test_tasks_show_basic():
    """tasks show：应显示任务详情"""
    with mock_get({
        "id": "BT-001", "title": "测试战团", "description": "这是描述",
        "state": "Planning", "priority": "high",
        "assignee_synapse": "overmind", "creator": "user",
        "created_at": "2024-01-01T10:00:00", "updated_at": "2024-01-01T11:00:00",
        "progress_log": [], "todos": [], "flow_log": [],
    }):
        result = runner.invoke(app, ["tasks", "show", "BT-001"])
    assert result.exit_code == 0
    assert "BT-001" in result.output
    assert "测试战团" in result.output
    assert "Planning" in result.output
    assert "overmind" in result.output


def test_tasks_show_with_todos_and_flow():
    """tasks show：有 todos 和流转记录时应显示"""
    with mock_get({
        "id": "BT-002", "title": "战团B", "description": "",
        "state": "Executing", "priority": "normal",
        "assignee_synapse": None, "creator": "test",
        "created_at": "2024-01-01T10:00:00", "updated_at": "2024-01-01T11:00:00",
        "progress_log": [{"ts": "2024-01-01T10:05:00", "agent": "overmind", "content": "已规划"}],
        "todos": [
            {"title": "步骤一", "done": True},
            {"title": "步骤二", "done": False},
        ],
        "flow_log": [
            {"from": None, "to": "Incubating", "agent": "api", "reason": "", "ts": "2024-01-01T10:00:00"},
            {"from": "Incubating", "to": "Planning", "agent": "overmind", "reason": "自动", "ts": "2024-01-01T10:01:00"},
        ],
    }):
        result = runner.invoke(app, ["tasks", "show", "BT-002"])
    assert result.exit_code == 0
    assert "步骤一" in result.output
    assert "步骤二" in result.output
    assert "已规划" in result.output
    assert "Incubating" in result.output


# ── tasks create ───────────────────────────────────────────────────────────

def test_tasks_create_success():
    """tasks create：应调用 _post 并显示新任务 ID"""
    with mock_post({
        "id": "BT-NEW-001", "title": "新战团", "state": "Incubating",
    }):
        result = runner.invoke(app, [
            "tasks", "create",
            "--title", "新战团",
            "--priority", "high",
        ])
    assert result.exit_code == 0
    assert "BT-NEW-001" in result.output
    assert "Incubating" in result.output


def test_tasks_create_with_description():
    """tasks create --desc：应传递 description"""
    with patch("greyfield_hive.cli._post", MagicMock(return_value={
        "id": "BT-NEW-002", "title": "战团C", "state": "Incubating",
    })) as mock:
        runner.invoke(app, [
            "tasks", "create",
            "--title", "战团C",
            "--desc", "这是详细描述",
        ])
    payload = mock.call_args[1]["json"]
    assert payload["description"] == "这是详细描述"
    assert payload["title"] == "战团C"


# ── tasks transition ───────────────────────────────────────────────────────

def test_tasks_transition_success():
    """tasks transition：应显示新状态"""
    with mock_post({"id": "BT-001", "state": "Planning"}):
        result = runner.invoke(app, ["tasks", "transition", "BT-001", "Planning"])
    assert result.exit_code == 0
    assert "Planning" in result.output


def test_tasks_transition_with_reason():
    """tasks transition --reason：应传递 reason"""
    with patch("greyfield_hive.cli._post", MagicMock(return_value={
        "id": "BT-001", "state": "Planning",
    })) as mock:
        runner.invoke(app, [
            "tasks", "transition", "BT-001", "Planning",
            "--reason", "手动触发",
        ])
    payload = mock.call_args[1]["json"]
    assert payload["reason"] == "手动触发"
    assert payload["agent"] == "cli"


# ── tasks cancel ───────────────────────────────────────────────────────────

def test_tasks_cancel():
    """tasks cancel：应流转到 Cancelled 状态"""
    with patch("greyfield_hive.cli._post", MagicMock(return_value={
        "id": "BT-001", "state": "Cancelled",
    })) as mock:
        result = runner.invoke(app, ["tasks", "cancel", "BT-001"])
    assert result.exit_code == 0
    assert "Cancelled" in result.output
    payload = mock.call_args[1]["json"]
    assert payload["new_state"] == "Cancelled"


# ── tasks patch ────────────────────────────────────────────────────────────

def test_tasks_patch_title():
    """tasks patch --title：应调用 httpx.patch 并显示更新成功"""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "BT-001", "title": "新标题", "priority": "high"}
    mock_resp.raise_for_status = MagicMock()

    with patch("greyfield_hive.cli.httpx") as mock_httpx:
        mock_httpx.patch.return_value = mock_resp
        mock_httpx.ConnectError = Exception
        mock_httpx.HTTPStatusError = Exception
        result = runner.invoke(app, ["tasks", "patch", "BT-001", "--title", "新标题"])

    assert result.exit_code == 0
    assert "BT-001" in result.output
    assert "已更新" in result.output
    call_kwargs = mock_httpx.patch.call_args
    assert "BT-001" in call_kwargs[0][0]
    assert call_kwargs[1]["json"]["title"] == "新标题"


def test_tasks_patch_priority():
    """tasks patch --priority：应传递 priority 字段"""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "BT-001", "title": "战团", "priority": "critical"}
    mock_resp.raise_for_status = MagicMock()

    with patch("greyfield_hive.cli.httpx") as mock_httpx:
        mock_httpx.patch.return_value = mock_resp
        mock_httpx.ConnectError = Exception
        mock_httpx.HTTPStatusError = Exception
        result = runner.invoke(app, ["tasks", "patch", "BT-001", "--priority", "critical"])

    assert result.exit_code == 0
    payload = mock_httpx.patch.call_args[1]["json"]
    assert payload.get("priority") == "critical"
    assert "title" not in payload


def test_tasks_patch_no_fields():
    """tasks patch 不带任何字段：应报错退出"""
    result = runner.invoke(app, ["tasks", "patch", "BT-001"])
    assert result.exit_code != 0


def test_tasks_patch_multiple_fields():
    """tasks patch --title --desc --priority：应传递全部字段"""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "BT-001", "title": "新", "priority": "low"}
    mock_resp.raise_for_status = MagicMock()

    with patch("greyfield_hive.cli.httpx") as mock_httpx:
        mock_httpx.patch.return_value = mock_resp
        mock_httpx.ConnectError = Exception
        mock_httpx.HTTPStatusError = Exception
        runner.invoke(app, [
            "tasks", "patch", "BT-001",
            "--title", "新", "--desc", "新描述", "--priority", "low",
        ])

    payload = mock_httpx.patch.call_args[1]["json"]
    assert payload["title"] == "新"
    assert payload["description"] == "新描述"
    assert payload["priority"] == "low"


# ── tasks delete ────────────────────────────────────────────────────────────

def test_tasks_delete_with_yes_flag():
    """tasks delete --yes：跳过确认，调用 httpx.delete"""
    mock_resp = MagicMock()
    mock_resp.status_code = 204

    with patch("greyfield_hive.cli.httpx") as mock_httpx:
        mock_httpx.delete.return_value = mock_resp
        mock_httpx.ConnectError = Exception
        result = runner.invoke(app, ["tasks", "delete", "BT-001", "--yes"])

    assert result.exit_code == 0
    assert "BT-001" in result.output
    assert "已删除" in result.output
    call_url = mock_httpx.delete.call_args[0][0]
    assert "BT-001" in call_url


def test_tasks_delete_not_found():
    """tasks delete --yes：404 时应报错"""
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("greyfield_hive.cli.httpx") as mock_httpx:
        mock_httpx.delete.return_value = mock_resp
        mock_httpx.ConnectError = Exception
        result = runner.invoke(app, ["tasks", "delete", "BT-999", "--yes"])

    assert result.exit_code != 0
    assert "不存在" in result.output


# ── synapses ───────────────────────────────────────────────────────────────

def test_synapses_list():
    """synapses：应显示小主脑表格"""
    with mock_get([
        {"id": "overmind",         "name": "主脑",     "emoji": "🧠", "tier": 1, "role": "决策调度"},
        {"id": "evolution-master", "name": "进化大师", "emoji": "🧬", "tier": 2, "role": "基因进化"},
        {"id": "code-expert",      "name": "代码专家", "emoji": "💻", "tier": 2, "role": "代码实现"},
    ]):
        result = runner.invoke(app, ["synapses"])
    assert result.exit_code == 0
    assert "overmind" in result.output
    assert "evolution-master" in result.output
    assert "主脑" in result.output
    assert "T1" in result.output
    assert "T2" in result.output
