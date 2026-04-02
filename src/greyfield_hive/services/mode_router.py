"""ModeRouter —— 根据 exec_mode 路由到对应执行路径

Solo   → 直接派发给 assignee_synapse（或 code-expert）
Trial  → 调用 TrialRaceService 双路赛马
Chain  → 调用 ChainRunnerService 串行链
Swarm  → 调用 SwarmRunnerService 并发 Unit 池
"""

from __future__ import annotations

from loguru import logger

from greyfield_hive.db import SessionLocal
from greyfield_hive.models.task import ExecutionMode, TaskState
from greyfield_hive.services.episode_store import EpisodeStore
from greyfield_hive.services.task_fingerprint import TaskFingerprintService
from greyfield_hive.services.policy_registry import PolicyRegistry
from greyfield_hive.services.shadow_evaluator import ShadowEvaluator
from greyfield_hive.services.skill_registry import SkillRegistry
from greyfield_hive.services.event_bus import get_event_bus, TOPIC_TASK_DISPATCH
from greyfield_hive.services.execution_events import publish_stage_event, publish_task_event

# 历史成功率差距阈值：超过此值才允许覆盖 baseline
_HISTORY_OVERRIDE_THRESHOLD = 0.20
# 允许覆盖的最小 Episode 样本数
_HISTORY_MIN_SAMPLES = 5


