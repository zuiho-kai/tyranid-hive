"""派发器 Worker —— 消费 task.dispatch 事件，调用 OpenClaw CLI 执行小主脑

工作流：
  task.dispatch 事件 → 读取 synapse ID → 调用 openclaw / python agent → 发布 agent.thoughts
"""

import asyncio
import os
import subprocess
from pathlib import Path

from loguru import logger

from greyfield_hive.services.event_bus import (
    get_event_bus,
    BusEvent,
    TOPIC_TASK_DISPATCH,
    TOPIC_AGENT_THOUGHTS,
    TOPIC_AGENT_HEARTBEAT,
)


# ── 小主脑元数据（人类可读）────────────────────────────────
SYNAPSE_META: dict[str, dict] = {
    "overmind": {
        "name": "主脑",
        "role": "任务拆解与调度决策",
        "emoji": "🧠",
        "tier": 1,
    },
    "evolution-master": {
        "name": "进化大师",
        "role": "经验萃取与基因进化",
        "emoji": "🧬",
        "tier": 2,
    },
    "code-expert": {
        "name": "代码专家",
        "role": "代码实现与调试",
        "emoji": "💻",
        "tier": 2,
    },
    "research-analyst": {
        "name": "研究分析师",
        "role": "信息收集与分析",
        "emoji": "🔍",
        "tier": 2,
    },
    "finance-scout": {
        "name": "金融侦察虫",
        "role": "市场数据获取与金融信息分析",
        "emoji": "📈",
        "tier": 2,
    },
}


class DispatchWorker:
    """派发器 —— 将任务分配给对应的小主脑（OpenClaw agent）"""

    def __init__(self, max_concurrent: int = 3) -> None:
        self.bus = get_event_bus()
        self._running = False
        self._sem = asyncio.Semaphore(max_concurrent)
        self._q: asyncio.Queue | None = None
        # OpenClaw 工作目录
        self._claw_dir = Path(os.environ.get("HIVE_CLAW_DIR", "."))

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        self._running = True
        self._q = self.bus.subscribe(TOPIC_TASK_DISPATCH)
        logger.info("[Dispatcher] 启动，最大并发=" + str(self._sem._value))

        while self._running:
            try:
                event: BusEvent = self._q.get_nowait()
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.1)
                continue

            asyncio.create_task(self._dispatch(event))

    async def stop(self) -> None:
        self._running = False
        logger.info("[Dispatcher] 停止")

    # ── 派发一个任务 ──────────────────────────────────────

    async def _dispatch(self, event: BusEvent) -> None:
        async with self._sem:
            payload  = event.payload
            task_id  = payload.get("task_id", "")
            synapse  = payload.get("synapse", "overmind")
            message  = payload.get("message", "")
            trace_id = event.trace_id

            await self.bus.publish(
                topic=TOPIC_AGENT_HEARTBEAT,
                trace_id=trace_id,
                event_type="agent.dispatch.start",
                producer="dispatcher",
                payload={"task_id": task_id, "synapse": synapse},
            )

            logger.info(f"[Dispatcher] 派发 {task_id} → {synapse}: {message[:60]}")
            result = await self._invoke_agent(synapse, message, task_id, trace_id)

            await self.bus.publish(
                topic=TOPIC_AGENT_THOUGHTS,
                trace_id=trace_id,
                event_type="agent.output",
                producer=f"synapse.{synapse}",
                payload={
                    "task_id":     task_id,
                    "synapse":     synapse,
                    "output":      result.get("stdout", ""),
                    "return_code": result.get("returncode", -1),
                    "error":       result.get("stderr", ""),
                },
            )

            if result.get("returncode", -1) != 0:
                logger.warning(f"[Dispatcher] {synapse} 返回非零: {result.get('returncode')}")

    # ── 调用 OpenClaw ────────────────────────────────────

    async def _invoke_agent(
        self,
        synapse: str,
        message: str,
        task_id: str,
        trace_id: str,
        timeout: int = 300,
    ) -> dict:
        """
        尝试通过 OpenClaw CLI 调用 agent。
        若 CLI 不可用（开发环境），返回 mock 结果。
        """
        env = {
            **os.environ,
            "HIVE_TASK_ID":   task_id,
            "HIVE_TRACE_ID":  trace_id,
            "HIVE_SYNAPSE":   synapse,
            "HIVE_API_URL":   os.environ.get("HIVE_API_URL", "http://localhost:8765"),
        }

        # 优先尝试 openclaw CLI
        cmd = ["openclaw", "agent", "--agent", synapse, "-m", message]

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=env,
                    cwd=str(self._claw_dir),
                ),
            )
            return {
                "returncode": result.returncode,
                "stdout":     result.stdout[-5000:],
                "stderr":     result.stderr[-2000:],
            }
        except FileNotFoundError:
            # openclaw 未安装 → 开发模式 mock
            logger.debug(f"[Dispatcher] openclaw 未安装，使用 mock 模式 synapse={synapse}")
            return {
                "returncode": 0,
                "stdout":     f"[mock] {synapse} 处理完毕: {message[:80]}",
                "stderr":     "",
            }
        except subprocess.TimeoutExpired:
            logger.error(f"[Dispatcher] {synapse} 超时 {timeout}s")
            return {"returncode": -1, "stdout": "", "stderr": f"timeout after {timeout}s"}
        except Exception as e:
            logger.error(f"[Dispatcher] 调用失败: {e}")
            return {"returncode": -1, "stdout": "", "stderr": str(e)}
