"""Docker 配置正确性测试 —— 不运行 docker，只验证文件内容和结构"""

import re
from pathlib import Path
import pytest
import yaml

ROOT = Path(__file__).parents[1]


# ── Dockerfile ─────────────────────────────────────────────

def read_dockerfile() -> str:
    p = ROOT / "Dockerfile"
    assert p.exists(), "Dockerfile 不存在"
    return p.read_text(encoding="utf-8")


def test_dockerfile_has_frontend_builder_stage():
    """Dockerfile 包含前端构建阶段"""
    df = read_dockerfile()
    assert "frontend-builder" in df
    assert "npm run build" in df


def test_dockerfile_copies_genes_dir():
    """Dockerfile 复制 genes/ 目录（GeneLoader 运行时需要）"""
    df = read_dockerfile()
    assert re.search(r"COPY\s+genes/", df), "缺少 COPY genes/ 指令"


def test_dockerfile_copies_config_dir():
    """Dockerfile 复制 config/ 目录"""
    df = read_dockerfile()
    assert re.search(r"COPY\s+config/", df)


def test_dockerfile_copies_migrations():
    """Dockerfile 复制 migrations/ 目录（alembic 升级所需）"""
    df = read_dockerfile()
    assert re.search(r"COPY\s+migrations/", df), "缺少 COPY migrations/ 指令"


def test_dockerfile_copies_alembic_ini():
    """Dockerfile 复制 alembic.ini"""
    df = read_dockerfile()
    assert "alembic.ini" in df


def test_dockerfile_installs_from_pyproject():
    """Dockerfile 用 pip install -e 安装，不硬编码包列表"""
    df = read_dockerfile()
    assert 'pip install' in df
    assert '-e' in df


def test_dockerfile_exposes_8765():
    """Dockerfile 暴露 8765 端口"""
    df = read_dockerfile()
    assert "EXPOSE 8765" in df


def test_dockerfile_has_healthcheck():
    """Dockerfile 包含 HEALTHCHECK 指令"""
    df = read_dockerfile()
    assert "HEALTHCHECK" in df
    assert "/health" in df


def test_dockerfile_sets_hive_db_path():
    """Dockerfile 设置 HIVE_DB_PATH 环境变量"""
    df = read_dockerfile()
    assert "HIVE_DB_PATH" in df
    assert "/data/hive.db" in df


# ── docker-compose.yml ─────────────────────────────────────

def read_compose() -> dict:
    p = ROOT / "docker-compose.yml"
    assert p.exists(), "docker-compose.yml 不存在"
    # 去掉注释行（# Compose Spec 行），yaml 能正常解析
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def test_compose_has_hive_service():
    """docker-compose.yml 包含 hive 服务"""
    dc = read_compose()
    assert "hive" in dc["services"]


def test_compose_hive_uses_local_build():
    """hive 服务使用本地 Dockerfile 构建"""
    dc = read_compose()
    hive = dc["services"]["hive"]
    assert "build" in hive
    assert hive["build"]["dockerfile"] == "Dockerfile"


def test_compose_hive_exposes_8765():
    """hive 服务映射 8765 端口"""
    dc = read_compose()
    ports = dc["services"]["hive"]["ports"]
    assert any("8765" in str(p) for p in ports)


def test_compose_has_hive_data_volume():
    """docker-compose.yml 定义 hive_data 数据卷"""
    dc = read_compose()
    assert "hive_data" in dc.get("volumes", {})


def test_compose_hive_has_healthcheck():
    """hive 服务配置了 healthcheck"""
    dc = read_compose()
    hive = dc["services"]["hive"]
    assert "healthcheck" in hive


def test_compose_mounts_genes_dir():
    """hive 服务挂载本地 genes/ 目录"""
    dc = read_compose()
    volumes = dc["services"]["hive"].get("volumes", [])
    volume_strs = [str(v) for v in volumes]
    assert any("genes" in v for v in volume_strs), \
        "hive 服务未挂载 genes/ 目录，热更新基因文件将无效"


def test_compose_has_postgres_profile():
    """postgres 服务使用 postgres profile（可选启用）"""
    dc = read_compose()
    if "postgres" not in dc["services"]:
        pytest.skip("无 postgres 服务")
    pg = dc["services"]["postgres"]
    assert "postgres" in pg.get("profiles", [])


def test_compose_no_required_false():
    """docker-compose.yml 不使用 required: false（v3.9 不支持）"""
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "required: false" not in text, \
        "docker-compose.yml 包含 `required: false`，该语法不兼容 v3.9"


# ── install.sh ─────────────────────────────────────────────

def test_install_sh_exists():
    """install.sh 存在"""
    assert (ROOT / "install.sh").exists()


def test_install_sh_is_executable():
    """install.sh 有执行权限（git 可执行位 或 POSIX 权限）"""
    import sys, subprocess, stat
    p = ROOT / "install.sh"
    # Windows：通过 git 检查 mode
    if sys.platform == "win32":
        result = subprocess.run(
            ["git", "ls-files", "--format=%(objectmode)", "install.sh"],
            capture_output=True, text=True, cwd=ROOT
        )
        mode_str = result.stdout.strip()
        assert mode_str in ("100755", ""), \
            f"install.sh 在 git 中无可执行位（mode={mode_str!r}）"
    else:
        mode = p.stat().st_mode
        assert bool(mode & stat.S_IXUSR), "install.sh 无执行权限"


def test_install_sh_supports_docker_mode():
    """install.sh 包含 --docker 安装模式"""
    text = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "--docker" in text
    assert "docker compose" in text or "docker-compose" in text


def test_install_sh_supports_local_mode():
    """install.sh 包含 --local 安装模式"""
    text = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "--local" in text
    assert "python3 -m venv" in text
