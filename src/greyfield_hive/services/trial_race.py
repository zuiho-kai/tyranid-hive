"""Trial Race 赛马机制 —— 两个 Synapse 并行竞争同一任务，胜者经验入库

流程：
  1. 接收 task_id + 两个 synapse + message + domain
  2. 异步并行调用两个 synapse（通过 DispatchWorker._invoke_agent）
  3. 多维评分：质量40% / 速度20% / 健壮性15% / 复用10% / Token成本-10% / 协调-5%
  4. 双方结果均写入 progress_log；胜者额外写入 Lessons Bank
  5. 返回 TrialResult（含双方详情 + 胜者 + 评分明细）
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger

from greyfield_hive.db import SessionLocal
from greyfield_hive.services.chain_runner import _record_fitness
from greyfield_hive.services.episode_store import EpisodeStore
from greyfield_hive.services.task_fingerprint import TaskFingerprintService
from greyfield_hive.services.execution_events import publish_stage_event
from greyfield_hive.services.event_bus import get_event_bus
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
class TrialScore:
    """多维评分明细（满分 100）"""
    quality:      float = 0.0   # 质量：输出结构化程度 × 40%
    speed:        float = 0.0   # 速度：响应时间得分 × 20%
    robustness:   float = 0.0   # 健壮性：无错误/警告 × 15%
    reuse:        float = 0.0   # 复用：引用已有 Playbook/Lesson × 10%
    token_cost:   float = 0.0   # Token 成本惩罚（输出越长扣越多）× -10%
    coordination: float = 0.0   # 协调开销惩罚（stderr 越多扣越多）× -5%

    @property
    def total(self) -> float:
        return (
            self.quality * 0.40
            + self.speed * 0.20
            + self.robustness * 0.15
            + self.reuse * 0.10
            - self.token_cost * 0.10
            - self.coordination * 0.05
        )


@dataclass
class TrialResult:
    task_id:    str
    winner:     Optional[str]             # synapse name or None（均失败）
    results:    dict[str, SynapseResult]  # synapse → result
    scores:     dict[str, TrialScore] = field(default_factory=dict)
    tie:        bool = False


# ── 多维评分 ──────────────────────────────────────────────

# 硬门槛：returncode != 0 直接判负，不进入评分
_FAILURE_KEYWORDS = {"error", "traceback", "exception", "fatal", "failed"}
_STRUCTURE_MARKERS = {"```", "##", "- ", "* ", "1.", "2.", "3."}


def _score(res: SynapseResult, max_elapsed: float) -> TrialScore:
    """对单个 SynapseResult 计算多维评分（各维度 0-100）"""
    s = TrialScore()

    if not res.success:
        return s  # 硬门槛：失败直接 0 分

    stdout = res.stdout or ""
    stderr = res.stderr or ""

    # 质量：结构化标记数量 + 非空行密度（满分 100）
    marker_hits = sum(1 for m in _STRUCTURE_MARKERS if m in stdout)
    lines = [l for l in stdout.splitlines() if l.strip()]
    density = min(len(lines) / 20, 1.0)  # 20 行以上满分
    s.quality = min(marker_hits * 12 + density * 40, 100.0)

    # 速度：相对最慢者的倒数（最快得 100，最慢得 0）
    if max_elapsed > 0:
        s.speed = max(0.0, (1.0 - res.elapsed_sec / max_elapsed) * 100)
    else:
        s.speed = 100.0

    # 健壮性：stderr 越少越好，无 failure 关键词得满分
    has_failure = any(kw in stdout.lower() for kw in _FAILURE_KEYWORDS)
    stderr_penalty = min(len(stderr) / 500, 1.0) * 50
    s.robustness = 0.0 if has_failure else max(0.0, 100.0 - stderr_penalty)

    # 复用：输出中引用 Playbook/Lesson 关键词
    reuse_hits = len(re.findall(r"playbook|lesson|经验|手册", stdout, re.IGNORECASE))
    s.reuse = min(reuse_hits * 25, 100.0)

    # Token 成本惩罚：输出超过 2000 字开始扣分
    excess = max(0, len(stdout) - 2000)
    s.token_cost = min(excess / 100, 100.0)

    # 协调开销惩罚：stderr 长度
    s.coordination = min(len(stderr) / 50, 100.0)

    return s


def _pick_winner(
    a: SynapseResult,
    b: SynapseResult,
    score_a: Optional[TrialScore] = None,
    score_b: Optional[TrialScore] = None,
) -> Optional[str]:
    """硬门槛 + 多维评分选胜者；均失败返回 None"""
    # 硬门槛
    if a.success and not b.success:
        return a.synapse
    if b.success and not a.success:
        return b.synapse
    if not a.success and not b.success:
        return None

    # 双方都成功 → 多维评分
    sa = score_a.total if score_a else float(len(a.stdout))
    sb = score_b.total if score_b else float(len(b.stdout))
    if abs(sa - sb) < 1.0:
        return a.synapse  # 平局取 A
    return a.synapse if sa >= sb else b.synapse


# ── Trial Race ────────────────────────────────────────────

class TrialRaceService:
    """赛马服务 —— 不持有长生命周期 worker，每次创建临时 DispatchWorker 进行调用"""

    def __init__(self, db=None) -> None:
        self._db = db
        self._worker = DispatchWorker()
        self._bus = get_event_bus()

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
        await publish_stage_event(
            self._bus,
            trace_id=trace_id,
            producer="trial-race",
            event_type="task.stage.started",
            task_id=task_id,
            stage="trial",
            payload={"mode": "trial", "synapses": [synapse_a, synapse_b]},
        )

        # 构建富提示词（共用同一个 message 和 domain）
        enriched_a, enriched_b = await asyncio.gather(
            self._worker._build_enriched_message(synapse_a, message, task_id, domain),
            self._worker._build_enriched_message(synapse_b, message, task_id, domain),
        )

        # 并行调用两个 synapse（独立计时）
        import time

        async def _timed(synapse, enriched):
            t = time.monotonic()
            raw = await self._worker._invoke_agent(synapse, enriched, task_id, trace_id)
            return raw, time.monotonic() - t

        # Phase 1: begin Episode
        _fp = TaskFingerprintService().extract(message, domain=domain)
        _episode_id: str | None = None
        try:
            async with SessionLocal() as _ep_db:
                _ep = await EpisodeStore(_ep_db).begin_episode(
                    task_id=task_id, fingerprint=_fp,
                    chosen_mode="trial",
                    justification=f"{synapse_a} vs {synapse_b}",
                )
                _episode_id = _ep.id
                await _ep_db.commit()
        except Exception as _e:
            logger.warning(f"[TrialRace] Episode begin 失败: {_e}")

        (raw_a, elapsed_a), (raw_b, elapsed_b) = await asyncio.gather(
            _timed(synapse_a, enriched_a),
            _timed(synapse_b, enriched_b),
        )

        result_a = SynapseResult(
            synapse=synapse_a,
            returncode=raw_a.get("returncode", -1),
            stdout=raw_a.get("stdout", ""),
            stderr=raw_a.get("stderr", ""),
            success=_infer_success(raw_a),
            elapsed_sec=elapsed_a,
        )
        result_b = SynapseResult(
            synapse=synapse_b,
            returncode=raw_b.get("returncode", -1),
            stdout=raw_b.get("stdout", ""),
            stderr=raw_b.get("stderr", ""),
            success=_infer_success(raw_b),
            elapsed_sec=elapsed_b,
        )

        # Phase 1: record steps for both synapses
        if _episode_id:
            try:
                async with SessionLocal() as _ep_db:
                    _ep_store = EpisodeStore(_ep_db)
                    for _r, _el in [(result_a, elapsed_a), (result_b, elapsed_b)]:
                        await _ep_store.record_step(
                            _episode_id, actor=_r.synapse, action_type="trial_arm",
                            token_cost=len(_r.stdout) // 4,
                            wall_time=round(_el, 3),
                            outcome="success" if _r.success else "failure",
                        )
                    await _ep_db.commit()
            except Exception as _e:
                logger.warning(f"[TrialRace] Episode step 失败: {_e}")

        # 多维评分
        max_elapsed = max(elapsed_a, elapsed_b, 0.001)
        score_a = _score(result_a, max_elapsed)
        score_b = _score(result_b, max_elapsed)

        winner_name = _pick_winner(result_a, result_b, score_a, score_b)
        tie = result_a.success == result_b.success and abs(score_a.total - score_b.total) < 1.0

        trial = TrialResult(
            task_id=task_id,
            winner=winner_name,
            results={synapse_a: result_a, synapse_b: result_b},
            scores={synapse_a: score_a, synapse_b: score_b},
            tie=tie,
        )

        logger.info(
            f"[TrialRace] 结果: {synapse_a}={'✅' if result_a.success else '❌'}"
            f"({score_a.total:.1f}分) "
            f"{synapse_b}={'✅' if result_b.success else '❌'}"
            f"({score_b.total:.1f}分) 胜者={winner_name or '无'}"
        )

        # Phase 1: finish Episode
        if _episode_id:
            try:
                async with SessionLocal() as _ep_db:
                    _overall = "success" if (result_a.success or result_b.success) else "failure"
                    await EpisodeStore(_ep_db).finish_episode(_episode_id, outcome=_overall)
                    await _ep_db.commit()
            except Exception as _e:
                logger.warning(f"[TrialRace] Episode finish 失败: {_e}")

        # 回写 progress_log + 写入经验
        await self._persist_all(trial, message, domain)

        # 发布 TrialClosed 事件（供 EvolutionMaster 订阅）
        try:
            from greyfield_hive.services.event_bus import TOPIC_TRIAL_CLOSED
            await self._bus.publish(
                topic=TOPIC_TRIAL_CLOSED,
                event_type="trial.closed",
                producer="trial-race",
                payload={
                    "task_id": task_id,
                    "domain": domain,
                    "winner": winner_name,
                    "tie": tie,
                    "scores": {
                        synapse_a: score_a.total,
                        synapse_b: score_b.total,
                    },
                },
            )
        except Exception as e:
            logger.warning(f"[TrialRace] TrialClosed 事件发布失败: {e}")

        await publish_stage_event(
            self._bus,
            trace_id=trace_id,
            producer="trial-race",
            event_type="task.stage.completed" if winner_name else "task.stage.failed",
            task_id=task_id,
            stage="trial",
            payload={
                "mode": "trial",
                "winner": winner_name,
                "tie": tie,
                "scores": {synapse_a: score_a.total, synapse_b: score_b.total},
            },
        )

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

        # 双方战功记录
        for synapse, res in trial.results.items():
            raw = {"returncode": res.returncode, "stdout": res.stdout}
            await _record_fitness(synapse, trial.task_id, domain, res.success, raw)
