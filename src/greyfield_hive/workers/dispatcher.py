"""派发器 Worker —— 消费 task.dispatch 事件，调用 OpenClaw CLI 执行小主脑

工作流：
  task.dispatch 事件 → 读取 synapse ID
                    → 注入基因上下文（Lessons + Playbooks）
                    → 通过 OpenClawAdapter 调用 agent（openclaw / claude / mock）
                    → 回写 task.progress_log
                    → 自动写入经验教训（Lessons Bank）
"""

from __future__ import annotations

import asyncio
import json
import os
import re

from loguru import logger

from greyfield_hive.db import SessionLocal
from greyfield_hive.services.event_bus import (
    get_event_bus,
    BusEvent,
    TOPIC_TASK_DISPATCH,
    TOPIC_TASK_STATUS,
    TOPIC_TASK_STAGE,
    TOPIC_AGENT_THOUGHTS,
    TOPIC_AGENT_HEARTBEAT,
)
from greyfield_hive.services.execution_events import publish_stage_event, publish_task_event
from greyfield_hive.adapters.openclaw import get_adapter, OpenClawAdapter
from greyfield_hive.models.task import TaskState
from greyfield_hive.services.task_service import TaskService, InvalidTransitionError
from greyfield_hive.services.lessons_bank import LessonsBank
from greyfield_hive.services.playbook_service import PlaybookService
from greyfield_hive.services.fitness_service import FitnessService
from greyfield_hive.services.gene_loader import get_gene_loader
from greyfield_hive.services.task_service import TaskService, InvalidTransitionError
from greyfield_hive.models.task import TaskState
from greyfield_hive.services.episode_store import EpisodeStore
from greyfield_hive.services.task_fingerprint import TaskFingerprintService


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

# synapse → 默认领域（用于基因库检索）
_SYNAPSE_DOMAIN: dict[str, str] = {
    "overmind":         "general",
    "evolution-master": "evolution",
    "code-expert":      "coding",
    "research-analyst": "research",
    "finance-scout":    "finance",
}


def _format_lessons_block(lessons: list) -> str:
    if not lessons:
        return "（暂无相关经验）"
    lines = []
    for l in lessons:
        outcome_tag = {"success": "✅", "failure": "❌", "partial": "⚠️"}.get(l.outcome, "？")
        lines.append(f"{outcome_tag} [{l.domain}] {l.content[:200]}")
    return "\n".join(lines)


def _format_playbooks_block(playbooks: list) -> str:
    if not playbooks:
        return "（暂无相关手册）"
    parts = []
    for p in playbooks:
        rate_pct = int((p.success_rate or 0) * 100)
        parts.append(
            f"《{p.title}》(v{p.version}, 成功率 {rate_pct}%)\n{p.content[:300]}"
        )
    return "\n\n".join(parts)


def _infer_success(result: dict) -> bool:
    """从 agent 输出粗略判断任务是否成功"""
    rc = result.get("returncode", -1)
    if rc != 0:
        return False
    stdout = (result.get("stdout") or "").lower()
    failure_keywords = ["error", "failed", "traceback", "exception", "fatal"]
    return not any(kw in stdout for kw in failure_keywords)


def _extract_json_payload(raw: str) -> dict | None:
    text = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def _normalize_overmind_state(data: dict, fallback: str) -> str:
    blockers = [str(item).strip() for item in data.get("blockers", []) if str(item).strip()]
    if blockers:
        return TaskState.WaitingInput.value

    raw_state = str(
        data.get("recommended_state", data.get("recommended_status", fallback or TaskState.Planning.value))
    ).strip()
    state_map = {
        "planning": TaskState.Planning.value,
        "reviewing": TaskState.Reviewing.value,
        "spawning": TaskState.Spawning.value,
        "executing": TaskState.Spawning.value,
        "waitinginput": TaskState.WaitingInput.value,
        "waiting_input": TaskState.WaitingInput.value,
        "dormant": TaskState.Dormant.value,
        "complete": TaskState.Complete.value,
    }
    return state_map.get(raw_state.lower(), fallback or TaskState.Planning.value)


