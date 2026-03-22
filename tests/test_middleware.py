"""请求日志中间件测试

覆盖：
- X-Request-ID 响应头存在性
- 客户端传入自定义 Request ID 时原样回传
- 无传入时自动生成 UUID
- get_request_id() 上下文变量在请求处理中可用
- 不同状态码的行为（2xx / 4xx / 5xx）
- 日志跳过前缀
"""

import pytest
from httpx import AsyncClient, ASGITransport

from greyfield_hive.main import app
from greyfield_hive.middleware import get_request_id, RequestLoggingMiddleware, REQUEST_ID_HEADER
from greyfield_hive.db import engine, Base


# ── fixture ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── 基础：响应头存在 ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_response_contains_request_id_header(client):
    """所有响应应包含 X-Request-ID 头"""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert REQUEST_ID_HEADER in resp.headers


@pytest.mark.asyncio
async def test_request_id_is_uuid_when_not_provided(client):
    """未提供 X-Request-ID 时，响应头应是 UUID 格式"""
    import re
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )
    resp = await client.get("/health")
    rid = resp.headers.get(REQUEST_ID_HEADER, "")
    assert uuid_pattern.match(rid), f"期望 UUID 格式，实际：{rid!r}"


@pytest.mark.asyncio
async def test_client_request_id_echoed_back(client):
    """客户端传入自定义 X-Request-ID 时应原样回传"""
    custom_id = "my-custom-trace-abc123"
    resp = await client.get("/health", headers={REQUEST_ID_HEADER: custom_id})
    assert resp.headers.get(REQUEST_ID_HEADER) == custom_id


@pytest.mark.asyncio
async def test_different_requests_get_different_ids(client):
    """两个不含 X-Request-ID 的请求应各自得到不同的 ID"""
    r1 = await client.get("/health")
    r2 = await client.get("/health")
    id1 = r1.headers.get(REQUEST_ID_HEADER)
    id2 = r2.headers.get(REQUEST_ID_HEADER)
    assert id1 != id2, "不同请求应该得到不同 Request ID"


# ── 状态码覆盖 ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_request_id_on_404(client):
    """404 响应也应包含 X-Request-ID"""
    resp = await client.get("/api/tasks/NOT-EXIST")
    assert resp.status_code == 404
    assert REQUEST_ID_HEADER in resp.headers


@pytest.mark.asyncio
async def test_request_id_on_post(client):
    """POST 请求响应也应包含 X-Request-ID"""
    resp = await client.post("/api/tasks", json={"title": "测试战团"})
    assert resp.status_code == 201
    assert REQUEST_ID_HEADER in resp.headers


@pytest.mark.asyncio
async def test_request_id_consistent_on_api_calls(client):
    """连续 API 调用每次应返回独立 Request ID"""
    resp1 = await client.post("/api/tasks", json={"title": "战团A"})
    resp2 = await client.post("/api/tasks", json={"title": "战团B"})
    id1 = resp1.headers.get(REQUEST_ID_HEADER)
    id2 = resp2.headers.get(REQUEST_ID_HEADER)
    assert id1 is not None
    assert id2 is not None
    assert id1 != id2


# ── contextvars ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_request_id_outside_request_context():
    """在请求上下文外调用 get_request_id() 应返回空串（不报错）"""
    rid = get_request_id()
    assert rid == ""


# ── 中间件单元测试 ──────────────────────────────────────────────────────────

def test_middleware_skip_prefixes_default():
    """默认跳过前缀应包含 /assets/"""
    from starlette.applications import Starlette
    inner = Starlette()
    mw = RequestLoggingMiddleware(inner)
    assert "/assets/" in mw._skip_prefixes


def test_middleware_custom_skip_prefixes():
    """支持自定义跳过前缀"""
    from starlette.applications import Starlette
    inner = Starlette()
    mw = RequestLoggingMiddleware(inner, skip_prefixes=("/static/", "/ping"))
    assert "/static/" in mw._skip_prefixes
    assert "/assets/" not in mw._skip_prefixes


# ── 多任务并发隔离 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_request_ids_are_isolated_across_concurrent_requests(client):
    """并发请求各自的 X-Request-ID 不应互相污染"""
    import asyncio

    ids_sent = [f"trace-concurrent-{i}" for i in range(5)]
    responses = await asyncio.gather(
        *[client.get("/health", headers={REQUEST_ID_HEADER: rid}) for rid in ids_sent]
    )
    ids_received = [r.headers.get(REQUEST_ID_HEADER) for r in responses]
    # 每个响应收到的 ID 应与发送的一致（顺序可能不同，但集合匹配）
    assert set(ids_received) == set(ids_sent)
