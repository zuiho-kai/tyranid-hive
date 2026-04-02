"""Evolution Master —— 自动经验萃取，从 Lessons 提炼 Playbook

流程（两阶段复盘）：
  Phase 1 — Reflect（诊断）：
    扫描 Lessons Bank，分析成功/失败模式，识别失败根因
    （tool问题 / 调用序列问题 / 输入理解问题）
  Phase 2 — Write（更新）：
    将诊断结果提炼为结构化 Playbook，语义聚类去重
    订阅 TrialClosed 事件，赛后自动触发
"""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from loguru import logger
from sqlalchemy import select, func, case

from greyfield_hive.models.lesson import Lesson
from greyfield_hive.models.episode import Episode, EpisodeStep
from greyfield_hive.services.lessons_bank import LessonsBank
from greyfield_hive.services.playbook_service import PlaybookService
from greyfield_hive.services.episode_store import EpisodeStore


@dataclass
class ReflectResult:
    """Phase 1 诊断结果"""
    domain:          str
    success_count:   int
    fail_count:      int
    fail_patterns:   dict[str, int]   # 失败根因 → 出现次数
    top_lessons:     list             # 筛选后的 top Lesson 对象
    clusters:        dict[str, list]  # 语义簇 → lesson id 列表


@dataclass
class EvolveResult:
    domain:           str
    lessons_used:     int
    playbook_id:      str
    playbook_slug:    str
    playbook_version: int
    is_new:           bool
    reflect:          Optional[ReflectResult] = None


