"""Chain Mode —— 顺序多 Agent 协作

流程：
  1. 按顺序依次调用 synapses
  2. 每一阶段的 stdout 追加到下一阶段的消息（前置上下文）
  3. 任一阶段失败则 fail-fast，停止后续执行
  4. 每阶段结果写入 progress_log；全链成功时最后阶段写入 Lessons Bank
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List

from loguru import logger

from greyfield_hive.db import SessionLocal
from greyfield_hive.services.event_bus import get_event_bus
from greyfield_hive.services.execution_events import publish_stage_event
from greyfield_hive.services.fitness_service import FitnessService
from greyfield_hive.workers.dispatcher import (
    DispatchWorker,
    _infer_success,
    _SYNAPSE_DOMAIN,
)


@dataclass
class ChainStageResult:
    synapse:     str
    returncode:  int
    stdout:      str
    stderr:      str
    success:     bool
    elapsed_sec: float = 0.0


@dataclass
class ChainResult:
    task_id:      str
    results:      List[ChainStageResult]
    success:      bool        # 全部阶段成功
    final_output: str = ""    # 最后一个执行阶段的 stdout


class ChainRunnerService:
    """Chain Mode 服务 —— 顺序调用 synapse 链，前后传递上下文"""

    def __init__(self, db=None) -> None:
        self._db = db
        self._worker = DispatchWorker()
        self._bus = get_event_bus()

    async def run(
        self,
        task_id: str,
        synapses: List[str],
        message: str,
        domain: str = "",
        trace_id: str = "",
    ) -> ChainResult:
        """顺序执行 synapses，返回 ChainResult"""
        if not synapses:
            return ChainResult(task_id=task_id, results=[], success=True, final_output="")

        if not domain:
            domain = _SYNAPSE_DOMAIN.get(synapses[0], "general")

        logger.info(f"[Chain] {task_id} 开始执行链: {' → '.join(synapses)}")
        await publish_stage_event(
            self._bus,
            trace_id=trace_id,
            producer="chain-runner",
            event_type="task.stage.started",
            task_id=task_id,
            stage="chain",
            payload={"mode": "chain", "synapses": list(synapses)},
        )

        results: List[ChainStageResult] = []
        current_message = message

        for i, synapse in enumerate(synapses):
            logger.info(f"[Chain] 阶段 {i+1}/{len(synapses)}: {synapse}")
            await publish_stage_event(
                self._bus,
                trace_id=trace_id,
                producer="chain-runner",
                event_type="task.stage.started",
                task_id=task_id,
                stage=f"chain:{i+1}",
                payload={"synapse": synapse, "index": i + 1, "total": len(synapses)},
            )

            enriched = await self._worker._build_enriched_message(
                synapse, current_message, task_id, domain
            )

            t0 = time.monotonic()
            raw = await self._worker._invoke_agent(synapse, enriched, task_id, trace_id)
            elapsed = time.monotonic() - t0

            stage = ChainStageResult(
                synapse=synapse,
                returncode=raw.get("returncode", -1),
                stdout=raw.get("stdout", ""),
                stderr=raw.get("stderr", ""),
                success=_infer_success(raw),
                elapsed_sec=elapsed,
            )
            results.append(stage)

            # 写入 progress_log
            await self._worker._persist_progress(task_id, synapse, raw)

            # 战功记录
            await _record_fitness(synapse, task_id, domain, stage.success, raw)

            if not stage.success:
                logger.warning(f"[Chain] 阶段 {synapse} 失败，中止执行链")
                await publish_stage_event(
                    self._bus,
                    trace_id=trace_id,
                    producer="chain-runner",
                    event_type="task.stage.failed",
                    task_id=task_id,
                    stage=f"chain:{i+1}",
                    payload={"synapse": synapse, "index": i + 1, "total": len(synapses)},
                )
                break
            await publish_stage_event(
                self._bus,
                trace_id=trace_id,
                producer="chain-runner",
                event_type="task.stage.completed",
                task_id=task_id,
                stage=f"chain:{i+1}",
                payload={"synapse": synapse, "index": i + 1, "total": len(synapses)},
            )

            # 将当前阶段输出拼入下一阶段消息
            if i < len(synapses) - 1:
                current_message = (
                    f"{message}\n\n"
                    f"[上一阶段 {synapse} 输出]\n"
                    f"{stage.stdout[:500]}"
                )

        all_success = all(r.success for r in results) and len(results) == len(synapses)
        final_output = results[-1].stdout if results else ""

        logger.info(
            f"[Chain] 结束: success={all_success}, "
            f"阶段={len(results)}/{len(synapses)}"
        )

        # 全链成功时写入最后阶段的经验
        if all_success and results:
            last = results[-1]
            await self._worker._write_outcome_lesson(
                task_id=task_id,
                synapse=last.synapse,
                domain=domain,
                message=message,
                result={"returncode": last.returncode, "stdout": last.stdout},
            )

        await publish_stage_event(
            self._bus,
            trace_id=trace_id,
            producer="chain-runner",
            event_type="task.stage.completed" if all_success else "task.stage.failed",
            task_id=task_id,
            stage="chain",
            payload={"mode": "chain", "success": all_success, "total": len(synapses)},
        )

        return ChainResult(
            task_id=task_id,
            results=results,
            success=all_success,
            final_output=final_output,
        )


# ── 适存度记录工具 ─────────────────────────────────────────────────────

async def _record_fitness(
    synapse: str,
    task_id: str,
    domain: str,
    success: bool,
    result: dict,
) -> None:
    """将执行结果写入战功记录（Chain/Trial/Swarm 共用）"""
    try:
        rc = result.get("returncode", -1)
        score = 1.0 if success else (0.5 if rc == 0 else 0.3)
        async with SessionLocal() as db:
            svc = FitnessService(db)
            await svc.record_execution(
                synapse_id=synapse,
                task_id=task_id or None,
                domain=domain,
                success=success,
                score=score,
            )
            await db.commit()
    except Exception as e:
        from loguru import logger
        logger.warning(f"[Fitness] 战功记录失败 {synapse}: {e}")
