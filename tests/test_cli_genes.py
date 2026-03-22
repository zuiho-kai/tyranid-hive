"""CLI 基因库命令测试 —— hive lessons / hive playbooks"""

import json
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


def mock_httpx_get(status_code=200, json_data=None):
    """Mock httpx.get for commands that call httpx directly"""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    m = MagicMock(return_value=resp)
    return patch("greyfield_hive.cli.httpx.get", m)


def mock_httpx_post(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    m = MagicMock(return_value=resp)
    return patch("greyfield_hive.cli.httpx.post", m)


def mock_httpx_delete(status_code=204):
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    m = MagicMock(return_value=resp)
    return patch("greyfield_hive.cli.httpx.delete", m)


_LESSON = {
    "id": "abc123def456",
    "domain": "coding",
    "content": "使用 async/await 提升并发性能",
    "outcome": "success",
    "frequency": 3,
    "last_used": "2026-03-01T10:00:00",
}

_PLAYBOOK = {
    "id": "pb-uuid-001",
    "slug": "coding-guide",
    "title": "编码最佳实践",
    "domain": "coding",
    "content": "代码审查要点：类型标注、异常处理、测试覆盖",
    "version": 2,
    "use_count": 12,
    "success_rate": 0.85,
    "is_active": True,
}


# ── lessons list ───────────────────────────────────────────────────────

def test_lessons_list_shows_table():
    """lessons list 应展示经验教训表格"""
    with mock_get([_LESSON]):
        result = runner.invoke(app, ["lessons", "list"])
    assert result.exit_code == 0
    assert "coding" in result.output
    assert "success" in result.output
    assert "async/await" in result.output


def test_lessons_list_empty():
    """lessons list 无数据时提示空"""
    with mock_get([]):
        result = runner.invoke(app, ["lessons", "list"])
    assert result.exit_code == 0
    assert "暂无" in result.output


def test_lessons_list_with_domain_filter():
    """lessons list --domain 传递 domain 参数"""
    with mock_get([_LESSON]) as m:
        result = runner.invoke(app, ["lessons", "list", "--domain", "coding"])
    assert result.exit_code == 0
    call_kwargs = m.call_args
    assert "coding" in str(call_kwargs)


# ── lessons add ────────────────────────────────────────────────────────

def test_lessons_add_success():
    """lessons add 成功时显示 ID"""
    with mock_post(_LESSON):
        result = runner.invoke(app, [
            "lessons", "add",
            "--domain", "coding",
            "--content", "使用 async/await",
            "--outcome", "success",
        ])
    assert result.exit_code == 0
    assert "✓" in result.output or "经验已入库" in result.output


def test_lessons_add_default_outcome():
    """lessons add 默认 outcome 为 success"""
    with mock_post(_LESSON) as m:
        runner.invoke(app, [
            "lessons", "add",
            "--domain", "research",
            "--content", "数据来源需验证",
        ])
    call_args = m.call_args[0][1]  # json body
    assert call_args["outcome"] == "success"


# ── lessons search ─────────────────────────────────────────────────────

def test_lessons_search_shows_results():
    """lessons search 显示结果列表"""
    with mock_post([_LESSON]):
        result = runner.invoke(app, ["lessons", "search", "coding"])
    assert result.exit_code == 0
    assert "async/await" in result.output


def test_lessons_search_empty():
    """lessons search 无结果时提示"""
    with mock_post([]):
        result = runner.invoke(app, ["lessons", "search", "unknown"])
    assert result.exit_code == 0
    assert "未找到" in result.output


def test_lessons_search_with_tags():
    """lessons search --tags 将 tags 传入 POST body"""
    with mock_post([_LESSON]) as m:
        runner.invoke(app, ["lessons", "search", "coding", "--tags", "性能 优化"])
    body = m.call_args[0][1]
    assert "性能" in body["tags"]
    assert "优化" in body["tags"]


# ── lessons bump ───────────────────────────────────────────────────────

def test_lessons_bump_success():
    """lessons bump 成功显示新 frequency"""
    bumped = {**_LESSON, "frequency": 4}
    with mock_httpx_post(200, bumped):
        result = runner.invoke(app, ["lessons", "bump", "abc123def456"])
    assert result.exit_code == 0
    assert "4" in result.output


def test_lessons_bump_not_found():
    """lessons bump 不存在时退出 1"""
    with mock_httpx_post(404):
        result = runner.invoke(app, ["lessons", "bump", "no-such-id"])
    assert result.exit_code != 0


# ── lessons delete ─────────────────────────────────────────────────────

def test_lessons_delete_with_yes():
    """lessons delete --yes 直接删除"""
    with mock_httpx_delete(204):
        result = runner.invoke(app, ["lessons", "delete", "abc123", "--yes"])
    assert result.exit_code == 0
    assert "✓" in result.output or "已删除" in result.output


def test_lessons_delete_not_found():
    """lessons delete 不存在时退出 1"""
    with mock_httpx_delete(404):
        result = runner.invoke(app, ["lessons", "delete", "no-such-id", "--yes"])
    assert result.exit_code != 0


# ── playbooks list ─────────────────────────────────────────────────────

def test_playbooks_list_shows_table():
    """playbooks list 应展示手册表格"""
    with mock_get([_PLAYBOOK]):
        result = runner.invoke(app, ["playbooks", "list"])
    assert result.exit_code == 0
    assert "coding-guide" in result.output
    assert "编码最佳实践" in result.output


def test_playbooks_list_empty():
    """playbooks list 无数据时提示"""
    with mock_get([]):
        result = runner.invoke(app, ["playbooks", "list"])
    assert result.exit_code == 0
    assert "暂无" in result.output


def test_playbooks_list_with_domain():
    """playbooks list --domain 传递 domain"""
    with mock_get([_PLAYBOOK]) as m:
        runner.invoke(app, ["playbooks", "list", "--domain", "coding"])
    assert "coding" in str(m.call_args)


# ── playbooks show ─────────────────────────────────────────────────────

def test_playbooks_show_content():
    """playbooks show 显示手册完整内容"""
    with mock_httpx_get(200, _PLAYBOOK):
        result = runner.invoke(app, ["playbooks", "show", "coding-guide"])
    assert result.exit_code == 0
    assert "编码最佳实践" in result.output
    assert "代码审查" in result.output


def test_playbooks_show_not_found():
    """playbooks show 不存在时退出 1"""
    with mock_httpx_get(404):
        result = runner.invoke(app, ["playbooks", "show", "no-such-slug"])
    assert result.exit_code != 0


# ── playbooks add ──────────────────────────────────────────────────────

def test_playbooks_add_success():
    """playbooks add 成功时显示 slug"""
    with mock_post(_PLAYBOOK):
        result = runner.invoke(app, [
            "playbooks", "add",
            "--slug",    "coding-guide",
            "--title",   "编码最佳实践",
            "--domain",  "coding",
            "--content", "代码审查要点",
        ])
    assert result.exit_code == 0
    assert "✓" in result.output or "已创建" in result.output


# ── playbooks search ───────────────────────────────────────────────────

def test_playbooks_search_shows_results():
    """playbooks search 显示手册列表"""
    with mock_post([_PLAYBOOK]):
        result = runner.invoke(app, ["playbooks", "search", "coding"])
    assert result.exit_code == 0
    assert "编码最佳实践" in result.output


def test_playbooks_search_empty():
    """playbooks search 无结果时提示"""
    with mock_post([]):
        result = runner.invoke(app, ["playbooks", "search", "unknown"])
    assert result.exit_code == 0
    assert "未找到" in result.output


def test_playbooks_search_with_tags():
    """playbooks search --tags 传递 tags 列表"""
    with mock_post([_PLAYBOOK]) as m:
        runner.invoke(app, ["playbooks", "search", "coding", "--tags", "代码 测试"])
    body = m.call_args[0][1]
    assert "代码" in body["tags"]
    assert "测试" in body["tags"]
