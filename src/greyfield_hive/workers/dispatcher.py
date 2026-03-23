"""派发器 Worker —— 消费 task.dispatch 事件，调用 OpenClaw CLI 执行小主脑

工作流：
  task.dispatch 事件 → 读取 synapse ID
                    → 注入基因上下文（Lessons + Playbooks）
                    → 通过 OpenClawAdapter 调用 agent（openclaw / claude / mock）
                    → 回写 task.progress_log
                    → 自动写入经验教训（Lessons Bank）
"""

import asyncio
import os

from loguru import logger

from greyfield_hive.db import SessionLocal
from greyfield_hive.services.event_bus import (
    get_event_bus,
    BusEvent,
    TOPIC_TASK_DISPATCH,
    TOPIC_TASK_STATUS,
    TOPIC_AGENT_THOUGHTS,
    TOPIC_AGENT_HEARTBEAT,
)
from greyfield_hive.adapters.openclaw import get_adapter, OpenClawAdapter
from greyfield_hive.services.lessons_bank import LessonsBank
from greyfield_hive.services.playbook_service import PlaybookService
from greyfield_hive.services.fitness_service import FitnessService
from greyfield_hive.services.gene_loader import get_gene_loader


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

            await self.bus.publish(
                topic=TOPIC_AGENT_HEARTBEAT,
                trace_id=trace_id,
                event_type="agent.dispatch.start",
                producer="dispatcher",
                payload={"task_id": task_id, "synapse": synapse},
            )

            # 注入基因上下文
            enriched_message = await self._build_enriched_message(
                synapse=synapse,
                message=message,
                task_id=task_id,
                domain=domain,
            )

            logger.info(f"[Dispatcher] 派发 {task_id} → {synapse}: {message[:60]}")
            result = await self._invoke_agent(synapse, enriched_message, task_id, trace_id)

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

            # 回写 progress_log
            if task_id:
                await self._persist_progress(task_id, synapse, result)

            # 主脑输出：提取 exec_mode 并保存到任务
            if synapse == "overmind" and task_id:
                await self._save_exec_mode(task_id, result)

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

            # 推进状态机：通知 Orchestrator 进入下一状态
            if next_state and task_id:
                await self.bus.publish(
                    topic=TOPIC_TASK_STATUS,
                    trace_id=trace_id,
                    event_type="task.status.change",
                    producer="dispatcher",
                    payload={"task_id": task_id, "to": next_state},
                )
                logger.info(f"[Dispatcher] 状态推进 {task_id} → {next_state}")

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
            system_prompt = gene_loader.get_system_prompt(synapse)

            context_block = (
                f"## 你的角色\n{system_prompt}\n\n"
                f"---\n"
                f"[HIVE CONTEXT]\n"
                f"Task-ID : {task_id or '—'}\n"
                f"Synapse : {synapse}\n"
                f"Domain  : {domain}\n"
                f"\n## 历史经验（来自基因库）\n{lessons_text}"
                f"\n\n## 作战手册\n{playbooks_text}"
                f"\n\n## 你的任务\n{message}"
            )
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

    # ── exec_mode 提取 ───────────────────────────────────

    async def _save_exec_mode(self, task_id: str, result: dict) -> None:
        """从主脑 stdout 提取 exec_mode 并保存到任务 meta"""
        import json
        import re
        stdout = result.get("stdout", "")
        try:
            text = re.sub(r"^```(?:json)?\s*", "", stdout.strip(), flags=re.MULTILINE)
            text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                return
            data = json.loads(m.group())
            exec_mode = str(data.get("exec_mode", "solo")).lower()
            if exec_mode not in {"solo", "trial", "chain", "swarm"}:
                exec_mode = "solo"
            async with SessionLocal() as db:
                from greyfield_hive.services.task_service import TaskService
                svc = TaskService(db)
                task = await svc.update_exec_mode(task_id, exec_mode)
                meta = dict(task.meta or {})
                for key in ("trial_candidates", "chain_stages", "swarm_units"):
                    if key in data:
                        meta[key] = data[key]
                task.meta = meta
                await db.commit()
                logger.info(f"[Dispatcher] exec_mode={exec_mode} 已保存 → {task_id}")
        except Exception as e:
            logger.warning(f"[Dispatcher] exec_mode 提取失败 {task_id}: {e}")

    # ── 调用 OpenClaw ────────────────────────────────────

    async def _invoke_agent(
        self,
        synapse: str,
        message: str,
        task_id: str,
        trace_id: str,
        timeout: int = 300,
    ) -> dict:
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
