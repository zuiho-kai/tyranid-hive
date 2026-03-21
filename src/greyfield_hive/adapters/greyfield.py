"""Greyfield 适配器 —— 实现 DecisionRuntime 接口"""

from typing import AsyncIterator, Callable, Any
from pathlib import Path

from loguru import logger

# 导入 Greyfield 接口（如果安装了 greyfield）
try:
    from greywind.decision_runtime import DecisionRuntime, DecisionEvent
    GREYFIELD_AVAILABLE = True
except ImportError:
    GREYFIELD_AVAILABLE = False
    # 定义接口的本地副本（用于独立开发）
    from dataclasses import dataclass

    @dataclass
    class DecisionEvent:
        type: str
        payload: dict

    class DecisionRuntime:
        async def process(self, context_packet, send_fn, send_audio_fn, interrupt_flag):
            raise NotImplementedError()

from greyfield_hive.claw import TyranidClaw
from greyfield_hive.config import HiveConfig


class HiveDecisionRuntime(DecisionRuntime):
    """Greyfield DecisionRuntime 接口的 Hive 实现"""

    def __init__(self, config: HiveConfig, config_dir: str = "config"):
        self.config = config
        self.config_dir = config_dir
        self.hive = TyranidClaw(config, config_dir)
        logger.info("HiveDecisionRuntime 初始化完成")

    async def process(
        self,
        context_packet: Any,
        send_fn: Callable,
        send_audio_fn: Callable,
        interrupt_flag: Callable[[], bool],
    ) -> AsyncIterator[DecisionEvent]:
        """处理用户输入"""
        # 转换 ContextPacket 为 Hive Task
        task = self._convert_task(context_packet)

        # 提交到虫群
        async for event in self.hive.submit_task(task):
            if interrupt_flag():
                logger.info("任务被中断")
                break

            # 转换 Hive Event 为 DecisionEvent
            yield self._convert_event(event)

    def _convert_task(self, context_packet: Any) -> dict:
        """转换 ContextPacket 为 Hive Task"""
        # TODO: Phase E1 实现详细转换逻辑
        return {
            "type": "user_request",
            "input": getattr(context_packet, "user_input", {}),
            "context": {
                "thread": getattr(context_packet, "thread", {}),
                "session": getattr(context_packet, "session", {}),
                "persona": getattr(context_packet, "persona", {}),
            },
            "hive_state": getattr(context_packet, "hive_state", None),
        }

    def _convert_event(self, event: dict) -> DecisionEvent:
        """转换 Hive Event 为 DecisionEvent"""
        return DecisionEvent(
            type=event.get("type", "unknown"),
            payload=event.get("payload", {}),
        )

    def get_name(self) -> str:
        return "hive"


class AutoDecisionRuntime(DecisionRuntime):
    """自动选择：简单任务用 Simple，复杂任务用 Hive"""

    def __init__(self, simple_runtime: DecisionRuntime, hive_runtime: DecisionRuntime, threshold: float = 0.7):
        self.simple = simple_runtime
        self.hive = hive_runtime
        self.threshold = threshold

    async def process(
        self,
        context_packet: Any,
        send_fn: Callable,
        send_audio_fn: Callable,
        interrupt_flag: Callable[[], bool],
    ) -> AsyncIterator[DecisionEvent]:
        """自动判断复杂度并选择运行时"""
        complexity = self._estimate_complexity(context_packet)

        if complexity < self.threshold:
            logger.info(f"任务复杂度 {complexity:.2f} < {self.threshold}，使用 Simple 模式")
            async for event in self.simple.process(context_packet, send_fn, send_audio_fn, interrupt_flag):
                yield event
        else:
            logger.info(f"任务复杂度 {complexity:.22} >= {self.threshold}，使用 Hive 模式")
            async for event in self.hive.process(context_packet, send_fn, send_audio_fn, interrupt_flag):
                yield event

    def _estimate_complexity(self, context_packet: Any) -> float:
        """估算任务复杂度"""
        user_input = ""
        if hasattr(context_packet, "user_input"):
            user_input_obj = getattr(context_packet, "user_input")
            if hasattr(user_input_obj, "raw_text"):
                user_input = user_input_obj.raw_text.lower()

        # 简单规则（后续可用LLM判断）
        simple_keywords = ["你好", "谢谢", "再见", "在吗", "简单", "帮我"]
        complex_keywords = ["研究", "分析", "对比", "优化", "设计", "实现", "爬虫", "自动化", "架构", "方案"]

        if any(k in user_input for k in simple_keywords):
            return 0.3
        if any(k in user_input for k in complex_keywords):
            return 0.9

        return 0.5

    def get_name(self) -> str:
        return "auto"


def create_hive_runtime(
    hive_config: HiveConfig,
    greyfield_config_dir: str = "config"
) -> DecisionRuntime:
    """工厂函数：创建 Hive Runtime"""
    # 寻找 Hive 自己的 config 目录
    hive_config_dir = Path(greyfield_config_dir) / "hive"
    if not hive_config_dir.exists():
        # 使用默认配置
        hive_config_dir = Path(__file__).parent.parent / "config"

    return HiveDecisionRuntime(hive_config, str(hive_config_dir))
