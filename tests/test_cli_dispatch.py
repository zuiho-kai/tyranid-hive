"""CLI 任务派发 / 子任务 / 阻塞状态 + 基因库导出/导入命令测试"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from greyfield_hive.cli import app

runner = CliRunner()


def mock_get(return_value):
    m = MagicMock(return_value=return_value)
    return patch("greyfield_hive.cli._get", m)


def mock_post(return_value):
    m = MagicMock(return_value=return_value)
    return patch("greyfield_hive.cli._post", m)


# ── tasks dispatch ─────────────────────────────────────────────────────

def test_tasks_dispatch_default_synapse():
    """dispatch 默认 synapse=overmind，显示成功信息"""
    with mock_post({"synapse": "overmind", "task_id": "T-001"}) as m:
        result = runner.invoke(app, ["tasks", "dispatch", "T-001"])
    assert result.exit_code == 0
    assert "T-001" in result.output
    assert "overmind" in result.output
    body = m.call_args[0][1]
    assert body["synapse"] == "overmind"


def test_tasks_dispatch_custom_synapse():
    """dispatch --synapse 传递自定义 synapse"""
    with mock_post({"synapse": "code-expert"}) as m:
        result = runner.invoke(app, ["tasks", "dispatch", "T-002", "--synapse", "code-expert"])
    assert result.exit_code == 0
    assert "code-expert" in result.output
    body = m.call_args[0][1]
    assert body["synapse"] == "code-expert"


def test_tasks_dispatch_with_message():
    """dispatch --message 传递附加消息"""
    with mock_post({"synapse": "overmind"}) as m:
        runner.invoke(app, ["tasks", "dispatch", "T-003", "--message", "请加急处理"])
    body = m.call_args[0][1]
    assert body["message"] == "请加急处理"


def test_tasks_dispatch_uses_actual_synapse_from_response():
    """dispatch 显示响应中的实际 synapse（auto 路由场景）"""
    with mock_post({"synapse": "code-expert-v2"}):
        result = runner.invoke(app, ["tasks", "dispatch", "T-004", "--synapse", "auto"])
    assert "code-expert-v2" in result.output


# ── tasks subtask ──────────────────────────────────────────────────────

def test_tasks_subtask_creates_with_parent():
    """subtask 携带 parent_id 发起 POST /api/tasks"""
    new_task = {"id": "SUB-001", "title": "子任务标题", "parent_id": "P-001"}
    with mock_post(new_task) as m:
        result = runner.invoke(app, [
            "tasks", "subtask", "P-001", "--title", "子任务标题"
        ])
    assert result.exit_code == 0
    assert "SUB-001" in result.output
    body = m.call_args[0][1]
    assert body["parent_id"] == "P-001"
    assert body["title"] == "子任务标题"


def test_tasks_subtask_with_assignee():
    """subtask --assignee 传递 assignee_synapse"""
    with mock_post({"id": "SUB-002", "title": "T"}) as m:
        runner.invoke(app, [
            "tasks", "subtask", "P-002",
            "--title", "T",
            "--assignee", "code-expert"
        ])
    body = m.call_args[0][1]
    assert body["assignee_synapse"] == "code-expert"


def test_tasks_subtask_with_priority():
    """subtask --priority 传递优先级"""
    with mock_post({"id": "SUB-003", "title": "T"}) as m:
        runner.invoke(app, [
            "tasks", "subtask", "P-003",
            "--title", "T",
            "--priority", "high"
        ])
    body = m.call_args[0][1]
    assert body["priority"] == "high"


def test_tasks_subtask_default_priority_normal():
    """subtask 默认优先级为 normal"""
    with mock_post({"id": "SUB-004", "title": "T"}) as m:
        runner.invoke(app, ["tasks", "subtask", "P-004", "--title", "T"])
    body = m.call_args[0][1]
    assert body["priority"] == "normal"


# ── tasks blocked ──────────────────────────────────────────────────────

def test_tasks_blocked_not_blocked():
    """blocked 无阻塞时显示绿色 ✓"""
    with mock_get({"is_blocked": False, "pending_deps": []}):
        result = runner.invoke(app, ["tasks", "blocked", "T-010"])
    assert result.exit_code == 0
    assert "无阻塞" in result.output or "✓" in result.output


def test_tasks_blocked_is_blocked():
    """blocked 有阻塞时显示未完成依赖"""
    deps = [{"id": "DEP-001", "state": "Incubating", "title": "前置任务"}]
    with mock_get({"is_blocked": True, "pending_deps": deps}):
        result = runner.invoke(app, ["tasks", "blocked", "T-011"])
    assert result.exit_code == 0
    assert "DEP-001" in result.output or "前置任务" in result.output


def test_tasks_blocked_calls_correct_endpoint():
    """blocked 调用 /api/tasks/{id}/blocked"""
    with mock_get({"is_blocked": False, "pending_deps": []}) as m:
        runner.invoke(app, ["tasks", "blocked", "T-999"])
    called_path = m.call_args[0][0]
    assert "/api/tasks/T-999/blocked" in called_path


# ── genes export ───────────────────────────────────────────────────────

_EXPORT_BUNDLE = {
    "exported_at": "2026-03-22T10:00:00+00:00",
    "lessons_count": 2,
    "playbooks_count": 1,
    "lessons": [
        {"domain": "arch", "content": "解耦", "outcome": "success", "tags": []},
        {"domain": "ops",  "content": "备份", "outcome": "success", "tags": []},
    ],
    "playbooks": [
        {"slug": "deploy", "domain": "ops", "title": "部署手册", "content": "# 步骤"}
    ]
}


def test_genes_export_stdout():
    """genes export 无 --output 时输出 JSON 到 stdout"""
    with mock_get(_EXPORT_BUNDLE):
        result = runner.invoke(app, ["genes", "export"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["lessons_count"] == 2
    assert parsed["playbooks_count"] == 1


def test_genes_export_to_file(tmp_path):
    """genes export --output 写入文件并打印确认信息"""
    out_file = str(tmp_path / "bundle.json")
    with mock_get(_EXPORT_BUNDLE):
        result = runner.invoke(app, ["genes", "export", "--output", out_file])
    assert result.exit_code == 0
    assert "✓" in result.output
    assert Path(out_file).exists()
    saved = json.loads(Path(out_file).read_text(encoding="utf-8"))
    assert saved["lessons_count"] == 2


def test_genes_export_calls_correct_endpoint():
    """genes export 调用 /api/genes/export"""
    with mock_get(_EXPORT_BUNDLE) as m:
        runner.invoke(app, ["genes", "export"])
    called_path = m.call_args[0][0]
    assert "/api/genes/export" in called_path


# ── genes import ───────────────────────────────────────────────────────

def test_genes_import_success(tmp_path):
    """genes import 读取文件并调用 /api/genes/import"""
    bundle_file = tmp_path / "bundle.json"
    bundle_file.write_text(
        json.dumps({
            "lessons": [{"domain": "x", "content": "c", "outcome": "success"}],
            "playbooks": [{"slug": "s", "domain": "d", "title": "t", "content": "c"}],
        }),
        encoding="utf-8"
    )
    import_result = {"lessons_added": 1, "playbooks_added": 1, "playbooks_skipped": 0}
    with mock_post(import_result) as m:
        result = runner.invoke(app, ["genes", "import", str(bundle_file)])
    assert result.exit_code == 0
    assert "✓" in result.output
    assert "+1" in result.output
    body = m.call_args[0][1]
    assert len(body["lessons"]) == 1
    assert len(body["playbooks"]) == 1


def test_genes_import_file_not_found():
    """genes import 文件不存在时退出非零"""
    result = runner.invoke(app, ["genes", "import", "/nonexistent/path.json"])
    assert result.exit_code != 0


def test_genes_import_invalid_json(tmp_path):
    """genes import JSON 解析失败时退出非零"""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not valid json", encoding="utf-8")
    result = runner.invoke(app, ["genes", "import", str(bad_file)])
    assert result.exit_code != 0


def test_genes_import_shows_skip_count(tmp_path):
    """genes import 显示跳过数量"""
    bundle_file = tmp_path / "bundle.json"
    bundle_file.write_text(json.dumps({"lessons": [], "playbooks": []}), encoding="utf-8")
    import_result = {"lessons_added": 0, "playbooks_added": 0, "playbooks_skipped": 3}
    with mock_post(import_result):
        result = runner.invoke(app, ["genes", "import", str(bundle_file)])
    assert result.exit_code == 0
    assert "3" in result.output
