"""Overmind Solo Mode Agent —— 主脑用 LLM 分析任务、注入基因上下文、输出 Todos

工作流：
  1. 加载基因上下文（宪法 + 主脑 L2 Gene）
  2. 搜索相关 Lessons（经验教训）和 Playbooks（作战手册）
  3. 构建提示词，调用 Anthropic API
  4. 解析 JSON 响应，返回 OvermindResult
  5. 调用方负责将 todos / 进度写回数据库
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from loguru import logger

from greyfield_hive.agents.llm_client import AnthropicClient

# 配置文件相对于本模块的位置
_CONFIG_ROOT = Path(__file__).parent.parent.parent.parent.parent / "config"


@dataclass
class OvermindResult:
    """主脑分析结果"""
    summary: str
    todos: list[str]
    risks: list[str]
    recommended_state: str
    domain: str
    raw_response: str = ""
    exec_mode: str = "solo"
    mode_justification: str = ""
    trial_candidates: list[str] = field(default_factory=list)
    chain_stages: list[str] = field(default_factory=list)
    swarm_units: list[dict] = field(default_factory=list)


# ── 基因上下文加载 ────────────────────────────────────────

def _load_constitution(config_root: Path) -> str:
    """从 constitution/baseline.yaml 加载安全规则"""
    path = config_root / "genes" / "constitution" / "baseline.yaml"
    if not path.exists():
        return ""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        lines: list[str] = []
        for section, rules in data.items():
            if isinstance(rules, list):
                for rule in rules:
                    if isinstance(rule, dict) and "rule" in rule:
                        lines.append(f"- {rule['rule']}")
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"[Overmind] 加载宪法失败: {e}")
        return ""


def _load_overmind_gene(config_root: Path) -> str:
    """从 genes/L2/synapse_overmind.yaml 加载主脑角色 Prompt"""
    path = config_root / "genes" / "L2" / "synapse_overmind.yaml"
    if not path.exists():
        return ""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data.get("gene", {}).get("system_prompt", "")
    except Exception as e:
        logger.warning(f"[Overmind] 加载主脑基因失败: {e}")
        return ""


# ── Lessons / Playbooks 上下文 ────────────────────────────

def _format_lessons(lessons: list[dict]) -> str:
    if not lessons:
        return "（无相关经验）"
    parts = []
    for l in lessons[:5]:
        parts.append(
            f"[{l.get('outcome', '?')}][{l.get('domain', '?')}] "
            f"{l.get('content', '')[:120]}"
        )
    return "\n".join(parts)


def _format_playbooks(playbooks: list[dict]) -> str:
    if not playbooks:
        return "（无相关手册）"
    parts = []
    for p in playbooks[:3]:
        parts.append(
            f"《{p.get('title', '?')}》(v{p.get('version', 1)}, "
            f"成功率 {int((p.get('success_rate', 0) or 0) * 100)}%)\n"
            f"{p.get('content', '')[:200]}"
        )
    return "\n\n".join(parts)


# ── 提示词构建 ────────────────────────────────────────────

_SYSTEM_TEMPLATE = """\
{gene_prompt}

## 强制规则（宪法）
{constitution}

## 执行模式选择规则
- solo：简单任务，单主脑直接执行（默认）
- trial：有多种可行方案、需要择优时，双路赛马
- chain：多阶段线性依赖任务，串行接棒
- swarm：多个完全独立的子任务，可并行执行

## 输出格式
你的回复必须是一个 JSON 对象，格式如下（不要包含任何其他内容）：
{{
  "summary": "一句话概括任务核心目标",
  "domain": "任务领域（如 coding / devops / research / planning）",
  "todos": ["子任务1", "子任务2", "子任务3"],
  "risks": ["风险点1", "风险点2"],
  "recommended_state": "Planning",
  "exec_mode": "solo",
  "mode_justification": "选择该模式的理由",
  "trial_candidates": [],
  "chain_stages": [],
  "swarm_units": []
}}

recommended_state 只能是以下之一：Planning / Executing / Dormant
exec_mode 只能是以下之一：solo / trial / chain / swarm
trial_candidates：Trial 模式时填两个 synapse ID，如 ["code-expert", "research-analyst"]
chain_stages：Chain 模式时填有序 synapse 列表，如 ["code-expert", "code-expert"]
swarm_units：Swarm 模式时填 unit 列表，如 [{{"synapse": "code-expert", "message": "子任务描述"}}]
"""

_USER_TEMPLATE = """\
## 任务信息
标题：{title}
描述：{description}