def _extract_waiting_input_blockers(raw: str) -> list[str]:
    hints = (
        "缺少",
        "缺失",
        "请补充",
        "需要补充",
        "请提供",
        "请确认",
        "无法进入有效拆解",
        "任务定义缺失",
        "关键信息",
        "未指定",
    )
    blockers: list[str] = []
    for line in raw.splitlines():
        clean = re.sub(r"^[\-\*\d\.\s`#>]+", "", line).strip()
        if not clean:
            continue
        if any(hint in clean for hint in hints):
            blockers.append(clean[:160])

    unique_blockers: list[str] = []
    for blocker in blockers:
        if blocker not in unique_blockers:
            unique_blockers.append(blocker)

    if unique_blockers:
        return unique_blockers[:5]
    if any(hint in raw for hint in hints):
        return ["需要用户补充关键信息"]
    return []


def _task_combined_text(task) -> str:
    title = str(task.title or "")
    description = str(task.description or "")
    return f"{title}\n{description}".lower()


def _is_optional_scope_blocker(text: str) -> bool:
    lowered = str(text).lower()
    return any(
        hint in lowered
        for hint in (
            "统计范围",
            "时间口径",
            "输出格式",
            "盘中实时",
            "收盘后",
            "自然语言摘要",
            "结构化数据",
        )
    )


def _apply_default_market_overview_plan(task, data: dict) -> dict:
    combined = _task_combined_text(task)
    market_hints = ("港股", "美股", "a股", "比特币", "btc", "股票", "市场", "盘面", "行情", "指数")
    trigger_hints = ("今天", "今日", "情况", "概览", "走势", "总结", "怎么样", "爬", "抓", "查")

    if not any(hint in combined for hint in market_hints):
        return data
    if not any(hint in combined for hint in trigger_hints):
        return data

    blockers = [str(item).strip() for item in data.get("blockers", []) if str(item).strip()]
    if blockers and not all(_is_optional_scope_blocker(item) for item in blockers):
        return data

    domain = str(data.get("domain", "") or "finance/market-data")
    if "finance" not in domain and "market" not in domain:
        domain = "finance/market-data"

    market_name = "市场"
    if "港股" in combined:
        market_name = "港股"
    elif "美股" in combined:
        market_name = "美股"
    elif "比特币" in combined or "btc" in combined:
        market_name = "比特币"

    use_swarm = any(
        hint in combined
        for hint in ("并行", "同时", "多源", "多个来源", "分维度", "分别抓", "全面", "全量")
    )

    next_data = dict(data)
    next_data["summary"] = f"按默认口径抓取今日{market_name}概览，并整理成简明市场摘要。"
    next_data["domain"] = domain
    next_data["blockers"] = []
    next_data["recommended_state"] = TaskState.Spawning.value
    next_data["todos"] = [
        f"抓取今日{market_name}主要指数、涨跌幅与成交额",
        f"补充今日{market_name}资金流、板块表现和活跃个股",
        "整理关键数据并产出面向用户的简明市场摘要",
    ]

    if use_swarm:
        next_data["exec_mode"] = "swarm"
        next_data["mode_justification"] = "用户意图更接近多路独立采集，适合先并行抓不同维度，再由主脑收敛。"
        next_data["swarm_units"] = [
            {"synapse": "finance-scout", "message": f"抓取今日{market_name}主要指数、涨跌幅与成交额", "domain": "finance"},
            {"synapse": "finance-scout", "message": f"抓取今日{market_name}资金流与板块表现", "domain": "finance"},
            {"synapse": "research-analyst", "message": f"整理今日{market_name}活跃个股与市场焦点", "domain": "research"},
        ]
        next_data.pop("trial_candidates", None)
        next_data.pop("chain_stages", None)
    else:
        next_data["exec_mode"] = "solo"
        next_data["mode_justification"] = "这是日常市场概览任务，主脑可按顺序工具链直接完成，默认保持 Solo。"
        next_data.pop("trial_candidates", None)
        next_data.pop("chain_stages", None)
        next_data.pop("swarm_units", None)
    return next_data


