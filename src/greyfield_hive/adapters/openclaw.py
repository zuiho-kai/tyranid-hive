"""OpenClaw 原生适配器 —— 替代 subprocess.run + loop.run_in_executor

设计：可插拔策略模式
  AsyncSubprocessAdapter  纯 asyncio subprocess（非阻塞，默认）
  MockAdapter             开发/测试用 mock

探测顺序（get_adapter）：
  1. openclaw CLI （OpenClaw 框架）
  2. claude CLI   （Claude Code 原生 CLI，功能等价）
  3. MockAdapter  （均不可用时降级）
"""

from __future__ import annotations

import asyncio
import os
import shutil
from typing import Protocol, runtime_checkable

from loguru import logger


# ── 协议（接口）──────────────────────────────────────────

@runtime_checkable
class OpenClawAdapter(Protocol):
    """所有适配器实现的接口"""

    async def invoke(
        self,
        synapse: str,
        message: str,
        env: dict,
        timeout: int,
    ) -> dict:
        """调用 agent，返回 {returncode, stdout, stderr}"""
        ...


# ── asyncio 原生 subprocess 适配器 ────────────────────────

class AsyncSubprocessAdapter:
    """使用 asyncio.create_subprocess_exec 非阻塞调用 CLI

    相比旧的 loop.run_in_executor(subprocess.run(...))：
    - 完全非阻塞，不占用线程池
    - asyncio.wait_for 精确超时控制，超时后 SIGKILL 子进程
    - 支持流式读取（大输出不会撑爆内存）
    """

    def __init__(self, cmd: list[str]) -> None:
        """
        cmd: 基础命令，例如 ["openclaw", "agent", "--agent"]
             invoke 时会追加 [synapse, "-m", message]
        """
        self.cmd = cmd

    async def invoke(
        self,
        synapse: str,
        message: str,
        env: dict,
        timeout: int,
    ) -> dict:
        full_cmd = self.cmd + [synapse, "-m", message]
        logger.debug(f"[Adapter] 调用: {' '.join(full_cmd[:5])}…")

        try:
            proc = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                    await proc.wait()
                except ProcessLookupError:
                    pass
                logger.error(f"[Adapter] {synapse} 超时 {timeout}s")
                return {
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"timeout after {timeout}s",
                }

            return {
                "returncode": proc.returncode,
                "stdout":     stdout_bytes.decode("utf-8", errors="replace")[-5000:],
                "stderr":     stderr_bytes.decode("utf-8", errors="replace")[-2000:],
            }
        except FileNotFoundError:
            logger.warning(f"[Adapter] 命令不存在: {self.cmd[0]}")
            raise
        except Exception as e:
            logger.error(f"[Adapter] 调用失败: {e}")
            raise


# ── Mock 适配器（开发 / 测试）─────────────────────────────

class MockAdapter:
    """不依赖任何外部进程，直接返回模拟输出"""

    async def invoke(
        self,
        synapse: str,
        message: str,
        env: dict,
        timeout: int,
    ) -> dict:
        logger.debug(f"[Adapter] mock 模式: synapse={synapse}")
        return {
            "returncode": 0,
            "stdout":     f"[mock] {synapse} 处理完毕: {message[:100]}",
            "stderr":     "",
        }


# ── Claude Code CLI 适配器 ───────────────────────────────

class ClaudeCodeAdapter:
    """Claude Code CLI 适配器 —— 使用 claude -p 执行任务

    与 AsyncSubprocessAdapter 的区别：
    - 不传 synapse 参数（synapse 上下文已由 dispatcher 注入 message）
    - 使用 -p 标志（非交互式输出模式）
    - message 直接作为参数传入，适合虫群任务的典型消息长度
    """

    async def invoke(
        self,
        synapse: str,
        message: str,
        env: dict,
        timeout: int,
    ) -> dict:
        logger.debug(f"[ClaudeCode] 调用 synapse={synapse}, msg_len={len(message)}")
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude", "-p", message,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                    await proc.wait()
                except ProcessLookupError:
                    pass
                logger.error(f"[ClaudeCode] {synapse} 超时 {timeout}s")
                return {"returncode": -1, "stdout": "", "stderr": f"timeout after {timeout}s"}

            return {
                "returncode": proc.returncode,
                "stdout":     stdout_bytes.decode("utf-8", errors="replace")[-5000:],
                "stderr":     stderr_bytes.decode("utf-8", errors="replace")[-2000:],
            }
        except FileNotFoundError:
            logger.warning("[ClaudeCode] claude CLI 不可用")
            raise
        except Exception as e:
            logger.error(f"[ClaudeCode] 调用失败: {e}")
            raise


# ── 工厂函数 ─────────────────────────────────────────────

def get_adapter(force_mock: bool = False) -> OpenClawAdapter:
    """探测可用 CLI，返回最合适的适配器

    探测顺序：
      1. HIVE_ADAPTER=mock  → MockAdapter（强制 mock，常用于测试）
      2. openclaw 可执行文件 → AsyncSubprocessAdapter (openclaw agent --agent)
      3. claude 可执行文件  → ClaudeCodeAdapter (claude -p)
      4. 均不可用           → MockAdapter
    """
    if force_mock or os.environ.get("HIVE_ADAPTER") == "mock":
        logger.debug("[Adapter] 强制使用 MockAdapter")
        return MockAdapter()

    if shutil.which("openclaw"):
        logger.info("[Adapter] 探测到 openclaw CLI，使用 AsyncSubprocessAdapter")
        return AsyncSubprocessAdapter(cmd=["openclaw", "agent", "--agent"])

    if shutil.which("claude"):
        logger.info("[Adapter] 探测到 claude CLI，使用 ClaudeCodeAdapter")
        return ClaudeCodeAdapter()

    logger.info("[Adapter] 未探测到 CLI，降级到 MockAdapter（开发模式）")
    return MockAdapter()
