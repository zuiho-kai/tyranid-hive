"""Greyfield Hive — 泰伦虫群核心

基于 OpenClaw 框架的多 Agent 调度系统，适配 Greyfield 宿主。
"""

__version__ = "0.1.0"

# 核心导出（用户最常用的接口）
from greyfield_hive.claw import TyranidClaw
from greyfield_hive.config import HiveConfig

__all__ = [
    "TyranidClaw",
    "HiveConfig",
    "__version__",
]
