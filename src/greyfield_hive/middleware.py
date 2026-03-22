"""请求日志中间件 —— X-Request-ID 传播 + 结构化访问日志

功能：
- 为每个请求生成/读取 X-Request-ID（UUID）
- 通过 contextvars 传播，供业务代码使用
- 记录：method path status_code duration_ms request_id
- 响应头写回 X-Request-ID
"""

from __future__ import annotations

import time
import uuid
from contextvars import ContextVar, Token

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# ── 上下文变量 ───────────────────────────────────────────────────────────

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """获取当前请求的 Request ID（无请求上下文时返回空串）"""
    return _request_id_var.get()


def _set_request_id(rid: str) -> Token:
    return _request_id_var.set(rid)


# ── 中间件 ───────────────────────────────────────────────────────────────

REQUEST_ID_HEADER = "X-Request-ID"

# 不记录日志的路径前缀（静态资源、健康检查可选跳过）
_SKIP_PREFIXES: tuple[str, ...] = ("/assets/",)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    结构化请求日志 + X-Request-ID 传播中间件

    行为：
    1. 读取请求头 X-Request-ID；若无则自动生成 UUID
    2. 设置 contextvars，供下游代码通过 get_request_id() 获取
    3. 处理完成后将 X-Request-ID 写入响应头
    4. 以结构化格式记录访问日志（INFO 成功，WARNING 4xx，ERROR 5xx）
    """

    def __init__(self, app: ASGIApp, skip_prefixes: tuple[str, ...] = _SKIP_PREFIXES) -> None:
        super().__init__(app)
        self._skip_prefixes = skip_prefixes

    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. 生成/读取 Request ID
        rid = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        token = _set_request_id(rid)

        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            _log(request, 500, duration_ms, rid)
            raise exc
        finally:
            _request_id_var.reset(token)

        duration_ms = int((time.monotonic() - start) * 1000)

        # 2. 写回响应头
        response.headers[REQUEST_ID_HEADER] = rid

        # 3. 记录日志
        path = request.url.path
        if not any(path.startswith(p) for p in self._skip_prefixes):
            _log(request, response.status_code, duration_ms, rid)

        return response


def _log(request: Request, status_code: int, duration_ms: int, rid: str) -> None:
    msg = (
        f"{request.method} {request.url.path}"
        f" → {status_code}"
        f" [{duration_ms}ms]"
        f" rid={rid[:8]}"
    )
    if status_code >= 500:
        logger.error(msg)
    elif status_code >= 400:
        logger.warning(msg)
    else:
        logger.info(msg)