## 相关经验教训（从基因库检索）
{lessons}

## 相关作战手册
{playbooks}

请分析这个任务，拆解子任务，识别风险，给出建议。
"""


# ── Overmind Agent ────────────────────────────────────────

class OvermindAgent:
    """主脑 Solo Mode Agent"""

    def __init__(
        self,
        client: Optional[AnthropicClient] = None,
        config_root: Optional[Path] = None,
    ) -> None:
        self.client = client or AnthropicClient()
        self._config_root = config_root or _CONFIG_ROOT

        # 启动时加载（轻量，缓存在内存中）
        self._constitution = _load_constitution(self._config_root)
        self._gene_prompt = _load_overmind_gene(self._config_root)

    def is_available(self) -> bool:
        return self.client.is_available()

    def _build_system(self) -> str:
        gene_prompt = self._gene_prompt or "你是 Tyranid Hive 的主脑，负责任务分析与拆解。"
        constitution = self._constitution or "（无额外约束）"
        return _SYSTEM_TEMPLATE.format(gene_prompt=gene_prompt, constitution=constitution)

    def _build_user_message(
        self,
        title: str,
        description: str,
        lessons: list[dict],
        playbooks: list[dict],
    ) -> str:
        return _USER_TEMPLATE.format(
            title=title,
            description=description or "（无描述）",
            lessons=_format_lessons(lessons),
            playbooks=_format_playbooks(playbooks),
        )

    def _parse_response(self, raw: str) -> OvermindResult:
        """从 LLM 响应中提取 JSON，容错处理"""
        # 先尝试直接 parse
        text = raw.strip()
        # 去掉可能的 markdown 代码块
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # 尝试从文本中提取 JSON 对象
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group())
                except json.JSONDecodeError:
                    logger.warning("[Overmind] JSON 解析失败，返回降级结果")
                    return OvermindResult(
                        summary="无法解析主脑输出",
                        todos=[],
                        risks=["LLM 输出解析失败"],
                        recommended_state="Dormant",
                        domain="unknown",
                        raw_response=raw,
                    )
            else:
                logger.warning("[Overmind] 响应中未找到 JSON 对象")
                return OvermindResult(
                    summary=raw[:100],
                    todos=[],
                    risks=["LLM 响应格式异常"],
                    recommended_state="Dormant",
                    domain="unknown",
                    raw_response=raw,
                )

        valid_modes = {"solo", "trial", "chain", "swarm"}
        exec_mode = str(data.get("exec_mode", "solo")).lower()
        if exec_mode not in valid_modes:
            exec_mode = "solo"

        return OvermindResult(
            summary=str(data.get("summary", "")),
            todos=[str(t) for t in data.get("todos", []) if t],
            risks=[str(r) for r in data.get("risks", []) if r],
            recommended_state=str(data.get("recommended_state", "Planning")),
            domain=str(data.get("domain", "general")),
            raw_response=raw,
            exec_mode=exec_mode,
            mode_justification=str(data.get("mode_justification", "")),
            trial_candidates=[str(s) for s in data.get("trial_candidates", []) if s],
            chain_stages=[str(s) for s in data.get("chain_stages", []) if s],
            swarm_units=[u for u in data.get("swarm_units", []) if isinstance(u, dict)],
        )

    async def analyze(
        self,
        title: str,
        description: str = "",
        lessons: list[dict] | None = None,
        playbooks: list[dict] | None = None,
    ) -> OvermindResult:
        """主脑分析任务，返回 OvermindResult（核心入口）"""
        system_prompt = self._build_system()
        user_message = self._build_user_message(
            title=title,
            description=description,
            lessons=lessons or [],
            playbooks=playbooks or [],
        )

        logger.info(f"[Overmind] 分析任务: {title[:50]}")
        raw = await self.client.complete(
            messages=[{"role": "user", "content": user_message}],
            system=system_prompt,
            max_tokens=2048,
            temperature=0.1,
        )

        result = self._parse_response(raw)
        logger.info(
            f"[Overmind] 分析完成: domain={result.domain}, "
            f"todos={len(result.todos)}, state={result.recommended_state}"
        )
        return result
