"""Playbook 使用统计闭环测试 —— record_use + 自动更新"""

import pytest
from greyfield_hive.db import engine, Base, SessionLocal
from greyfield_hive.services.playbook_service import PlaybookService


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.mark.asyncio
async def test_record_use_increments_count():
    """record_use 应递增 use_count"""
    async with SessionLocal() as db:
        svc = PlaybookService(db)
        pb = await svc.create(
            slug="test-pb", domain="coding",
            title="测试手册", content="操作步骤"
        )
        await db.commit()
        pb_id = pb.id

    async with SessionLocal() as db:
        svc = PlaybookService(db)
        await svc.record_usage(pb_id, success=True)
        await db.commit()

    async with SessionLocal() as db:
        svc = PlaybookService(db)
        pb = await svc.get_by_id(pb_id)

    assert pb.use_count == 1
    assert pb.success_rate > 0


@pytest.mark.asyncio
async def test_record_use_failure_lowers_success_rate():
    """失败调用应降低 success_rate"""
    async with SessionLocal() as db:
        svc = PlaybookService(db)
        pb = await svc.create(
            slug="fail-pb", domain="research",
            title="失败手册", content="..."
        )
        await db.commit()
        pb_id = pb.id

    async with SessionLocal() as db:
        svc = PlaybookService(db)
        # 先设一次成功
        await svc.record_usage(pb_id, success=True)
        await db.commit()

    async with SessionLocal() as db:
        svc = PlaybookService(db)
        # 再两次失败
        await svc.record_usage(pb_id, success=False)
        await svc.record_usage(pb_id, success=False)
        await db.commit()

    async with SessionLocal() as db:
        svc = PlaybookService(db)
        pb = await svc.get_by_id(pb_id)

    assert pb.use_count == 3
    assert pb.success_rate < 0.5


@pytest.mark.asyncio
async def test_dispatcher_calls_update_playbook_stats():
    """_update_playbook_stats 对匹配 domain 的 playbook 更新统计"""
    from greyfield_hive.workers.dispatcher import DispatchWorker
    from greyfield_hive.adapters.openclaw import MockAdapter

    # 先插入一个 playbook
    async with SessionLocal() as db:
        svc = PlaybookService(db)
        pb = await svc.create(
            slug="coding-guide", domain="coding",
            title="编码指南", content="最佳实践"
        )
        await db.commit()
        pb_id = pb.id

    # 直接调用 _update_playbook_stats（不走完整 dispatch 流程）
    worker = DispatchWorker()
    worker._adapter = MockAdapter()
    await worker._update_playbook_stats(
        domain="coding",
        tags=["代码", "实现", "测试"],
        success=True,
    )

    async with SessionLocal() as db:
        svc = PlaybookService(db)
        pb = await svc.get_by_id(pb_id)

    assert pb.use_count >= 1
    assert pb.success_rate > 0
