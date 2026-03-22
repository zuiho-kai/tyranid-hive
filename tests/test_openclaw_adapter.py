"""OpenClaw 原生适配器测试"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── 协议 / 接口测试 ───────────────────────────────────────

def test_mock_adapter_returns_success():
    """MockAdapter 应返回 returncode=0"""
    from greyfield_hive.adapters.openclaw import MockAdapter
    adapter = MockAdapter()
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(
        adapter.invoke("code-expert", "实现 hello world", {}, 30)
    )
    assert result["returncode"] == 0
    assert "mock" in result["stdout"].lower() or "code-expert" in result["stdout"]
    assert result["stderr"] == ""


@pytest.mark.asyncio
async def test_mock_adapter_includes_synapse_in_output():
    """MockAdapter 输出包含 synapse 名"""
    from greyfield_hive.adapters.openclaw import MockAdapter
    adapter = MockAdapter()
    result = await adapter.invoke("research-analyst", "搜索信息", {}, 30)
    assert "research-analyst" in result["stdout"]


@pytest.mark.asyncio
async def test_subprocess_adapter_timeout():
    """AsyncSubprocessAdapter 超时时返回 returncode=-1"""
    from greyfield_hive.adapters.openclaw import AsyncSubprocessAdapter

    # 用 sleep 命令模拟超时
    adapter = AsyncSubprocessAdapter(cmd=["python", "-c", "import time; time.sleep(60)"])
    result = await adapter.invoke("code-expert", "任务", {}, timeout=1)
    assert result["returncode"] == -1
    assert "timeout" in result["stderr"].lower()


@pytest.mark.asyncio
async def test_subprocess_adapter_captures_stdout():
    """AsyncSubprocessAdapter 应捕获进程标准输出"""
    from greyfield_hive.adapters.openclaw import AsyncSubprocessAdapter

    adapter = AsyncSubprocessAdapter(cmd=["python", "-c", "print('hello from agent')"])
    result = await adapter.invoke("code-expert", "任务", {}, timeout=10)
    assert result["returncode"] == 0
    assert "hello from agent" in result["stdout"]


@pytest.mark.asyncio
async def test_subprocess_adapter_captures_stderr():
    """AsyncSubprocessAdapter 应捕获 stderr"""
    from greyfield_hive.adapters.openclaw import AsyncSubprocessAdapter
    import sys

    adapter = AsyncSubprocessAdapter(
        cmd=["python", "-c", f"import sys; sys.stderr.write('error msg'); sys.exit(1)"]
    )
    result = await adapter.invoke("code-expert", "任务", {}, timeout=10)
    assert result["returncode"] != 0
    assert "error msg" in result["stderr"]


@pytest.mark.asyncio
async def test_subprocess_adapter_passes_env():
    """AsyncSubprocessAdapter 应将 env 传递给子进程"""
    import os
    from greyfield_hive.adapters.openclaw import AsyncSubprocessAdapter

    adapter = AsyncSubprocessAdapter(cmd=["python", "-c", "import os; print(os.environ.get('HIVE_TEST_VAR','missing'))"])
    env = {**os.environ, "HIVE_TEST_VAR": "hive_value_42"}
    result = await adapter.invoke("code-expert", "任务", env, timeout=10)
    assert "hive_value_42" in result["stdout"]


# ── 适配器工厂测试 ────────────────────────────────────────

def test_get_adapter_returns_mock_when_no_cli(monkeypatch):
    """openclaw/claude 均不存在时，应返回 MockAdapter"""
    from greyfield_hive.adapters.openclaw import get_adapter, MockAdapter
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    adapter = get_adapter()
    assert isinstance(adapter, MockAdapter)


def test_get_adapter_prefers_openclaw_over_claude(monkeypatch):
    """同时存在 openclaw 和 claude 时，优先使用 openclaw"""
    from greyfield_hive.adapters.openclaw import get_adapter, AsyncSubprocessAdapter

    def fake_which(cmd):
        if cmd == "openclaw":
            return "/usr/local/bin/openclaw"
        if cmd == "claude":
            return "/usr/local/bin/claude"
        return None

    monkeypatch.setattr("shutil.which", fake_which)
    adapter = get_adapter()
    assert isinstance(adapter, AsyncSubprocessAdapter)
    assert "openclaw" in adapter.cmd[0]


def test_get_adapter_falls_back_to_claude(monkeypatch):
    """openclaw 不存在但 claude 存在时，使用 claude"""
    from greyfield_hive.adapters.openclaw import get_adapter, AsyncSubprocessAdapter

    def fake_which(cmd):
        return "/usr/local/bin/claude" if cmd == "claude" else None

    monkeypatch.setattr("shutil.which", fake_which)
    adapter = get_adapter()
    assert isinstance(adapter, AsyncSubprocessAdapter)
    assert "claude" in adapter.cmd[0]


# ── DispatchWorker 集成：使用新适配器 ────────────────────

@pytest.mark.asyncio
async def test_dispatcher_uses_adapter():
    """DispatchWorker._invoke_agent 应通过适配器调用"""
    from greyfield_hive.workers.dispatcher import DispatchWorker
    from greyfield_hive.adapters.openclaw import MockAdapter

    worker = DispatchWorker()
    worker._adapter = MockAdapter()

    result = await worker._invoke_agent("code-expert", "测试消息", "T001", "trace-001")
    assert result["returncode"] == 0
    assert "code-expert" in result["stdout"]


@pytest.mark.asyncio
async def test_dispatcher_inject_env_vars():
    """_invoke_agent 应将 HIVE_TASK_ID 等环境变量注入"""
    from greyfield_hive.workers.dispatcher import DispatchWorker
    import os

    captured_env: dict = {}

    class CapturingAdapter:
        async def invoke(self, synapse, message, env, timeout):
            captured_env.update(env)
            return {"returncode": 0, "stdout": "OK", "stderr": ""}

    worker = DispatchWorker()
    worker._adapter = CapturingAdapter()

    await worker._invoke_agent("code-expert", "测试", "TASK-99", "TRACE-88")
    assert captured_env.get("HIVE_TASK_ID") == "TASK-99"
    assert captured_env.get("HIVE_TRACE_ID") == "TRACE-88"
    assert captured_env.get("HIVE_SYNAPSE") == "code-expert"


@pytest.mark.asyncio
async def test_dispatcher_adapter_error_returns_error_dict():
    """适配器抛出异常时，_invoke_agent 应返回 returncode=-1"""
    from greyfield_hive.workers.dispatcher import DispatchWorker

    class ErrorAdapter:
        async def invoke(self, synapse, message, env, timeout):
            raise RuntimeError("模拟故障")

    worker = DispatchWorker()
    worker._adapter = ErrorAdapter()

    result = await worker._invoke_agent("code-expert", "任务", "T1", "T2")
    assert result["returncode"] == -1
    assert "模拟故障" in result["stderr"]
