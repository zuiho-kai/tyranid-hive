"""虫群配置模型 —— Pydantic 校验"""

from typing import Literal, Optional, List
from pydantic import BaseModel, ConfigDict, Field


class OvermindConfig(BaseModel):
    """主脑配置"""
    model: str = "claude-sonnet-4-20250514"
    complexity_threshold: float = 0.7
    max_concurrent_broods: int = 5
    max_trials_per_race: int = 3


class SynapseConfig(BaseModel):
    """小主脑配置"""
    name: str
    domain: List[str]  # 领域标签，如 ["code", "debug"]
    model: str
    system_prompt: Optional[str] = None
    resident: bool = True  # 是否常驻内存
    max_broods: int = 3  # 最大同时管理工作组数


class StorageConfig(BaseModel):
    """存储配置"""
    backend: Literal["sqlite", "postgres"] = "sqlite"
    path: str = "data/hive.db"
    postgres_url: Optional[str] = None


class ChannelConfig(BaseModel):
    """频道配置"""
    expose_to_user: bool = True
    max_visible: int = 10
    default_collapsed: bool = True


class EvolutionConfig(BaseModel):
    """进化层配置"""
    enabled: bool = False
    trial_threshold: float = 0.8
    gene_pool_path: str = "data/gene_pool/"
    promotion_threshold: int = 100  # 战功晋升阈值
    demotion_threshold: int = -50  # 负战功降级阈值


class ToolConfig(BaseModel):
    """工具配置"""
    inherit_from_greyfield: bool = True
    custom_tools: List[str] = Field(default_factory=list)


class HiveConfig(BaseModel):
    """虫巢系统完整配置"""
    enabled: bool = False
    mode: Literal["auto", "simple", "hive"] = "auto"

    overmind: OvermindConfig = Field(default_factory=OvermindConfig)
    synapses: List[SynapseConfig] = Field(default_factory=list)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    channels: ChannelConfig = Field(default_factory=ChannelConfig)
    evolution: EvolutionConfig = Field(default_factory=EvolutionConfig)
    tools: ToolConfig = Field(default_factory=ToolConfig)

    model_config = ConfigDict(extra="allow")  # 允许扩展字段