class EvolutionMasterService:
    """Evolution Master 服务 —— 从经验库自动萃取作战手册"""

    LESSON_THRESHOLD = 5   # 触发进化所需的最少成功经验数

    def __init__(self, db) -> None:
        self._db = db
        self._bank = LessonsBank(db)
        self._pb_svc = PlaybookService(db)

    # ── 公开接口 ──────────────────────────────────────────

    async def scan_and_evolve(self) -> List[EvolveResult]:
        """扫描所有域，对达到阈值的域触发进化。返回本次进化结果列表。"""
        domains = await self._get_qualified_domains()
        results: List[EvolveResult] = []
        for domain in domains:
            result = await self.evolve_domain(domain)
            if result is not None:
                results.append(result)
        logger.info(f"[EvolutionMaster] 全域扫描完成，进化 {len(results)} 个域")
        return results

    async def evolve_domain(self, domain: str) -> Optional[EvolveResult]:
        """两阶段复盘：Reflect → Write"""
        success_lessons = await self._get_success_lessons(domain)
        if len(success_lessons) < self.LESSON_THRESHOLD:
            logger.debug(f"[EvolutionMaster] {domain} 成功经验 {len(success_lessons)} 条，未达阈值，跳过")
            return None

        # Phase 1: Reflect
        reflect = await self._reflect(domain, success_lessons)

        # Phase 2: Write
        top_lessons = reflect.top_lessons[:10]
        content = self._synthesize(domain, top_lessons, reflect)
        slug = f"evolved-{domain}"

        existing = await self._pb_svc._get_active(slug)
        if existing is None:
            pb = await self._pb_svc.create(
                slug=slug, domain=domain,
                title=f"{domain} 最佳实践（Evolution Master 生成）",
                content=content,
            )
            is_new = True
            logger.info(f"[EvolutionMaster] 新建 Playbook: {slug} v{pb.version}")
        else:
            pb = await self._pb_svc.create_new_version(
                slug=slug, content=content,
                notes=f"两阶段复盘：{len(top_lessons)} 条经验，{len(reflect.fail_patterns)} 种失败模式",
            )
            is_new = False
            logger.info(f"[EvolutionMaster] 更新 Playbook: {slug} → v{pb.version}")

        for lesson in top_lessons[:self.LESSON_THRESHOLD]:
            await self._bank.promote_to_playbook(lesson.id, pb.id)

        return EvolveResult(
            domain=domain, lessons_used=len(top_lessons),
            playbook_id=pb.id, playbook_slug=pb.slug,
            playbook_version=pb.version, is_new=is_new, reflect=reflect,
        )

    async def on_trial_closed(self, task_id: str, domain: str) -> None:
        """订阅 TrialClosed 事件，赛后自动触发域进化"""
        logger.info(f"[EvolutionMaster] TrialClosed → 触发 {domain} 域进化检查")
        try:
            result = await self.evolve_domain(domain)
            if result:
                logger.info(f"[EvolutionMaster] 赛后进化完成: {result.playbook_slug} v{result.playbook_version}")
        except Exception as e:
            logger.warning(f"[EvolutionMaster] 赛后进化失败 domain={domain}: {e}")

    async def get_domain_status(self) -> List[dict]:
        """返回各域的经验统计（用于仪表盘展示）"""
        result = await self._db.execute(
            select(
                Lesson.domain,
                func.count(Lesson.id).label("total"),
                func.sum(
                    case((Lesson.outcome == "success", 1), else_=0)
                ).label("success_count"),
            ).group_by(Lesson.domain)
        )
        rows = result.all()
        return [
            {
                "domain":        row.domain,
                "total":         row.total,
                "success_count": row.success_count or 0,
                "ready_to_evolve": (row.success_count or 0) >= self.LESSON_THRESHOLD,
            }
            for row in rows
        ]

    # ── 私有方法 ──────────────────────────────────────────

    async def _reflect(self, domain: str, lessons: List[Lesson]) -> ReflectResult:
        """Phase 1 Reflect：诊断失败模式，语义聚类（Phase 1 增强：接入 EpisodeStore）"""
        fail_lessons = await self._get_fail_lessons(domain)
        fail_patterns: dict[str, int] = defaultdict(int)

        # 原有：从 Lesson 内容提取失败模式
        for lesson in fail_lessons:
            content = (lesson.content or "").lower()
            if any(kw in content for kw in ("tool", "工具", "api")):
                fail_patterns["tool_issue"] += 1
            elif any(kw in content for kw in ("sequence", "顺序", "步骤", "order")):
                fail_patterns["sequence_issue"] += 1
            elif any(kw in content for kw in ("understand", "理解", "unclear", "ambiguous")):
                fail_patterns["understanding_issue"] += 1
            else:
                fail_patterns["strategy_issue"] += 1

        # Phase 1 新增：从 EpisodeStore 补充失败模式（更结构化，有 error_class）
        try:
            _ep_store = EpisodeStore(self._db)
            fail_episodes = await _ep_store.query_by_domain(domain, days=30)
            for ep in fail_episodes:
                if ep.outcome != "failure":
                    continue
                # 从 episode 步骤的 error_class 计数（此处直接统计 episode 级 outcome）
                fail_patterns["episode_failure"] = fail_patterns.get("episode_failure", 0) + 1
            if fail_episodes:
                logger.debug(
                    f"[EvolutionMaster] Episode 补充: domain={domain} "
                    f"episodes={len(fail_episodes)} "
                    f"fail={sum(1 for e in fail_episodes if e.outcome == 'failure')}"
                )
        except Exception as _e:
            logger.warning(f"[EvolutionMaster] EpisodeStore 查询失败（不影响进化）: {_e}")

        # 语义聚类：按 tags 分组
        clusters: dict[str, list] = defaultdict(list)
        for lesson in lessons:
            tags = [t.strip() for t in (lesson.tags or "").split(",") if t.strip()]
            key = tags[0] if tags else "general"
            clusters[key].append(lesson.id)

        # 去重：每个簇只保留频率最高的 lesson
        top_lessons = []
        seen_clusters: set[str] = set()
        for lesson in lessons:
            tags = [t.strip() for t in (lesson.tags or "").split(",") if t.strip()]
            key = tags[0] if tags else "general"
            if key not in seen_clusters:
                seen_clusters.add(key)
                top_lessons.append(lesson)
            elif len(top_lessons) < 10:
                top_lessons.append(lesson)

        return ReflectResult(
            domain=domain,
            success_count=len(lessons),
            fail_count=len(fail_lessons),
            fail_patterns=dict(fail_patterns),
            top_lessons=top_lessons,
            clusters=dict(clusters),
        )

    async def _get_fail_lessons(self, domain: str) -> List[Lesson]:
        result = await self._db.execute(
            select(Lesson)
            .where(Lesson.domain == domain, Lesson.outcome != "success")
            .order_by(Lesson.last_used.desc())
            .limit(20)
        )
        return list(result.scalars().all())

    async def _get_qualified_domains(self) -> List[str]:
        """查询成功经验数 >= 阈值的所有域"""
        result = await self._db.execute(
            select(Lesson.domain)
            .where(Lesson.outcome == "success")
            .group_by(Lesson.domain)
            .having(func.count(Lesson.id) >= self.LESSON_THRESHOLD)
        )
        return [row[0] for row in result.all()]

    async def _get_success_lessons(self, domain: str) -> List[Lesson]:
        """获取指定域的成功经验，按频率降序排列"""
        result = await self._db.execute(
            select(Lesson)
            .where(Lesson.domain == domain, Lesson.outcome == "success")
            .order_by(Lesson.frequency.desc(), Lesson.last_used.desc())
            .limit(20)
        )
        return list(result.scalars().all())

    @staticmethod
    def _synthesize(domain: str, lessons: List[Lesson], reflect: Optional[ReflectResult] = None) -> str:
        """Phase 2 Write：将诊断结果提炼为结构化 Playbook"""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            f"# {domain} 最佳实践",
            f"",
            f"> 由 Evolution Master 两阶段复盘自动生成，基于 {len(lessons)} 条成功经验",
            f"> 生成时间：{ts}",
            f"",
            f"## 核心原则",
            f"",
        ]

        for i, lesson in enumerate(lessons, 1):
            summary = (lesson.content or "").strip()
            if len(summary) > 150:
                summary = summary[:147] + "…"
            freq_tag = f"（频率：{lesson.frequency or 1}）" if (lesson.frequency or 0) > 1 else ""
            lines.append(f"{i}. {summary}{freq_tag}")

        # 失败模式诊断（来自 Reflect 阶段）
        if reflect and reflect.fail_patterns:
            lines += ["", "## 已知失败模式（避坑指南）", ""]
            pattern_names = {
                "tool_issue": "工具调用问题",
                "sequence_issue": "调用顺序问题",
                "understanding_issue": "输入理解问题",
                "strategy_issue": "策略选择问题",
            }
            for pattern, count in sorted(reflect.fail_patterns.items(), key=lambda x: -x[1]):
                name = pattern_names.get(pattern, pattern)
                lines.append(f"- {name}（出现 {count} 次）")

        lines += ["", "## 标签", ""]
        all_tags: set[str] = set()
        for lesson in lessons:
            if lesson.tags:
                for tag in lesson.tags.split(","):
                    t = tag.strip()
                    if t:
                        all_tags.add(t)
        lines.append(", ".join(sorted(all_tags)) if all_tags else domain)

        return "\n".join(lines)
