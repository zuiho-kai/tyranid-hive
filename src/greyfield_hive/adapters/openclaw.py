"""OpenClaw 原生适配器 —— 替代 subprocess.run + loop.run_in_executor

设计：可插拔策略模式
  AsyncSubprocessAdapter  纯 asyncio subprocess（非阻塞，默认）
  MockAdapter             开发/测试用 mock

探测顺序（get_adapter）：
  1. openclaw CLI （OpenClaw 框架）
  2. codex CLI    （OpenAI Codex CLI，不受进程树 403 限制）
  3. claude CLI   （Claude Code 原生 CLI，嵌套调用会被进程树检测 403）
  4. MockAdapter  （均不可用时降级）
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
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

# 子进程中必须清除的环境变量，否则 claude -p 会返回 403
_BLOCKED_ENV_KEYS = frozenset({"CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"})


class ClaudeCodeAdapter:
    """Claude Code CLI 适配器 —— 使用 claude -p 执行任务

    与 AsyncSubprocessAdapter 的区别：
    - 不传 synapse 参数（synapse 上下文已由 dispatcher 注入 message）
    - 使用 -p 标志（非交互式输出模式）
    - 清除 CLAUDECODE / CLAUDE_CODE_ENTRYPOINT，防止嵌套调用返回 403
    - --output-format json 返回单条 JSON，解析 result 字段
    """

    async def invoke(
        self,
        synapse: str,
        message: str,
        env: dict,
        timeout: int,
    ) -> dict:
        import json as _json

        # 清除会触发 403 的环境变量
        clean_env = {k: v for k, v in env.items() if k not in _BLOCKED_ENV_KEYS}

        logger.debug(f"[ClaudeCode] 调用 synapse={synapse}, msg_len={len(message)}")
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude", "-p", message,
                "--output-format", "json",
                "--dangerously-skip-permissions",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=clean_env,
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

            raw = stdout_bytes.decode("utf-8", errors="replace")
            # 解析 JSON 输出，提取 result 字段作为 stdout
            try:
                data = _json.loads(raw)
                if data.get("is_error"):
                    stdout_text = data.get("result", raw)
                    returncode = proc.returncode if proc.returncode is not None else 1
                else:
                    stdout_text = data.get("result", raw)
                    returncode = 0
            except _json.JSONDecodeError:
                stdout_text = raw
                returncode = proc.returncode

            return {
                "returncode": returncode,
                "stdout":     stdout_text[-5000:],
                "stderr":     stderr_bytes.decode("utf-8", errors="replace")[-2000:],
            }
        except FileNotFoundError:
            logger.warning("[ClaudeCode] claude CLI 不可用")
            raise
        except Exception as e:
            logger.error(f"[ClaudeCode] 调用失败: {e}")
            raise


# ── Codex CLI 适配器 ─────────────────────────────────────

class CodexAdapter:
    """OpenAI Codex CLI 适配器 —— 使用 codex exec 执行任务

    相比 ClaudeCodeAdapter：
    - 不受 CLAUDECODE 进程树检测限制，无 403 问题
    - 使用 codex exec --dangerously-bypass-approvals-and-sandbox

    关键设计（参考 clowder-ai CodexAgentService）：
    - 通过 tempfile.mkdtemp() 创建干净 cwd，避免 codex 读取项目
      CLAUDE.md / AGENTS.md 而忽略实际任务
    - 使用 --skip-git-repo-check 允许在非 git 目录运行
    """

    async def invoke(
        self,
        synapse: str,
        message: str,
        env: dict,
        timeout: int,
    ) -> dict:
        logger.debug(f"[Codex] 调用 synapse={synapse}, msg_len={len(message)}")

        # 创建干净的临时目录作为 cwd，防止 codex 读取项目指令文件
        cwd = tempfile.mkdtemp(prefix="hive-codex-")

        # Windows 上 .CMD 文件需要通过 cmd.exe /c 调用
        codex_bin = shutil.which("codex") or "codex"
        base_args = [
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "--skip-git-repo-check",
            "-",
        ]
        if codex_bin.upper().endswith(".CMD"):
            cmd_args = ["cmd.exe", "/c", codex_bin] + base_args
        else:
            cmd_args = [codex_bin] + base_args

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=cwd,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(message.encode("utf-8")), timeout=timeout
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                    await proc.wait()
                except ProcessLookupError:
                    pass
                logger.error(f"[Codex] {synapse} 超时 {timeout}s")
                return {"returncode": -1, "stdout": "", "stderr": f"timeout after {timeout}s"}

            return {
                "returncode": proc.returncode,
                "stdout":     stdout_bytes.decode("utf-8", errors="replace")[-5000:],
                "stderr":     stderr_bytes.decode("utf-8", errors="replace")[-2000:],
            }
        except FileNotFoundError:
            logger.warning("[Codex] codex CLI 不可用")
            raise
        except Exception as e:
            logger.error(f"[Codex] 调用失败: {e}")
            raise
        finally:
            shutil.rmtree(cwd, ignore_errors=True)


# ── 工厂函数 ─────────────────────────────────────────────

def get_adapter(force_mock: bool = False) -> OpenClawAdapter:
    """探测可用 CLI，返回最合适的适配器

    探测顺序：
      1. HIVE_ADAPTER=mock  → MockAdapter（强制 mock，常用于测试）
      2. HIVE_ADAPTER=codex → CodexAdapter（强制 codex）
      3. openclaw 可执行文件 → AsyncSubprocessAdapter (openclaw agent --agent)
      4. codex 可执行文件   → CodexAdapter (codex exec)
      5. claude 可执行文件  → ClaudeCodeAdapter (claude -p，嵌套有 403 风险)
      6. 均不可用           → MockAdapter
    """
    if force_mock or os.environ.get("HIVE_ADAPTER") == "mock":
        logger.debug("[Adapter] 强制使用 MockAdapter")
        return MockAdapter()

    if os.environ.get("HIVE_ADAPTER") == "codex":
        logger.info("[Adapter] 强制使用 CodexAdapter（HIVE_ADAPTER=codex）")
        return CodexAdapter()

    if os.environ.get("HIVE_ADAPTER") == "claude":
        logger.info("[Adapter] 强制使用 ClaudeCodeAdapter（HIVE_ADAPTER=claude）")
        return ClaudeCodeAdapter()

    if shutil.which("openclaw"):
        logger.info("[Adapter] 探测到 openclaw CLI，使用 AsyncSubprocessAdapter")
        return AsyncSubprocessAdapter(cmd=["openclaw", "agent", "--agent"])

    if shutil.which("codex"):
        logger.info("[Adapter] 探测到 codex CLI，使用 CodexAdapter")
        return CodexAdapter()

    if shutil.which("claude"):
        logger.info("[Adapter] 探测到 claude CLI，使用 ClaudeCodeAdapter（注意：嵌套调用可能 403）")
        return ClaudeCodeAdapter()

    logger.info("[Adapter] 未探测到 CLI，降级到 MockAdapter（开发模式）")
    return MockAdapter()
