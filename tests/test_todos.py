"""Todo 精细化操作测试 —— POST /api/tasks/{id}/todos, PATCH /api/tasks/{id}/todos/{index}"""

import pytest
from httpx import AsyncClient, ASGITransport

from greyfield_hive.main import app
from greyfield_hive.db import engine, Base


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


async def _create(client, title: str = "测试任务") -> dict:
    r = await client.post("/api/tasks", json={"title": title})
    assert r.status_code == 201
    return r.json()


# ── 追加 Todo ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_append_todo_returns_201(client):
    """追加 todo 返回 201"""
    task = await _create(client)
    r = await client.post(f"/api/tasks/{task['id']}/todos", json={"title": "子任务A"})
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_append_todo_appears_in_list(client):
    """追加后 todo 出现在任务的 todos 列表中"""
    task = await _create(client)
    r = await client.post(f"/api/tasks/{task['id']}/todos", json={"title": "子任务A"})
    todos = r.json()["todos"]
    assert len(todos) == 1
    assert todos[0]["title"] == "子任务A"
    assert todos[0]["done"] is False


@pytest.mark.asyncio
async def test_append_multiple_todos_accumulates(client):
    """多次追加不覆盖，累计增长"""
    task = await _create(client)
    await client.post(f"/api/tasks/{task['id']}/todos", json={"title": "子任务A"})
    r = await client.post(f"/api/tasks/{task['id']}/todos", json={"title": "子任务B"})
    todos = r.json()["todos"]
    assert len(todos) == 2
    titles = [t["title"] for t in todos]
    assert "子任务A" in titles
    assert "子任务B" in titles


@pytest.mark.asyncio
async def test_append_does_not_touch_existing_todos(client):
    """追加单条不会替换通过 PUT 设置的已有 todos"""
    task = await _create(client)
    await client.put(f"/api/tasks/{task['id']}/todos", json={"todos": [
        {"title": "已有任务1", "done": True},
        {"title": "已有任务2", "done": False},
    ]})
    r = await client.post(f"/api/tasks/{task['id']}/todos", json={"title": "新追加"})
    todos = r.json()["todos"]
    assert len(todos) == 3
    assert todos[0]["done"] is True   # 已有任务1 状态保持
    assert todos[2]["title"] == "新追加"


@pytest.mark.asyncio
async def test_append_todo_auto_assigns_id(client):
    """每个 todo 被追加时自动分配 UUID"""
    task = await _create(client)
    r = await client.post(f"/api/tasks/{task['id']}/todos", json={"title": "带ID的任务"})
    todo = r.json()["todos"][0]
    assert todo.get("id") is not None
    assert len(todo["id"]) > 0


@pytest.mark.asyncio
async def test_append_todo_task_not_found(client):
    """任务不存在时追加返回 404"""
    r = await client.post("/api/tasks/BT-不存在-ZZZZZZ/todos", json={"title": "x"})
    assert r.status_code == 404


# ── 切换 Todo 完成状态 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_toggle_todo_marks_done(client):
    """切换未完成的 todo 变为完成"""
    task = await _create(client)
    await client.post(f"/api/tasks/{task['id']}/todos", json={"title": "待完成"})
    r = await client.patch(f"/api/tasks/{task['id']}/todos/0")
    assert r.status_code == 200
    assert r.json()["todos"][0]["done"] is True


@pytest.mark.asyncio
async def test_toggle_todo_marks_undone(client):
    """再次切换已完成的 todo 变回未完成"""
    task = await _create(client)
    await client.post(f"/api/tasks/{task['id']}/todos", json={"title": "待完成"})
    await client.patch(f"/api/tasks/{task['id']}/todos/0")   # → done
    r = await client.patch(f"/api/tasks/{task['id']}/todos/0")  # → undone
    assert r.status_code == 200
    assert r.json()["todos"][0]["done"] is False


@pytest.mark.asyncio
async def test_toggle_correct_index(client):
    """只切换指定索引的 todo，其他不受影响"""
    task = await _create(client)
    await client.post(f"/api/tasks/{task['id']}/todos", json={"title": "A"})
    await client.post(f"/api/tasks/{task['id']}/todos", json={"title": "B"})
    await client.post(f"/api/tasks/{task['id']}/todos", json={"title": "C"})
    r = await client.patch(f"/api/tasks/{task['id']}/todos/1")  # toggle B
    todos = r.json()["todos"]
    assert todos[0]["done"] is False  # A 不变
    assert todos[1]["done"] is True   # B 被切换
    assert todos[2]["done"] is False  # C 不变


@pytest.mark.asyncio
async def test_toggle_out_of_bounds_returns_422(client):
    """索引越界返回 422"""
    task = await _create(client)
    await client.post(f"/api/tasks/{task['id']}/todos", json={"title": "只有一条"})
    r = await client.patch(f"/api/tasks/{task['id']}/todos/5")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_toggle_empty_todos_returns_422(client):
    """空 todo 列表时切换返回 422"""
    task = await _create(client)
    r = await client.patch(f"/api/tasks/{task['id']}/todos/0")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_toggle_todo_task_not_found(client):
    """任务不存在时切换返回 404"""
    r = await client.patch("/api/tasks/BT-不存在-ZZZZZZ/todos/0")
    assert r.status_code == 404