class DispatchWorker:
    """派发器 —— 将任务分配给对应的小主脑（OpenClaw agent）"""

    def __init__(self, max_concurrent: int = 3) -> None:
        self.bus = get_event_bus()
        self._running = False
        self._sem = asyncio.Semaphore(max_concurrent)
        self._q: asyncio.Queue | None = None
        # 原生适配器（自动探测 openclaw/claude CLI，降级到 mock）
        self._adapter: OpenClawAdapter = get_adapter()

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
            payload    = event.payload
            task_id    = payload.get("task_id", "")
            synapse    = payload.get("synapse", "overmind")
            message    = payload.get("message", "")
            domain     = payload.get("domain", _SYNAPSE_DOMAIN.get(synapse, "general"))
            next_state = payload.get("next_state", "")
            trace_id   = event.trace_id

            await publish_task_event(
                self.bus,
                topic=TOPIC_AGENT_HEARTBEAT,
                trace_id=trace_id,
                event_type="agent.dispatch.start",
                producer="dispatcher",
                task_id=task_id,
                payload={"synapse": synapse},
            )

            # 注入基因上下文
            enriched_message = await self._build_enriched_message(
                synapse=synapse,
                message=message,
                task_id=task_id,
                domain=domain,
            )

            logger.info(f"[Dispatcher] 派发 {task_id} → {synapse}: {message[:60]}")
            stage_kind = "analysis" if synapse == "overmind" else "execution"
            await publish_stage_event(
                self.bus,
                trace_id=trace_id,
                producer=f"synapse.{synapse}",
                event_type=f"task.{stage_kind}.started" if synapse == "overmind" else "task.stage.started",
                task_id=task_id,
                stage=synapse,
                payload={"synapse": synapse, "message": message[:200]},
            )

            # ── Phase 1: Episode 记录（异步，不阻塞主执行路径）────────────────
            _fp_svc = TaskFingerprintService()
            _fingerprint = _fp_svc.extract(message, domain=domain)
            _episode_id: str | None = None
            try:
                async with SessionLocal() as _ep_db:
                    _ep_store = EpisodeStore(_ep_db)
                    _ep = await _ep_store.begin_episode(
                        task_id=task_id or "unknown",
                        fingerprint=_fingerprint,
                        chosen_mode=domain,
                        justification=f"synapse={synapse}",
                    )
                    _episode_id = _ep.id
                    await _ep_db.commit()
            except Exception as _ep_err:
                logger.warning(f"[Dispatcher] Episode begin 失败（不影响执行）: {_ep_err}")

            import time as _time
            _t0 = _time.monotonic()
            result = await self._invoke_agent(synapse, enriched_message, task_id, trace_id)
            _wall = round(_time.monotonic() - _t0, 3)

            # 写入 EpisodeStep
            if _episode_id:
                _success = _infer_success(result)
                _stdout_len = len(result.get("stdout") or "")
                try:
                    async with SessionLocal() as _ep_db:
                        _ep_store = EpisodeStore(_ep_db)
                        await _ep_store.record_step(
                            _episode_id,
                            actor=synapse,
                            action_type=stage_kind,
                            token_cost=_stdout_len // 4,   # 粗估：4 字符 ≈ 1 token
                            wall_time=_wall,
                            outcome="success" if _success else "failure",
                            error_class=None if _success else "strategy",
                        )
                        await _ep_store.finish_episode(
                            _episode_id,
                            outcome="success" if _success else "failure",
                        )
                        await _ep_db.commit()
                except Exception as _ep_err:
                    logger.warning(f"[Dispatcher] Episode step 写入失败（不影响执行）: {_ep_err}")
            # ── Episode 记录结束 ─────────────────────────────────────────────

            await publish_task_event(
                self.bus,
                topic=TOPIC_AGENT_THOUGHTS,
                trace_id=trace_id,
                event_type="agent.output",
                producer=f"synapse.{synapse}",
                task_id=task_id,
                payload={
                    "synapse": synapse,
                    "output": result.get("stdout", ""),
                    "return_code": result.get("returncode", -1),
                    "error": result.get("stderr", ""),
                },
            )

            if result.get("returncode", -1) != 0:
                logger.warning(f"[Dispatcher] {synapse} 返回非零: {result.get('returncode')}")

            # 回写 progress_log
            if task_id:
                await self._persist_progress(task_id, synapse, result)

            # 主脑输出：提取分析结果并覆盖下一状态
            if synapse == "overmind" and task_id:
                next_state = await self._save_overmind_analysis(task_id, result, next_state)

            # 自动写入经验教训
            await self._write_outcome_lesson(
                task_id=task_id,
                synapse=synapse,
                domain=domain,
                message=message,
                result=result,
            )

            # 战功记录（适存驱动）
            await self._record_kill_mark(
                task_id=task_id,
                synapse=synapse,
                domain=domain,
                result=result,
            )

            # Playbook 使用统计（闭合反馈回路）
            success = _infer_success(result)
            tags = [w for w in message.split() if 3 <= len(w) <= 10][:8]
            await self._update_playbook_stats(domain=domain, tags=tags, success=success)

            # 推进状态机：失败时进入 Dormant，成功时进入目标状态
            target_state = next_state
            if task_id and result.get("returncode", -1) != 0:
                target_state = TaskState.Dormant.value

            if target_state and task_id:
                try:
                    new_ts = TaskState(target_state)
                    async with SessionLocal() as db:
                        svc = TaskService(db)
                        await svc.transition(task_id, new_ts, agent="dispatcher")
                    logger.info(f"[Dispatcher] 状态推进 {task_id} → {target_state}")
                except InvalidTransitionError as e:
                    logger.warning(f"[Dispatcher] 非法状态跳转，跳过: {e}")
                except Exception as e:
                    logger.error(f"[Dispatcher] 状态推进失败 {task_id}: {e}")

            await publish_stage_event(
                self.bus,
                trace_id=trace_id,
                producer=f"synapse.{synapse}",
                event_type=(
                    "task.analysis.completed"
                    if synapse == "overmind" and result.get("returncode", -1) == 0
                    else (
                        "task.analysis.failed"
                        if synapse == "overmind"
                        else ("task.stage.completed" if result.get("returncode", -1) == 0 else "task.stage.failed")
                    )
                ),
                task_id=task_id,
                stage=synapse,
                payload={
                    "synapse": synapse,
                    "returncode": result.get("returncode", -1),
                    "success": _infer_success(result),
                },
            )

    # ── 基因上下文注入 ────────────────────────────────────

    async def _build_enriched_message(
        self,
        synapse: str,
        message: str,
        task_id: str,
        domain: str,
    ) -> str:
        """
        构建携带基因库上下文的富提示词。

        格式：
          [HIVE CONTEXT]
          ...基因上下文...

          ## 你的任务
          {原始 message}
        """
        try:
            async with SessionLocal() as db:
                bank = LessonsBank(db)
                # 从 message 中提取简单 tags（按空白分词，长度 3-10 的词）
                tags = [w for w in message.split() if 3 <= len(w) <= 10][:8]
                lessons  = await bank.search(task_domain=domain, task_tags=tags, top_k=5)
                pb_svc   = PlaybookService(db)
                playbooks = await pb_svc.search(domain=domain, task_tags=tags, top_k=3)

            lessons_text  = _format_lessons_block(lessons)
            playbooks_text = _format_playbooks_block(playbooks)

            # 从 L2 基因文件加载 Synapse 角色系统提示词
            gene_loader = get_gene_loader()
            system_prompt = gene_loader.get_system_prompt(synapse).strip()
            if synapse == "overmind":
                system_prompt = (
                    f"{system_prompt}\n\n"
                    "硬性要求：你当前处于任务分析阶段，不是执行阶段。\n"
                    "不要直接回答用户问题，不要直接产出最终成品，不要进入实现细节。\n"
                    "你的唯一输出必须是一个 JSON 对象，且不能带 Markdown、代码块或额外解释。\n"
                    "JSON 至少包含这些字段：summary, domain, todos, risks, blockers, recommended_state, exec_mode。\n"
                    "如果信息缺失，blockers 填缺失项，recommended_state 必须为 WaitingInput。\n"
                    "如果任务已经足够明确且适合直接执行，recommended_state 设为 Spawning，exec_mode 默认用 solo。"
                )

            context_block = (
                f"[SYSTEM]\n{system_prompt}\n\n"
                f"[TASK]\n{message}\n\n"
                f"---\n"
                f"[HIVE CONTEXT]\n"
                f"Task-ID : {task_id or '—'}\n"
                f"Synapse : {synapse}\n"
                f"Domain  : {domain}\n"
            )
            # Keep stable section headers/placeholders so tests and operators
            # can rely on a predictable enriched prompt shape.
            if lessons_text:
                context_block += f"\n历史经验:\n{lessons_text}"
            if playbooks_text:
                context_block += f"\n作战手册:\n{playbooks_text}"
            return context_block

        except Exception as e:
            logger.warning(f"[Dispatcher] 基因上下文注入失败，降级到原始消息: {e}")
            return message

    # ── 经验教训写入 ──────────────────────────────────────

    async def _write_outcome_lesson(
        self,
        task_id: str,
        synapse: str,
        domain: str,
        message: str,
        result: dict,
    ) -> None:
        """将 agent 执行结果作为经验教训写入 Lessons Bank"""
        if not message:
            return
        try:
            success = _infer_success(result)
            outcome = "success" if success else "failure"
            stdout  = (result.get("stdout") or "").strip()
            # 内容：任务摘要 + 输出摘要
            content = f"[{synapse}] {message[:120]}"
            if stdout:
                content += f"\n输出摘要: {stdout[:200]}"

            async with SessionLocal() as db:
                bank = LessonsBank(db)
                lesson = await bank.add(
                    domain=domain,
                    content=content,
                    outcome=outcome,
                    task_id=task_id or None,
                    tags=[synapse],
                )
                logger.debug(f"[Dispatcher] 经验入库 {lesson.id[:8]} outcome={outcome}")
        except Exception as e:
            logger.warning(f"[Dispatcher] 经验写入失败: {e}")

    async def _record_kill_mark(
        self,
        task_id: str,
        synapse: str,
        domain: str,
        result: dict,
    ) -> None:
        """将执行结果写入战功记录（适存驱动）"""
        try:
            success = _infer_success(result)
            rc = result.get("returncode", -1)
            # score: 成功=1.0，部分成功=0.5（rc=0但有警告），失败=0.3
            if success:
                score = 1.0
            elif rc == 0:
                score = 0.5
            else:
                score = 0.3
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
                logger.debug(f"[Dispatcher] 战功入库 synapse={synapse} success={success}")
        except Exception as e:
            logger.warning(f"[Dispatcher] 战功记录失败: {e}")

    async def _update_playbook_stats(
        self,
        domain: str,
        tags: list[str],
        success: bool,
    ) -> None:
        """更新命中 Playbook 的使用次数和成功率（闭合反馈回路）"""
        try:
            async with SessionLocal() as db:
                pb_svc = PlaybookService(db)
                playbooks = await pb_svc.search(domain=domain, task_tags=tags, top_k=3)
                for pb in playbooks:
                    await pb_svc.record_usage(pb.id, success=success)
                if playbooks:
                    await db.commit()
                    logger.debug(
                        f"[Dispatcher] Playbook 使用统计已更新 "
                        f"domain={domain} count={len(playbooks)}"
                    )
        except Exception as e:
            logger.warning(f"[Dispatcher] Playbook 统计更新失败: {e}")

    async def _persist_progress(self, task_id: str, synapse: str, result: dict) -> None:
        """将 agent 执行结果写回任务进度日志"""
        from greyfield_hive.services.task_service import TaskService, TaskNotFoundError

        rc     = result.get("returncode", -1)
        stdout = (result.get("stdout") or "").strip()
        stderr = (result.get("stderr")  or "").strip()

        if rc == 0:
            content = stdout[:2000] if stdout else f"[{synapse}] 执行完成"
        else:
            content = f"[执行失败 rc={rc}]"
            if stdout:
                content += f"\n{stdout[:1000]}"
            if stderr:
                content += f"\n[stderr] {stderr[:300]}"

        try:
            async with SessionLocal() as db:
                svc = TaskService(db)
                await svc.add_progress(task_id, f"synapse.{synapse}", content)
                logger.debug(f"[Dispatcher] 进度已回写 {task_id} ← {synapse} ({len(content)}字)")
        except TaskNotFoundError:
            logger.debug(f"[Dispatcher] 任务不存在，跳过进度回写: {task_id}")
        except Exception as e:
            logger.warning(f"[Dispatcher] 进度回写失败 {task_id}: {e}")

    # ── 主脑分析结果提取 ───────────────────────────────────

    async def _save_overmind_analysis(
        self,
        task_id: str,
        result: dict,
        fallback_next_state: str,
    ) -> str:
        """从主脑 stdout 提取分析结果，并返回有效的下一状态。"""
        stdout = result.get("stdout", "")
        try:
            data = _extract_json_payload(stdout)
            if not data:
                blockers = _extract_waiting_input_blockers(stdout)
                if not blockers:
                    return fallback_next_state
                data = {
                    "summary": stdout[:300],
                    "domain": "general",
                    "risks": [],
                    "blockers": blockers,
                    "recommended_state": TaskState.WaitingInput.value,
                    "exec_mode": "solo",
                }

            async with SessionLocal() as db:
                from greyfield_hive.services.task_service import TaskService
                svc = TaskService(db)
                task = await svc.get_by_id(task_id)
                data = _apply_default_market_overview_plan(task, data)
                blockers = [str(item).strip() for item in data.get("blockers", []) if str(item).strip()]
                risks = [str(item).strip() for item in data.get("risks", []) if str(item).strip()]
                effective_next_state = _normalize_overmind_state(data, fallback_next_state)
                meta = dict(task.meta or {})

                mode_selected = False
                exec_mode = task.exec_mode.value if task.exec_mode else "solo"
                if not (task.exec_mode and meta.get("mode_source") == "user"):
                    exec_mode = str(data.get("exec_mode", "solo")).lower()
                    if exec_mode not in {"solo", "trial", "chain", "swarm"}:
                        exec_mode = "solo"
                    task = await svc.update_exec_mode(task_id, exec_mode)
                    meta = dict(task.meta or {})
                    mode_selected = True

                meta["analysis_summary"] = str(data.get("summary", ""))
                meta["analysis_domain"] = str(data.get("domain", "general"))
                meta["analysis_risks"] = risks
                meta["analysis_blockers"] = blockers
                meta["awaiting_user_input"] = bool(blockers)
                meta["recommended_state"] = effective_next_state
                meta["analysis_exec_mode"] = exec_mode
                meta["mode_justification"] = str(data.get("mode_justification", ""))
                meta["route_target"] = "waiting-input" if blockers else exec_mode
                if blockers:
                    meta["route_reason"] = "缺少关键信息，先等待用户补充，再继续规划或执行。"
                elif str(data.get("mode_justification", "")).strip():
                    meta["route_reason"] = str(data.get("mode_justification", "")).strip()
                elif exec_mode == "solo":
                    meta["route_reason"] = "主脑判断任务已足够明确，先按单线执行推进。"
                elif exec_mode == "trial":
                    meta["route_reason"] = "主脑判断需要对比多个方案或多个代理结果，再决定后续方向。"
                elif exec_mode == "chain":
                    meta["route_reason"] = "主脑判断任务需要前后串行协作，上一阶段输出会喂给下一阶段。"
                else:
                    meta["route_reason"] = "主脑判断任务可以拆成多个相对独立的单元，并行推进更合适。"
                for key in ("trial_candidates", "chain_stages", "swarm_units"):
                    if key in data:
                        meta[key] = data[key]
                task.meta = meta
                await db.commit()

                logger.info(
                    f"[Dispatcher] overmind analysis saved task={task_id} "
                    f"next={effective_next_state} blockers={len(blockers)} mode={exec_mode}"
                )
                if mode_selected:
                    await publish_stage_event(
                        self.bus,
                        trace_id=task.trace_id,
                        producer="dispatcher",
                        event_type="task.mode.selected",
                        task_id=task_id,
                        stage="routing",
                        payload={"mode": exec_mode, "source": "overmind"},
                    )
                return effective_next_state
        except Exception as e:
            logger.warning(f"[Dispatcher] overmind analysis parse failed {task_id}: {e}")
        return fallback_next_state

    # ── 调用 OpenClaw ────────────────────────────────────

    async def _invoke_agent(
        self,
        synapse: str,
        message: str,
        task_id: str,
        trace_id: str,
        timeout: int = 0,
    ) -> dict:
        if timeout <= 0:
            timeout = int(os.environ.get("HIVE_AGENT_TIMEOUT", "600"))
        """通过适配器调用 agent（openclaw / claude / mock）"""
        env = {
            **os.environ,
            "HIVE_TASK_ID":   task_id,
            "HIVE_TRACE_ID":  trace_id,
            "HIVE_SYNAPSE":   synapse,
            "HIVE_API_URL":   os.environ.get("HIVE_API_URL", "http://localhost:8765"),
        }
        try:
            return await self._adapter.invoke(synapse, message, env, timeout)
        except Exception as e:
            logger.error(f"[Dispatcher] 调用失败: {e}")
            return {"returncode": -1, "stdout": "", "stderr": str(e)}
