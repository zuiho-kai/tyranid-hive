"""hive evolve 子命令测试 —— status / scan / domain"""

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


# ── evolve status ────────────────────────────────────────────────────

def test_evolve_status_shows_table():
    """evolve status：显示各域进化状态表格"""
    data = {
        "threshold": 5,
        "domains": [
            {"domain": "coding",   "total": 10, "success_count": 8, "ready_to_evolve": True},
            {"domain": "research", "total": 3,  "success_count": 2, "ready_to_evolve": False},
        ],
    }
    with mock_get(data):
        result = runner.invoke(app, ["evolve", "status"])
    assert result.exit_code == 0
    assert "coding" in result.output
    assert "research" in result.output
    assert "可进化" in result.output
    assert "10" in result.output
    assert "8"  in result.output


def test_evolve_status_empty():
    """evolve status：无数据时显示空提示"""
    with mock_get({"threshold": 5, "domains": []}):
        result = runner.invoke(app, ["evolve", "status"])
    assert result.exit_code == 0
    assert "暂无" in result.output


def test_evolve_status_threshold_shown():
    """evolve status：标题中显示进化阈值"""
    with mock_get({"threshold": 5, "domains": [
        {"domain": "coding", "total": 5, "success_count": 5, "ready_to_evolve": True},
    ]}):
        result = runner.invoke(app, ["evolve", "status"])
    assert result.exit_code == 0
    assert "5" in result.output  # 阈值 5


# ── evolve scan ──────────────────────────────────────────────────────

def test_evolve_scan_no_domains():
    """evolve scan：没有域达到阈值时显示提示"""
    with mock_post({"total": 0, "evolved": []}):
        result = runner.invoke(app, ["evolve", "scan"])
    assert result.exit_code == 0
    assert "没有域" in result.output or "阈值" in result.output


def test_evolve_scan_single_domain_new():
    """evolve scan：新建 Playbook 场景"""
    with mock_post({
        "total": 1,
        "evolved": [{
            "domain": "coding",
            "playbook_slug": "coding-best-practices",
            "playbook_version": 1,
            "lessons_used": 5,
            "is_new": True,
        }],
    }):
        result = runner.invoke(app, ["evolve", "scan"])
    assert result.exit_code == 0
    assert "1 个域" in result.output
    assert "coding" in result.output
    assert "coding-best-practices" in result.output
    assert "新建" in result.output
    assert "v1" in result.output


def test_evolve_scan_version_upgrade():
    """evolve scan：版本升级（非新建）场景"""
    with mock_post({
        "total": 1,
        "evolved": [{
            "domain": "research",
            "playbook_slug": "research-workflow",
            "playbook_version": 3,
            "lessons_used": 7,
            "is_new": False,
        }],
    }):
        result = runner.invoke(app, ["evolve", "scan"])
    assert result.exit_code == 0
    assert "升版" in result.output
    assert "v3" in result.output
    assert "7" in result.output  # lessons_used


def test_evolve_scan_multiple_domains():
    """evolve scan：多域同时进化"""
    with mock_post({
        "total": 2,
        "evolved": [
            {"domain": "coding",   "playbook_slug": "pb-1", "playbook_version": 1, "lessons_used": 5, "is_new": True},
            {"domain": "research", "playbook_slug": "pb-2", "playbook_version": 2, "lessons_used": 6, "is_new": False},
        ],
    }):
        result = runner.invoke(app, ["evolve", "scan"])
    assert result.exit_code == 0
    assert "2 个域" in result.output
    assert "coding" in result.output
    assert "research" in result.output


def test_evolve_scan_calls_correct_endpoint():
    """evolve scan：应调用 POST /api/evolution/scan"""
    with mock_post({"total": 0, "evolved": []}) as m:
        runner.invoke(app, ["evolve", "scan"])
    m.assert_called_once()
    args = m.call_args[0]
    assert "/api/evolution/scan" in args[0]


# ── evolve domain ────────────────────────────────────────────────────

def test_evolve_domain_success_new():
    """evolve domain：新建 Playbook 场景显示成功"""
    resp_mock = MagicMock()
    resp_mock.status_code = 200
    resp_mock.json.return_value = {
        "domain": "coding",
        "playbook_slug": "coding-bp",
        "playbook_version": 1,
        "lessons_used": 5,
        "is_new": True,
    }

    with patch("httpx.post", return_value=resp_mock):
        result = runner.invoke(app, ["evolve", "domain", "coding"])
    assert result.exit_code == 0
    assert "coding" in result.output
    assert "新建" in result.output
    assert "coding-bp" in result.output


def test_evolve_domain_success_upgrade():
    """evolve domain：版本升级场景"""
    resp_mock = MagicMock()
    resp_mock.status_code = 200
    resp_mock.json.return_value = {
        "domain": "research",
        "playbook_slug": "research-bp",
        "playbook_version": 4,
        "lessons_used": 8,
        "is_new": False,
    }

    with patch("httpx.post", return_value=resp_mock):
        result = runner.invoke(app, ["evolve", "domain", "research"])
    assert result.exit_code == 0
    assert "升版" in result.output
    assert "v4" in result.output


def test_evolve_domain_insufficient_lessons():
    """evolve domain：经验不足时（204）显示提示"""
    resp_mock = MagicMock()
    resp_mock.status_code = 204

    with patch("httpx.post", return_value=resp_mock):
        result = runner.invoke(app, ["evolve", "domain", "general"])
    assert result.exit_code == 0
    assert "不足" in result.output or "阈值" in result.output


def test_evolve_domain_calls_correct_url():
    """evolve domain：应调用正确的 API URL"""
    resp_mock = MagicMock()
    resp_mock.status_code = 204

    with patch("httpx.post", return_value=resp_mock) as m:
        runner.invoke(app, ["evolve", "domain", "coding"])
    m.assert_called_once()
    called_url = m.call_args[0][0]
    assert "/api/evolution/domain/coding" in called_url
