"""Evolution Master —— 自动经验萃取，从 Lessons 提炼 Playbook

流程：
  1. 扫描 Lessons Bank，按域统计成功经验数量
  2. 达到阈值（默认 5 条成功经验）触发提炼
  3. 启发式合成：将 top-K Lesson 格式化为结构化 Playbook 内容
  4. 创建新 Playbook 或为已有 Playbook 创建新版本
  5. 将已使用的 Lesson 关联到生成的 Playbook（promote_to_playbook）
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from loguru import logger
from sqlalchemy import select, func, case

from greyfield_hive.models.lesson import Lesson
from greyfield_hive.services.lessons_bank import LessonsBank
from greyfield_hive.services.playbook_service import PlaybookService


@dataclass
class EvolveResult:
    domain:           str
    lessons_used:     int
    playbook_id:      str
    playbook_slug:    str
    playbook_version: int
    is_new:           bool    # True = 新建，False = 新版本


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
        """为指定域提炼经验，生成/更新 Playbook。

        如果成功经验数不足阈值，返回 None。
        """
        # 取该域所有成功经验，按使用频率排序
        success_lessons = await self._get_success_lessons(domain)
        if len(success_lessons) < self.LESSON_THRESHOLD:
            logger.debug(
                f"[EvolutionMaster] {domain} 成功经验仅 {len(success_lessons)} 条，"
                f"未达阈值 {self.LESSON_THRESHOLD}，跳过"
            )
            return None

        top_lessons = success_lessons[:10]  # 取前 10 条用于合成
        content = self._synthesize(domain, top_lessons)
        slug = f"evolved-{domain}"

        # 判断是新建还是更新
        existing = await self._pb_svc._get_active(slug)
        if existing is None:
            pb = await self._pb_svc.create(
                slug=slug,
                domain=domain,
                title=f"{domain} 最佳实践（Evolution Master 生成）",
                content=content,
            )
            is_new = True
            logger.info(f"[EvolutionMaster] 新建 Playbook: {slug} v{pb.version} (domain={domain})")
        else:
            pb = await self._pb_svc.create_new_version(
                slug=slug,
                content=content,
                notes=f"Evolution Master 经验萃取：使用 {len(top_lessons)} 条经验更新",
            )
            is_new = False
            logger.info(f"[EvolutionMaster] 更新 Playbook: {slug} → v{pb.version} (domain={domain})")

        # 关联 lesson → playbook
        for lesson in top_lessons[:self.LESSON_THRESHOLD]:
            await self._bank.promote_to_playbook(lesson.id, pb.id)

        return EvolveResult(
            domain=domain,
            lessons_used=len(top_lessons),
            playbook_id=pb.id,
            playbook_slug=pb.slug,
            playbook_version=pb.version,
            is_new=is_new,
        )

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
    def _synthesize(domain: str, lessons: List[Lesson]) -> str:
        """启发式合成：将 Lessons 提炼为结构化 Playbook 内容"""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            f"# {domain} 最佳实践",
            f"",
            f"> 由 Evolution Master 自动萃取，基于 {len(lessons)} 条成功经验",
            f"> 生成时间：{ts}",
            f"",
            f"## 核心原则",
            f"",
        ]

        for i, lesson in enumerate(lessons, 1):
            # 取 content 前 150 字符作为摘要
            summary = (lesson.content or "").strip()
            if len(summary) > 150:
                summary = summary[:147] + "…"
            freq_tag = f"（使用频率：{lesson.frequency or 1}）" if (lesson.frequency or 0) > 1 else ""
            lines.append(f"{i}. {summary}{freq_tag}")

        lines += [
            f"",
            f"## 标签",
            f"",
        ]
        # 收集所有 tags
        all_tags: set[str] = set()
        for lesson in lessons:
            if lesson.tags:
                for tag in lesson.tags.split(","):
                    t = tag.strip()
                    if t:
                        all_tags.add(t)
        if all_tags:
            lines.append(", ".join(sorted(all_tags)))
        else:
            lines.append(domain)

        return "\n".join(lines)
