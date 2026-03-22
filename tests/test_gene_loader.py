"""GeneLoader 服务测试 —— L2 基因 YAML 加载、缓存、fallback"""

import pytest
import yaml
from pathlib import Path

from greyfield_hive.services.gene_loader import GeneLoader


@pytest.fixture
def gene_dir(tmp_path: Path) -> Path:
    """创建临时 genes/L2/ 目录，写入两个测试 YAML"""
    d = tmp_path / "L2"
    d.mkdir()

    # 标准 synapse
    (d / "synapse_code_expert.yaml").write_text(yaml.dump({
        "gene": {
            "synapse_id": "code-expert",
            "tier": 2,
            "domain": "coding",
            "system_prompt": "你是代码专家，负责写高质量代码。",
        }
    }), encoding="utf-8")

    # 连字符 ID，文件名使用下划线
    (d / "synapse_research_analyst.yaml").write_text(yaml.dump({
        "gene": {
            "synapse_id": "research-analyst",
            "tier": 2,
            "domain": "research",
            "system_prompt": "你是研究分析师，负责信息采集。",
        }
    }), encoding="utf-8")

    return d


@pytest.fixture
def loader(gene_dir: Path) -> GeneLoader:
    return GeneLoader(genes_dir=gene_dir)


# ── 正常加载 ──────────────────────────────────────────────

def test_get_system_prompt_exact_match(loader):
    """精确命名匹配（synapse_code_expert.yaml → code-expert）"""
    prompt = loader.get_system_prompt("code-expert")
    assert "代码专家" in prompt


def test_get_system_prompt_hyphen_to_underscore(loader):
    """连字符 ID 自动转下划线匹配文件（research-analyst → synapse_research_analyst.yaml）"""
    prompt = loader.get_system_prompt("research-analyst")
    assert "研究分析师" in prompt


def test_get_gene_returns_dict(loader):
    """get_gene 返回完整 gene 节点"""
    gene = loader.get_gene("code-expert")
    assert gene is not None
    assert gene["synapse_id"] == "code-expert"
    assert gene["domain"] == "coding"
    assert gene["tier"] == 2


def test_get_gene_missing_returns_none(loader):
    """不存在的 synapse 返回 None"""
    gene = loader.get_gene("nonexistent-synapse")
    assert gene is None


def test_fallback_prompt_when_synapse_missing(loader):
    """不存在时返回通用 fallback 提示词（不崩溃）"""
    prompt = loader.get_system_prompt("unknown-synapse")
    assert len(prompt) > 10
    assert "Synapse" in prompt or "小主脑" in prompt or "任务" in prompt


# ── 缓存行为 ──────────────────────────────────────────────

def test_caching_returns_same_dict(loader):
    """同一 synapse 多次调用返回同一对象（缓存命中）"""
    g1 = loader.get_gene("code-expert")
    g2 = loader.get_gene("code-expert")
    assert g1 is g2


def test_invalidate_single(loader):
    """invalidate(synapse_id) 清除单条缓存"""
    loader.get_gene("code-expert")          # 写入缓存
    loader.invalidate("code-expert")
    assert "code-expert" not in loader._cache


def test_invalidate_all(loader):
    """invalidate() 清除全部缓存"""
    loader.get_gene("code-expert")
    loader.get_gene("research-analyst")
    loader.invalidate()
    assert loader._cache == {}


# ── list_synapses ─────────────────────────────────────────

def test_list_synapses(loader):
    """list_synapses 返回目录中所有 synapse ID"""
    ids = loader.list_synapses()
    assert "code-expert" in ids
    assert "research-analyst" in ids


def test_list_synapses_empty_dir(tmp_path):
    """空目录返回空列表"""
    empty = tmp_path / "empty_L2"
    empty.mkdir()
    loader = GeneLoader(genes_dir=empty)
    assert loader.list_synapses() == []


def test_list_synapses_nonexistent_dir(tmp_path):
    """目录不存在时返回空列表，不抛异常"""
    loader = GeneLoader(genes_dir=tmp_path / "no_such_dir")
    assert loader.list_synapses() == []


# ── 容错 ─────────────────────────────────────────────────

def test_malformed_yaml_does_not_crash(tmp_path):
    """损坏的 YAML 文件不导致崩溃，返回 None"""
    d = tmp_path / "L2"
    d.mkdir()
    (d / "synapse_bad.yaml").write_text(": {invalid: yaml: [", encoding="utf-8")
    loader = GeneLoader(genes_dir=d)
    gene = loader.get_gene("bad")
    assert gene is None


def test_yaml_without_gene_key_returns_none(tmp_path):
    """YAML 存在但缺少 gene 键时返回 None"""
    d = tmp_path / "L2"
    d.mkdir()
    (d / "synapse_weird.yaml").write_text(yaml.dump({"not_gene": {}}), encoding="utf-8")
    loader = GeneLoader(genes_dir=d)
    gene = loader.get_gene("weird")
    assert gene is None


# ── 真实基因文件集成测试 ──────────────────────────────────

def test_real_genes_dir_loads_overmind():
    """使用项目真实 genes/L2/ 目录，能加载 overmind 基因"""
    real_loader = GeneLoader()  # 使用默认路径
    if not real_loader._dir.exists():
        pytest.skip("genes/L2/ 目录不存在，跳过集成测试")
    prompt = real_loader.get_system_prompt("overmind")
    # 基本验证：内容非空，来自真实文件
    assert len(prompt) > 20


def test_real_genes_list_known_synapses():
    """真实目录应包含至少 3 个内置 Synapse"""
    real_loader = GeneLoader()
    if not real_loader._dir.exists():
        pytest.skip("genes/L2/ 目录不存在，跳过集成测试")
    ids = real_loader.list_synapses()
    assert len(ids) >= 3
    assert "overmind" in ids
