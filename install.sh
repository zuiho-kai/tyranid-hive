#!/usr/bin/env bash
# Tyranid Hive 安装脚本
# 用法：bash install.sh [--docker | --local]
set -euo pipefail

HIVE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${HIVE_DATA_DIR:-$HOME/.tyranid-hive/data}"
PORT="${HIVE_PORT:-8765}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[HIVE]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERR ]${NC} $*" >&2; }

require_cmd() {
    command -v "$1" &>/dev/null || { error "需要 '$1' 但未安装。请先安装后重试。"; exit 1; }
}

print_banner() {
    echo ""
    echo "  ████████╗██╗   ██╗██████╗  █████╗ ███╗   ██╗██╗██████╗ "
    echo "     ██╔══╝╚██╗ ██╔╝██╔══██╗██╔══██╗████╗  ██║██║██╔══██╗"
    echo "     ██║    ╚████╔╝ ██████╔╝███████║██╔██╗ ██║██║██║  ██║"
    echo "     ██║     ╚██╔╝  ██╔══██╗██╔══██║██║╚██╗██║██║██║  ██║"
    echo "     ██║      ██║   ██║  ██║██║  ██║██║ ╚████║██║██████╔╝"
    echo "     ╚═╝      ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝╚═════╝ "
    echo ""
    echo "            ██╗  ██╗██╗██╗   ██╗███████╗"
    echo "            ██║  ██║██║██║   ██║██╔════╝"
    echo "            ███████║██║██║   ██║█████╗  "
    echo "            ██╔══██║██║╚██╗ ██╔╝██╔══╝  "
    echo "            ██║  ██║██║ ╚████╔╝ ███████╗"
    echo "            ╚═╝  ╚═╝╚═╝  ╚═══╝  ╚══════╝"
    echo ""
    info "Tyranid Hive —— 泰伦虫群多 Agent 编排框架"
    echo ""
}

install_docker() {
    info "使用 Docker 模式安装…"
    require_cmd docker
    require_cmd docker-compose || require_cmd "docker compose"

    cd "$HIVE_DIR"

    info "构建镜像（首次构建需要几分钟）…"
    docker compose build

    mkdir -p "$DATA_DIR"
    info "数据目录：$DATA_DIR"

    # 创建环境变量文件（如果不存在）
    if [[ ! -f "$HIVE_DIR/.env" ]]; then
        cat > "$HIVE_DIR/.env" <<EOF
# Tyranid Hive 环境配置
HIVE_PORT=${PORT}
HIVE_DATA_DIR=${DATA_DIR}
EOF
        info "已生成 .env 配置文件"
    fi

    info "启动服务…"
    HIVE_DATA_DIR="$DATA_DIR" HIVE_PORT="$PORT" docker compose up -d

    echo ""
    info "✅ 安装完成！"
    info "   Dashboard：http://localhost:${PORT}"
    info "   API 文档：http://localhost:${PORT}/docs"
    info "   停止服务：docker compose down"
    info "   查看日志：docker compose logs -f"
}

install_local() {
    info "使用本地模式安装…"
    require_cmd python3

    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"; then
        info "Python 版本：$PYTHON_VERSION ✓"
    else
        error "需要 Python 3.10+，当前版本：$PYTHON_VERSION"
        exit 1
    fi

    cd "$HIVE_DIR"

    # 创建虚拟环境
    if [[ ! -d ".venv" ]]; then
        info "创建虚拟环境 .venv…"
        python3 -m venv .venv
    fi

    source .venv/bin/activate

    info "安装 Python 依赖…"
    pip install --quiet --upgrade pip
    pip install --quiet -e ".[server]"

    # 构建前端（如有 Node.js）
    if command -v node &>/dev/null && command -v npm &>/dev/null; then
        NODE_VERSION=$(node --version)
        info "Node.js 版本：$NODE_VERSION，构建前端…"
        cd dashboard
        npm ci --silent
        npm run build
        cd ..
        info "前端构建完成"
    else
        warn "未检测到 Node.js，跳过前端构建。Dashboard 可能不可用。"
        warn "安装 Node.js 后运行：cd dashboard && npm ci && npm run build"
    fi

    mkdir -p "$DATA_DIR"
    info "数据目录：$DATA_DIR"

    # 生成启动脚本
    cat > "$HIVE_DIR/start.sh" <<STARTSH
#!/usr/bin/env bash
cd "$HIVE_DIR"
source .venv/bin/activate
export HIVE_DB_PATH="${DATA_DIR}/hive.db"
exec uvicorn greyfield_hive.main:app --host 0.0.0.0 --port ${PORT} "\$@"
STARTSH
    chmod +x "$HIVE_DIR/start.sh"

    echo ""
    info "✅ 安装完成！"
    info "   启动服务：./start.sh"
    info "   Dashboard：http://localhost:${PORT}"
    info "   API 文档：http://localhost:${PORT}/docs"
    info "   开发模式：uvicorn greyfield_hive.main:app --reload --port ${PORT}"
}

main() {
    print_banner

    MODE="${1:-}"

    # 自动检测模式
    if [[ -z "$MODE" ]]; then
        if command -v docker &>/dev/null; then
            warn "未指定模式，检测到 Docker，使用 --docker 模式"
            warn "如需本地安装，请运行：bash install.sh --local"
            echo ""
            MODE="--docker"
        else
            warn "未检测到 Docker，使用 --local 模式"
            MODE="--local"
        fi
    fi

    case "$MODE" in
        --docker)  install_docker ;;
        --local)   install_local ;;
        *)
            echo "用法：bash install.sh [--docker | --local]"
            echo ""
            echo "  --docker  使用 Docker Compose 启动（推荐生产环境）"
            echo "  --local   在本地 Python 环境安装（推荐开发环境）"
            exit 1
            ;;
    esac
}

main "$@"
