"""Dispatcher 基因上下文注入测试"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from greyfield_hive.workers.dispatcher import (
    DispatchWorker,
    _format_lessons_block,
    _format_playbooks_block,
    _infer_success,
    _SYNAPSE_DOMAIN,
)


# ── _infer_success ────────────────────────────────────────

def test_infer_success_rc_zero():
    assert _infer_success({"returncode": 0, "stdout": "task complete"}) is True

def test_infer_success_rc_nonzero():
    assert _infer_success({"returncode": 1, "stdout": "done"}) is False

def test_infer_success_error_in_stdout():
    assert _infer_success({"returncode": 0, "stdout": "Error: something went wrong"}) is False

def test_infer_success_exception_in_stdout():
    assert _infer_success({"returncode": 0, "stdout": "Traceback (most recent call last)..."}) is False

def test_infer_success_empty():
    assert _infer_success({}) is False


# ── _format_lessons_block ─────────────────────────────────

def test_format_lessons_empty():
    result = _format_lessons_block([])
    assert "暂无" in result

def test_format_lessons_success_outcome():
    lesson = MagicMock()
    lesson.outcome = "success"
    lesson.domain = "coding"
    lesson.content = "使用 pytest-asyncio 处理异步测试"
    result = _format_lessons_block([lesson])
    assert "✅" in result
    assert "coding" in result
    assert "pytest-asyncio" in result

def test_format_lessons_failure_outcome():
    lesson = MagicMock()
    lesson.outcome = "failure"
    lesson.domain = "devops"
    lesson.content = "Docker build 失败，需要先安装 buildkit"
    result = _format_lessons_block([lesson])
    assert "❌" in result

def test_format_lessons_truncates_long_content():
    lesson = MagicMock()
    lesson.outcome = "success"
    lesson.domain = "research"
    lesson.content = "X" * 500
    result = _format_lessons_block([lesson])
    # content is truncated to 200 chars
    assert len(result) < 500


# ── _format_playbooks_block ───────────────────────────────

def test_format_playbooks_empty():
    result = _format_playbooks_block([])
    assert "暂无" in result

def test_format_playbooks_shows_title_and_rate():
    pb = MagicMock()
    pb.title = "Python 调试手册"
    pb.version = 2
    pb.success_rate = 0.85
    pb.content = "1. 先复现 2. 缩小范围 3. 添加日志"
    result = _format_playbooks_block([pb])
    assert "Python 调试手册" in result
    assert "v2" in result
    assert "85%" in result


# ── _SYNAPSE_DOMAIN ───────────────────────────────────────

def test_synapse_domain_mapping():
    assert _SYNAPSE_DOMAIN["code-expert"] == "coding"
    assert _SYNAPSE_DOMAIN["research-analyst"] == "research"
    assert _SYNAPSE_DOMAIN["finance-scout"] == "finance"
    assert _SYNAPSE_DOMAIN["overmind"] == "general"


# ── _build_enriched_message ───────────────────────────────

@pytest.mark.asyncio
async def test_build_enriched_message_includes_gene_context():
    """基因上下文注入后，消息应包含 HIVE CONTEXT 块和原始消息"""
    worker = DispatchWorker()

    mock_lesson = MagicMock()
    mock_lesson.outcome = "success"
    mock_lesson.domain = "coding"
    mock_lesson.content = "使用 asyncio.gather 并发执行"

    mock_pb = MagicMock()
    mock_pb.title = "异步编程手册"
    mock_pb.version = 1
    mock_pb.success_rate = 0.9
    mock_pb.content = "步骤1：定义 async 函数"

    mock_bank = AsyncMock()
    mock_bank.search.return_value = [mock_lesson]
    mock_pb_svc = AsyncMock()
    mock_pb_svc.search.return_value = [mock_pb]

    with patch("greyfield_hive.workers.dispatcher.SessionLocal") as mock_session_cls:
        mock_db = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_db
        mock_session_cls.return_value.__aexit__.return_value = None

        with patch("greyfield_hive.workers.dispatcher.LessonsBank", return_value=mock_bank), \
             patch("greyfield_hive.workers.dispatcher.PlaybookService", return_value=mock_pb_svc):

            result = await worker._build_enriched_message(
                synapse="code-expert",
                message="实现一个异步任务队列",
                task_id="task-123",
                domain="coding",
            )

    assert "[HIVE CONTEXT]" in result
    assert "Task-ID" in result
    assert "task-123" in result
    assert "code-expert" in result
    assert "实现一个异步任务队列" in result
    assert "历史经验" in result
    assert "作战手册" in result


@pytest.mark.asyncio
async def test_build_enriched_message_fallback_on_error():
    """数据库查询失败时，应降级返回原始消息"""
    worker = DispatchWorker()

    with patch("greyfield_hive.workers.dispatcher.SessionLocal") as mock_session_cls:
        mock_session_cls.side_effect = Exception("DB 连接失败")

        result = await worker._build_enriched_message(
            synapse="code-expert",
            message="实现一个功能",
            task_id="task-999",
            domain="coding",
        )

    assert result == "实现一个功能"


@pytest.mark.asyncio
async def test_build_enriched_message_no_lessons_no_playbooks():
    """无历史经验时，应显示'暂无相关经验'"""
    worker = DispatchWorker()

    mock_bank = AsyncMock()
    mock_bank.search.return_value = []
    mock_pb_svc = AsyncMock()
    mock_pb_svc.search.return_value = []

    with patch("greyfield_hive.workers.dispatcher.SessionLocal") as mock_session_cls:
        mock_db = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_db
        mock_session_cls.return_value.__aexit__.return_value = None

        with patch("greyfield_hive.workers.dispatcher.LessonsBank", return_value=mock_bank), \
             patch("greyfield_hive.workers.dispatcher.PlaybookService", return_value=mock_pb_svc):

            result = await worker._build_enriched_message(
                synapse="research-analyst",
                message="分析市场趋势",
                task_id="",
                domain="research",
            )

    assert "暂无相关经验" in result
    assert "分析市场趋势" in result


# ── _write_outcome_lesson ─────────────────────────────────

@pytest.mark.asyncio
async def test_write_outcome_lesson_success():
    """成功结果应写入 outcome=success 的 Lesson"""
    worker = DispatchWorker()

    mock_bank = AsyncMock()
    mock_lesson = MagicMock()
    mock_lesson.id = "abcdef1234567890"
    mock_bank.add.return_value = mock_lesson

    with patch("greyfield_hive.workers.dispatcher.SessionLocal") as mock_session_cls:
        mock_db = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_db
        mock_session_cls.return_value.__aexit__.return_value = None

        with patch("greyfield_hive.workers.dispatcher.LessonsBank", return_value=mock_bank):
            await worker._write_outcome_lesson(
                task_id="task-001",
                synapse="code-expert",
                domain="coding",
                message="实现功能 X",
                result={"returncode": 0, "stdout": "功能已实现"},
            )

    mock_bank.add.assert_called_once()
    call_kwargs = mock_bank.add.call_args.kwargs
    assert call_kwargs["outcome"] == "success"
    assert call_kwargs["domain"] == "coding"
    assert "code-expert" in call_kwargs["content"]


@pytest.mark.asyncio
async def test_write_outcome_lesson_failure():
    """失败结果应写入 outcome=failure 的 Lesson"""
    worker = DispatchWorker()

    mock_bank = AsyncMock()
    mock_lesson = MagicMock()
    mock_lesson.id = "abcdef1234567890"
    mock_bank.add.return_value = mock_lesson

    with patch("greyfield_hive.workers.dispatcher.SessionLocal") as mock_session_cls:
        mock_db = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_db
        mock_session_cls.return_value.__aexit__.return_value = None

        with patch("greyfield_hive.workers.dispatcher.LessonsBank", return_value=mock_bank):
            await worker._write_outcome_lesson(
                task_id="task-002",
                synapse="code-expert",
                domain="coding",
                message="实现功能 Y",
                result={"returncode": 1, "stdout": "", "stderr": "build failed"},
            )

    call_kwargs = mock_bank.add.call_args.kwargs
    assert call_kwargs["outcome"] == "failure"


@pytest.mark.asyncio
async def test_write_outcome_lesson_skips_empty_message():
    """空 message 时不写入 Lesson"""
    worker = DispatchWorker()

    with patch("greyfield_hive.workers.dispatcher.SessionLocal") as mock_session_cls:
        mock_bank = AsyncMock()

        await worker._write_outcome_lesson(
            task_id="task-003",
            synapse="overmind",
            domain="general",
            message="",
            result={"returncode": 0, "stdout": "done"},
        )

    # SessionLocal should NOT have been called
    mock_session_cls.assert_not_called()


@pytest.mark.asyncio
async def test_write_outcome_lesson_silences_db_errors():
    """数据库错误不应向上抛出"""
    worker = DispatchWorker()

    with patch("greyfield_hive.workers.dispatcher.SessionLocal") as mock_session_cls:
        mock_session_cls.side_effect = Exception("DB 连接失败")

        # Should not raise
        await worker._write_outcome_lesson(
            task_id="task-004",
            synapse="code-expert",
            domain="coding",
            message="实现功能 Z",
            result={"returncode": 0, "stdout": "done"},
        )