class ModeRouter:
    """执行模式路由器 —— 根据 task.exec_mode 选择执行路径"""

    def __init__(self, db) -> None:
        self._db = db
        self._bus = get_event_bus()

    async def route(self, task_id: str, trace_id: str = "") -> None:
        """读取 task.exec_mode，路由到对应执行路径"""
        from greyfield_hive.services.task_service import TaskService
        svc = TaskService(self._db)
        task = await svc.get_by_id(task_id)

        mode = task.exec_mode or ExecutionMode.Solo
        message = task.description or task.title
        meta = task.meta or {}
        success_state = self._success_state(meta)
        logger.info(f"[ModeRouter] {task_id} exec_mode={mode.value if hasattr(mode, 'value') else mode}")

        # Phase 3: Skill 优先匹配 — 有成熟器官就用器官
        _fp = TaskFingerprintService().extract(
            message or "", domain=getattr(task, "domain", "general") or "general"
        )
        _matched_skill = None
        try:
            async with SessionLocal() as _sk_db:
                _matched_skill = await SkillRegistry(_sk_db).match_skill(_fp)
            if _matched_skill:
                logger.info(
                    f"[ModeRouter] Skill 匹配: {_matched_skill.slug} "
                    f"rate={_matched_skill.success_rate:.0%} uses={_matched_skill.total_uses}"
                )
                # 用器官的 preferred_mode 覆盖
                try:
                    mode = ExecutionMode(_matched_skill.preferred_mode)
                except ValueError:
                    pass
        except Exception as _e:
            logger.debug(f"[ModeRouter] Skill 匹配失败: {_e}")

        # Phase 2: 历史权重 + active policy 介入决策（_fp 已在 Phase 3 Skill 匹配时提取）
        _final_mode = mode  # 初始为 baseline
        _shadow_policies = []

        try:
            async with SessionLocal() as _ep_db:
                _ep_store = EpisodeStore(_ep_db)
                _policy_reg = PolicyRegistry(_ep_db)

                # 1. 查历史 Episode 各模式成功率
                _history = await _ep_store.get_domain_mode_stats(_fp.domain, days=30)

                # 2. 查 active policy，看有无模式建议
                _active_policies = await _policy_reg.get_active(
                    domain=_fp.domain, category="mode_selection"
                )
                # 3. 查 shadow policy（旁路预测用）
                _shadow_policies = await _policy_reg.get_shadow(
                    domain=_fp.domain, category="mode_selection"
                )

            # 4. 决策：历史成功率差 > 20% 且样本 ≥ 5 时覆盖 baseline
            _baseline_rate = _history.get(
                _final_mode.value if hasattr(_final_mode, "value") else str(_final_mode), {}
            ).get("success_rate", 0.0)

            for _hist_mode, _stats in _history.items():
                _rate = _stats.get("success_rate", 0.0)
                _samples = _stats.get("sample_count", 0)
                if (
                    _rate - _baseline_rate > _HISTORY_OVERRIDE_THRESHOLD
                    and _samples >= _HISTORY_MIN_SAMPLES
                ):
                    try:
                        _new_mode = ExecutionMode(_hist_mode)
                        logger.info(
                            f"[ModeRouter] 历史覆盖: {_final_mode} → {_new_mode} "
                            f"（成功率差={_rate-_baseline_rate:.0%}, 样本={_samples}）"
                        )
                        _final_mode = _new_mode
                        _baseline_rate = _rate
                    except ValueError:
                        pass  # 未知模式，跳过

            if _final_mode != mode:
                # 更新 task.exec_mode
                from greyfield_hive.services.task_service import TaskService as _TS
                async with SessionLocal() as _upd_db:
                    await _TS(_upd_db).update_exec_mode(task_id, _final_mode.value)
                    await _upd_db.commit()
                mode = _final_mode

            logger.debug(
                f"[ModeRouter] domain={_fp.domain} history={_history} "
                f"active_policies={len(_active_policies)} final_mode={mode}"
            )

        except Exception as _e:
            logger.debug(f"[ModeRouter] Phase2 历史决策失败（fallback baseline）: {_e}")
        if task.state == TaskState.Spawning:
            task = await svc.transition(task_id, TaskState.Executing, agent="mode-router", reason="进入执行态")
            trace_id = task.trace_id
        await publish_stage_event(
            self._bus,
            trace_id=trace_id,
            producer="mode-router",
            event_type="task.execution.started",
            task_id=task_id,
            stage="execution",
            payload={"mode": mode.value if hasattr(mode, "value") else str(mode)},
        )

        if mode == ExecutionMode.Trial:
            await self._save_route_meta(
                task,
                mode="trial",
                target="trial",
                reason="该任务进入对比评审模式，会并行比较多个候选执行者的结果。",
                split_plan=[
                    {"type": "candidate", "synapse": candidate}
                    for candidate in meta.get("trial_candidates", ["code-expert", "research-analyst"])
                ],
            )
            success = await self._route_trial(task_id, message, meta, trace_id)
        elif mode == ExecutionMode.Chain:
            await self._save_route_meta(
                task,
                mode="chain",
                target="chain",
                reason="该任务进入串行协作模式，前一阶段输出会成为下一阶段输入。",
                split_plan=[
                    {"type": "stage", "order": index + 1, "synapse": synapse}
                    for index, synapse in enumerate(meta.get("chain_stages", ["code-expert"]))
                ],
            )
            success = await self._route_chain(task_id, message, meta, trace_id)
        elif mode == ExecutionMode.Swarm:
            await self._save_route_meta(
                task,
                mode="swarm",
                target="swarm",
                reason="该任务进入并行协作模式，会拆成多个相对独立的执行单元同时推进。",
                split_plan=[
                    {
                        "type": "unit",
                        "order": index + 1,
                        "synapse": unit.get("synapse", "code-expert"),
                        "message": unit.get("message", message),
                    }
                    for index, unit in enumerate(meta.get("swarm_units") or [{"synapse": "code-expert", "message": message}])
                    if isinstance(unit, dict)
                ],
            )
            success = await self._route_swarm(task_id, message, meta, trace_id)
        else:
            await self._route_solo(task, trace_id, success_state)
            return

        task = await svc.transition(
            task_id,
            success_state if success else TaskState.Dormant,
            agent="mode-router",
            reason="执行完成" if success else "执行失败",
        )
        await publish_stage_event(
            self._bus,
            trace_id=task.trace_id,
            producer="mode-router",
            event_type="task.execution.completed" if success else "task.execution.failed",
            task_id=task_id,
            stage="execution",
            payload={"mode": mode.value if hasattr(mode, "value") else str(mode), "success": success},
        )

        # Phase 2: shadow policy 旁路预测记录
        if _shadow_policies:
            _actual_mode = mode.value if hasattr(mode, "value") else str(mode)
            try:
                async with SessionLocal() as _sh_db:
                    _sh_eval = ShadowEvaluator(_sh_db)
                    for _sp in _shadow_policies:
                        _sp_mode = (_sp.rule_logic or {}).get("prefer_mode", "")
                        if _sp_mode:
                            await _sh_eval.record_prediction(
                                _sp.id, task_id,
                                predicted_mode=_sp_mode,
                                actual_mode=_actual_mode,
                                actual_outcome="success" if success else "failure",
                            )
                    # 检查是否有 shadow 可以激活
                    await _sh_eval.evaluate_all_shadows(domain=_fp.domain)
                    await _sh_db.commit()
            except Exception as _e:
                logger.debug(f"[ModeRouter] shadow 记录失败: {_e}")

    async def _route_solo(self, task, trace_id: str, success_state: TaskState) -> None:
        """Solo: 派发给 assignee_synapse 或默认 code-expert，执行后推进到 Executing"""
        synapse = task.assignee_synapse or "code-expert"
        reason = (
            f"任务按单线执行推进，明确指定由 {synapse} 处理。"
            if task.assignee_synapse
            else "任务按单线执行推进，未显式指定执行者时默认交给代码专家。"
        )
        await self._save_route_meta(
            task,
            mode="solo",
            target=synapse,
            reason=reason,
            split_plan=[],
            selected_synapse=synapse,
        )
        await publish_task_event(
            self._bus,
            topic=TOPIC_TASK_DISPATCH,
            trace_id=trace_id,
            event_type="task.dispatch.request",
            producer="mode-router",
            task_id=task.id,
            payload={
                "synapse": synapse,
                "message": task.description or task.title,
                "domain": "general",
                "next_state": success_state.value,
            },
        )
        logger.info(f"[ModeRouter] Solo → {synapse} → next={success_state.value}")

    @staticmethod
    def _success_state(meta: dict) -> TaskState:
        if meta.get("skip_consolidation"):
            return TaskState.Complete
        return TaskState.Consolidating

    async def _route_trial(self, task_id: str, message: str,
                           meta: dict, trace_id: str) -> bool:
        """Trial: 双路赛马 —— N-5: 优先按净值选人"""
        from greyfield_hive.services.trial_race import TrialRaceService
        from greyfield_hive.services.fitness_service import FitnessService

        # 按域净值选最高的两个 synapse
        domain = meta.get("domain", "general")
        fallback_a = "code-expert"
        fallback_b = "research-analyst"
        try:
            leaderboard = await FitnessService(self._db).get_leaderboard(limit=10)
            # 过滤：优先同域，再看 general
            domain_scores = [s for s in leaderboard
                             if domain in s.synapse_id or "general" in s.synapse_id]
            if len(domain_scores) >= 2:
                fallback_a = domain_scores[0].synapse_id
                fallback_b = domain_scores[1].synapse_id
            elif len(domain_scores) == 1:
                fallback_a = domain_scores[0].synapse_id
        except Exception:
            pass

        candidates = meta.get("trial_candidates", [fallback_a, fallback_b])
        synapse_a = candidates[0] if candidates else fallback_a
        synapse_b = candidates[1] if len(candidates) > 1 else fallback_b
        logger.info(f"[ModeRouter] Trial → {synapse_a}(净值优先) vs {synapse_b}")
        svc = TrialRaceService(self._db)
        result = await svc.run(task_id=task_id, synapse_a=synapse_a,
                               synapse_b=synapse_b, message=message, trace_id=trace_id)
        return result.winner is not None

    async def _route_chain(self, task_id: str, message: str,
                           meta: dict, trace_id: str) -> bool:
        """Chain: 串行链"""
        from greyfield_hive.services.chain_runner import ChainRunnerService
        stages = meta.get("chain_stages", ["code-expert"])
        logger.info(f"[ModeRouter] Chain → {stages}")
        svc = ChainRunnerService(self._db)
        result = await svc.run(task_id=task_id, synapses=stages,
                               message=message, trace_id=trace_id)
        return result.success

    async def _route_swarm(self, task_id: str, message: str,
                           meta: dict, trace_id: str) -> bool:
        """Swarm: 并发 Unit 池"""
        from greyfield_hive.services.swarm_runner import SwarmRunnerService, SwarmUnit
        units_meta = meta.get("swarm_units") or [{"synapse": "code-expert", "message": message}]
        units = [
            SwarmUnit(synapse=u.get("synapse", "code-expert"),
                      message=u.get("message", message),
                      domain=u.get("domain", "general"))
            for u in units_meta if isinstance(u, dict)
        ]
        logger.info(f"[ModeRouter] Swarm → {len(units)} units")
        svc = SwarmRunnerService(self._db)
        result = await svc.run(task_id=task_id, units=units, trace_id=trace_id)
        return result.all_success

    async def _save_route_meta(
        self,
        task,
        *,
        mode: str,
        target: str,
        reason: str,
        split_plan: list[dict],
        selected_synapse: str | None = None,
    ) -> None:
        meta = dict(task.meta or {})
        meta["route_mode"] = mode
        meta["route_target"] = target
        meta["route_reason"] = reason
        meta["split_plan"] = split_plan
        if selected_synapse:
            meta["selected_synapse"] = selected_synapse
        task.meta = meta
        await self._db.commit()
