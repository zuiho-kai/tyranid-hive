"""Swarm Mode —— 并发 Unit 池，批量独立任务并行执行

流程：
  1. 接收 task_id + units（每个 unit 有独立 synapse + message）
  2. 通过 asyncio.gather 并发执行所有 unit（受 max_concurrent 信号量限制）
  3. 每个 unit 结果独立写入 progress_log 和 Lessons Bank
  4. 返回 SwarmResult（含所有 unit 结果 + 成功率统计）

适用场景：
  - 批量独立子任务（互不依赖）
  - 多目标并行研究
  - 并发代码生成多个独立模块
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import List

from loguru import logger

from greyfield_hive.workers.dispatcher import (
    DispatchWorker,
    _infer_success,
    _SYNAPSE_DOMAIN,
)


@dataclass
class SwarmUnit:
    """单个 Swarm Unit 的输入"""
    synapse: str
    message: str
    domain: str = ""


@dataclass
class SwarmUnitResult:
    """单个 Swarm Unit 的执行结果"""
    synapse:     str
    message:     str          # 原始 message（摘要）
    returncode:  int
    stdout:      str
    stderr:      str
    success:     bool
    elapsed_sec: float = 0.0


@dataclass
class SwarmResult:
    task_id:      str
    results:      List[SwarmUnitResult]
    success_count: int = 0
    fail_count:    int = 0
    total:         int = 0

    def __post_init__(self):
        self.total         = len(self.results)
        self.success_count = sum(1 for r in self.results if r.success)
        self.fail_count    = self.total - self.success_count

    @property
    def success_rate(self) -> float:
        return self.success_count / self.total if self.total else 0.0

    @property
    def all_success(self) -> bool:
        return self.fail_count == 0 and self.total > 0


class SwarmRunnerService:
    """Swarm Mode 服务 —— 并发 Unit 池执行"""

    DEFAULT_MAX_CONCURRENT = 5

    def __init__(self, db=None) -> None:
        self._db = db
        self._worker = DispatchWorker()

    async def run(
        self,
        task_id: str,
        units: List[SwarmUnit],
        trace_id: str = "",
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
    ) -> SwarmResult:
        """并发执行所有 units，返回 SwarmResult"""
        if not units:
            return SwarmResult(task_id=task_id, results=[])

        sem = asyncio.Semaphore(max_concurrent)
        logger.info(
            f"[Swarm] {task_id} 启动 {len(units)} 个 units，"
            f"最大并发={max_concurrent}"
        )

        async def run_unit(unit: SwarmUnit, idx: int) -> SwarmUnitResult:
            async with sem:
                domain = unit.domain or _SYNAPSE_DOMAIN.get(unit.synapse, "general")
                logger.info(f"[Swarm] unit[{idx}] {unit.synapse}: {unit.message[:40]}…")

                enriched = await self._worker._build_enriched_message(
                    unit.synapse, unit.message, task_id, domain
                )

                t0 = time.monotonic()
                raw = await self._worker._invoke_agent(
                    unit.synapse, enriched, task_id, trace_id
                )
                elapsed = time.monotonic() - t0

                result = SwarmUnitResult(
                    synapse=unit.synapse,
                    message=unit.message[:120],
                    returncode=raw.get("returncode", -1),
                    stdout=raw.get("stdout", ""),
                    stderr=raw.get("stderr", ""),
                    success=_infer_success(raw),
                    elapsed_sec=elapsed,
                )

                # 写入 progress_log
                await self._worker._persist_progress(unit.synapse, unit.synapse, raw)

                # 写入 Lessons Bank
                await self._worker._write_outcome_lesson(
                    task_id=task_id,
                    synapse=unit.synapse,
                    domain=domain,
                    message=unit.message,
                    result=raw,
                )

                status = "✅" if result.success else "❌"
                logger.info(
                    f"[Swarm] unit[{idx}] {unit.synapse} 完成 "
                    f"{status} rc={result.returncode} "
                    f"{result.elapsed_sec:.1f}s"
                )
                return result

        tasks = [run_unit(u, i) for i, u in enumerate(units)]
        results = await asyncio.gather(*tasks)

        swarm = SwarmResult(task_id=task_id, results=list(results))
        logger.info(
            f"[Swarm] 完成: 总={swarm.total} "
            f"成功={swarm.success_count} 失败={swarm.fail_count} "
            f"成功率={swarm.success_rate:.0%}"
        )
        return swarm
