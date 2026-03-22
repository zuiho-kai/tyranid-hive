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

# 先复制 pyproject.toml，安装所有运行时依赖（利用 Docker 层缓存）
# 使用占位 src/ 让 pip 能解析 [project] 元数据
COPY pyproject.toml ./
RUN mkdir -p src/greyfield_hive && touch src/greyfield_hive/__init__.py && \
    pip install --no-cache-dir -e ".[server]" && \
    rm -rf src/greyfield_hive

# 复制源码，完成最终安装
COPY src/ src/

# 配置文件 + 基因库（运行时读取）
COPY config/     config/
COPY genes/      genes/
COPY alembic.ini alembic.ini
COPY migrations/ migrations/

# 安装包本体（不重新安装依赖，利用上层缓存）
RUN pip install --no-cache-dir --no-deps -e .

# 从构建阶段复制前端产物（覆盖 src/ 中的 static/）
COPY --from=frontend-builder /app/src/greyfield_hive/static src/greyfield_hive/static

# 数据目录
RUN mkdir -p /data
ENV HIVE_DB_PATH=/data/hive.db

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8765/health || exit 1

CMD ["uvicorn", "greyfield_hive.main:app", "--host", "0.0.0.0", "--port", "8765"]
