"""Trial Race 赛马机制 —— 两个 Synapse 并行竞争同一任务，胜者经验入库

流程：
  1. 接收 task_id + 两个 synapse + message + domain
  2. 异步并行调用两个 synapse（通过 DispatchWorker._invoke_agent）
  3. 比较结果：success > failure；同为 success 则响应更丰富者胜
  4. 双方结果均写入 progress_log；胜者额外写入 Lessons Bank
  5. 返回 TrialResult（含双方详情 + 胜者）
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger

from greyfield_hive.workers.dispatcher import (
    DispatchWorker,
    _infer_success,
    _SYNAPSE_DOMAIN,
)


@dataclass
class SynapseResult:
    synapse:     str
    returncode:  int
    stdout:      str
    stderr:      str
    success:     bool
    elapsed_sec: float = 0.0


@dataclass
class TrialResult:
    task_id:    str
    winner:     Optional[str]            # synapse name or None（均失败）
    results:    dict[str, SynapseResult]  # synapse → result
    tie:        bool = False             # 双方同样成功/失败，按启发规则选


# ── 胜负判断 ──────────────────────────────────────────────

def _pick_winner(a: SynapseResult, b: SynapseResult) -> Optional[str]:
    """返回胜者 synapse name；均失败返回 None"""
    if a.success and not b.success:
        return a.synapse
    if b.success and not a.success:
        return b.synapse
    if not a.success and not b.success:
        return None
    # 双方都成功 → 以 stdout 字数作为"丰富度"指标（更多输出 = 更详细的工作）
    return a.synapse if len(a.stdout) >= len(b.stdout) else b.synapse


# ── Trial Race ────────────────────────────────────────────

class TrialRaceService:
    """赛马服务 —— 不持有长生命周期 worker，每次创建临时 DispatchWorker 进行调用"""

    def __init__(self, db=None) -> None:
        self._db = db
        self._worker = DispatchWorker()

    async def run(
        self,
        task_id: str,
        synapse_a: str,
        synapse_b: str,
        message: str,
        domain: str = "",
        trace_id: str = "",
    ) -> TrialResult:
        """
        并行执行两个 synapse，返回 TrialResult。
        同时将双方结果写入 task.progress_log；胜者写入 Lessons Bank。
        """
        if not domain:
            domain = _SYNAPSE_DOMAIN.get(synapse_a, "general")

        logger.info(f"[TrialRace] {task_id} 开始赛马: {synapse_a} vs {synapse_b}")

        # 构建富提示词（共用同一个 message 和 domain）
        enriched_a, enriched_b = await asyncio.gather(
            self._worker._build_enriched_message(synapse_a, message, task_id, domain),
            self._worker._build_enriched_message(synapse_b, message, task_id, domain),
        )

        # 并行调用两个 synapse
        import time
        t0 = time.monotonic()
        (raw_a, raw_b) = await asyncio.gather(
            self._worker._invoke_agent(synapse_a, enriched_a, task_id, trace_id),
            self._worker._invoke_agent(synapse_b, enriched_b, task_id, trace_id),
        )
        elapsed = time.monotonic() - t0

        result_a = SynapseResult(
            synapse=synapse_a,
            returncode=raw_a.get("returncode", -1),
            stdout=raw_a.get("stdout", ""),
            stderr=raw_a.get("stderr", ""),
            success=_infer_success(raw_a),
            elapsed_sec=elapsed,
        )
        result_b = SynapseResult(
            synapse=synapse_b,
            returncode=raw_b.get("returncode", -1),
            stdout=raw_b.get("stdout", ""),
            stderr=raw_b.get("stderr", ""),
            success=_infer_success(raw_b),
            elapsed_sec=elapsed,
        )

        winner_name = _pick_winner(result_a, result_b)
        tie = (result_a.success == result_b.success)

        trial = TrialResult(
            task_id=task_id,
            winner=winner_name,
            results={synapse_a: result_a, synapse_b: result_b},
            tie=tie,
        )

        logger.info(
            f"[TrialRace] 结果: {synapse_a}={'✅' if result_a.success else '❌'} "
            f"{synapse_b}={'✅' if result_b.success else '❌'} "
            f"胜者={winner_name or '无'}"
        )

        # 回写 progress_log + 写入经验
        await self._persist_all(trial, message, domain)

        return trial

    async def _persist_all(
        self, trial: TrialResult, message: str, domain: str
    ) -> None:
        """将双方结果写入 progress_log；胜者写入 Lessons Bank"""
        if not trial.task_id:
            return

        for synapse, res in trial.results.items():
            raw = {"returncode": res.returncode, "stdout": res.stdout, "stderr": res.stderr}
            await self._worker._persist_progress(trial.task_id, synapse, raw)

        # 胜者经验入库
        if trial.winner:
            winner_res = trial.results[trial.winner]
            outcome = "success" if winner_res.success else "partial"
            loser   = [s for s in trial.results if s != trial.winner][0]
            content = (
                f"[赛马胜者={trial.winner} vs {loser}] {message[:120]}\n"
                f"输出摘要: {winner_res.stdout[:200]}"
            )
            await self._worker._write_outcome_lesson(
                task_id=trial.task_id,
                synapse=trial.winner,
                domain=domain,
                message=message,
                result={"returncode": winner_res.returncode, "stdout": winner_res.stdout},
            )
