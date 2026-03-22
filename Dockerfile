# ── 构建阶段：编译前端 ────────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /app/dashboard
COPY dashboard/package*.json ./
RUN npm ci --silent

COPY dashboard/ .
RUN npm run build


# ── 运行阶段：Python 后端 ─────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 先安装依赖（利用 Docker 层缓存）
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    pydantic loguru pyyaml aiofiles typing-extensions \
    "fastapi>=0.104.0" "uvicorn[standard]>=0.24.0" "websockets>=12.0" \
    "sqlalchemy[asyncio]>=2.0.0" "aiosqlite>=0.19.0" \
    "httpx>=0.27.0"

# 复制源码并安装包（非 editable，避免需要整个 venv）
COPY src/ src/
COPY config/ config/
RUN pip install --no-cache-dir --no-deps -e .

# 从构建阶段复制前端产物
COPY --from=frontend-builder /app/src/greyfield_hive/static src/greyfield_hive/static

# 数据目录
RUN mkdir -p /data
ENV HIVE_DB_PATH=/data/hive.db

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8765/health || exit 1

CMD ["uvicorn", "greyfield_hive.main:app", "--host", "0.0.0.0", "--port", "8765"]
