"""TaskFingerprintService —— 从任务标题/描述提取结构化特征

Phase 1：纯关键词匹配，零 LLM 成本。
Phase 2+ 可升级为 embedding 检索，接口不变。

特征维度：
  domain          — 主域（coding / devops / research / finance / general）
  structural_tags — 结构标签（multi-file / linear-dep / parallel / browser / api / ...）
  complexity      — 复杂度（low / medium / high）
  tool_hints      — 暗示的工具（browser / api / file / shell / ...）
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ── 关键词规则表 ──────────────────────────────────────────────────────────────

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "coding":   ["代码", "实现", "函数", "class", "python", "javascript", "bug", "重构",
                 "接口", "api", "测试", "test", "debug", "compile", "算法"],
    "devops":   ["docker", "ci", "cd", "部署", "deploy", "kubernetes", "nginx",
                 "服务器", "pipeline", "workflow", "镜像", "容器"],
    "research": ["搜索", "调研", "分析", "报告", "总结", "摘要", "新闻", "资料",
                 "search", "research", "analyze", "summary"],
    "finance":  ["股票", "行情", "基金", "期货", "交易", "收益", "市场", "涨跌",
                 "portfolio", "finance", "stock", "market"],
}

_STRUCTURAL_TAGS: dict[str, list[str]] = {
    "multi-file":   ["多文件", "重构", "迁移", "refactor", "migration", "系统", "架构"],
    "linear-dep":   ["先", "然后", "再", "步骤", "阶段", "依赖", "串行", "p1", "p2", "phase"],
    "parallel":     ["并行", "同时", "并发", "批量", "多个", "一批", "concurrent"],
    "browser":      ["浏览器", "爬虫", "抓取", "playwright", "selenium", "网页", "browser"],
    "api":          ["api", "http", "请求", "接口", "endpoint", "rest", "graphql"],
    "file-io":      ["文件", "读写", "csv", "excel", "json", "xml", "上传", "下载"],
    "high-risk":    ["删除", "清空", "重置", "drop", "truncate", "不可回滚", "生产", "production"],
}

_COMPLEXITY_HIGH: list[str] = [
    "系统", "架构", "重构", "迁移", "整体", "全面", "完整", "复杂", "多模块", "大型"
]
_COMPLEXITY_LOW: list[str] = [
    "简单", "单个", "一个", "快速", "小", "轻量", "demo", "示例", "hello"
]

_TOOL_HINTS: dict[str, list[str]] = {
    "browser": ["浏览器", "playwright", "selenium", "爬虫", "网页", "browser", "scrape"],
    "api":     ["api", "http", "curl", "requests", "fetch", "rest"],
    "file":    ["文件", "目录", "路径", "读写", "file", "dir", "path"],
    "shell":   ["命令", "终端", "shell", "bash", "cmd", "powershell", "执行"],
    "llm":     ["llm", "gpt", "claude", "模型", "对话", "prompt", "生成"],
}


# ── 数据类 ───────────────────────────────────────────────────────────────────

@dataclass
class TaskFingerprint:
    """任务结构化特征向量"""

    domain:          str            = "general"
    structural_tags: list[str]      = field(default_factory=list)
    complexity:      str            = "medium"
    tool_hints:      list[str]      = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "domain":          self.domain,
            "structural_tags": self.structural_tags,
            "complexity":      self.complexity,
            "tool_hints":      self.tool_hints,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TaskFingerprint":
        return cls(
            domain=d.get("domain", "general"),
            structural_tags=d.get("structural_tags", []),
            complexity=d.get("complexity", "medium"),
            tool_hints=d.get("tool_hints", []),
        )


# ── 服务 ─────────────────────────────────────────────────────────────────────

class TaskFingerprintService:
    """从任务标题/描述提取结构化指纹（Phase 1：关键词匹配）"""

    def extract(self, title: str, description: str = "",
                domain: str = "") -> TaskFingerprint:
        """提取任务指纹。同步方法，无 IO，随时可调用。"""
        text = (title + " " + description).lower()

        resolved_domain = domain if domain and domain != "general" else self._match_domain(text)
        tags   = self._match_tags(text)
        hints  = self._match_tool_hints(text)
        complexity = self._estimate_complexity(text)

        return TaskFingerprint(
            domain=resolved_domain,
            structural_tags=tags,
            complexity=complexity,
            tool_hints=hints,
        )

    # ── 内部匹配逻辑 ──────────────────────────────────────────────────────────

    def _match_domain(self, text: str) -> str:
        scores: dict[str, int] = {}
        for domain, keywords in _DOMAIN_KEYWORDS.items():
            scores[domain] = sum(1 for kw in keywords if kw in text)
        best = max(scores, key=lambda d: scores[d])
        return best if scores[best] > 0 else "general"

    def _match_tags(self, text: str) -> list[str]:
        return [tag for tag, kws in _STRUCTURAL_TAGS.items()
                if any(kw in text for kw in kws)]

    def _estimate_complexity(self, text: str) -> str:
        if any(kw in text for kw in _COMPLEXITY_HIGH):
            return "high"
        if any(kw in text for kw in _COMPLEXITY_LOW):
            return "low"
        return "medium"

    def _match_tool_hints(self, text: str) -> list[str]:
        return [tool for tool, kws in _TOOL_HINTS.items()
                if any(kw in text for kw in kws)]
