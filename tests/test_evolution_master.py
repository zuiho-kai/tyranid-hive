"""Evolution Master 自动经验萃取测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from greyfield_hive.main import app
from greyfield_hive.db import engine, Base, SessionLocal


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


@pytest.fixture
async def db_session():
    async with SessionLocal() as db:
        yield db


# ── 辅助 ──────────────────────────────────────────────────

async def _add_lessons(bank, domain, count, outcome="success"):
    """批量写入指定数量的 Lesson"""
    lessons = []
    for i in range(count):
        l = await bank.add(
            domain=domain,
            content=f"最佳实践 {i+1}：对 {domain} 领域任务使用策略 {i+1}",
            outcome=outcome,
            tags=[domain, f"tip{i+1}"],
        )
        lessons.append(l)
    return lessons


# ── EvolutionMasterService 单元测试 ──────────────────────

@pytest.mark.asyncio
async def test_evolve_domain_creates_playbook(db_session):
    """足够的成功经验时，evolve_domain 应创建新 Playbook"""
    from greyfield_hive.services.evolution_master import EvolutionMasterService
    from greyfield_hive.services.lessons_bank import LessonsBank

    bank = LessonsBank(db_session)
    await _add_lessons(bank, "coding", 5, outcome="success")

    svc = EvolutionMasterService(db_session)
    result = await svc.evolve_domain("coding")

    assert result is not None
    assert result.domain == "coding"
    assert result.lessons_used >= 5
    assert result.playbook_slug.startswith("evolved-coding")
    assert result.is_new is True


@pytest.mark.asyncio
async def test_evolve_domain_not_enough_lessons(db_session):
    """成功经验不足阈值时，evolve_domain 返回 None"""
    from greyfield_hive.services.evolution_master import EvolutionMasterService
    from greyfield_hive.services.lessons_bank import LessonsBank

    bank = LessonsBank(db_session)
    await _add_lessons(bank, "research", 3, outcome="success")

    svc = EvolutionMasterService(db_session)
    result = await svc.evolve_domain("research")

    assert result is None


@pytest.mark.asyncio
async def test_evolve_domain_ignores_failure_lessons(db_session):
    """失败经验不计入阈值"""
    from greyfield_hive.services.evolution_master import EvolutionMasterService
    from greyfield_hive.services.lessons_bank import LessonsBank

    bank = LessonsBank(db_session)
    # 4 failure + 1 success → 低于阈值
    await _add_lessons(bank, "ops", 4, outcome="failure")
    await _add_lessons(bank, "ops", 1, outcome="success")

    svc = EvolutionMasterService(db_session)
    result = await svc.evolve_domain("ops")

    assert result is None


@pytest.mark.asyncio
async def test_evolve_domain_updates_existing_playbook(db_session):
    """域已有 Playbook 时，应创建新版本而非重复创建"""
    from greyfield_hive.services.evolution_master import EvolutionMasterService
    from greyfield_hive.services.lessons_bank import LessonsBank
    from greyfield_hive.services.playbook_service import PlaybookService

    bank = LessonsBank(db_session)
    await _add_lessons(bank, "coding", 5)

    svc = EvolutionMasterService(db_session)
    result1 = await svc.evolve_domain("coding")
    assert result1 is not None
    assert result1.is_new is True

    # 再加 5 条新经验，再次进化
    await _add_lessons(bank, "coding", 5)
    result2 = await svc.evolve_domain("coding")

    assert result2 is not None
    assert result2.is_new is False           # 是更新，不是新建
    assert result2.playbook_version > result1.playbook_version


@pytest.mark.asyncio
async def test_evolve_domain_links_lessons_to_playbook(db_session):
    """提炼后，使用的 Lesson 应关联到生成的 Playbook"""
    from greyfield_hive.services.evolution_master import EvolutionMasterService
    from greyfield_hive.services.lessons_bank import LessonsBank

    bank = LessonsBank(db_session)
    lessons = await _add_lessons(bank, "coding", 5)

    svc = EvolutionMasterService(db_session)
    result = await svc.evolve_domain("coding")

    # 至少有部分 lesson 已关联 playbook
    linked = 0
    for l in lessons:
        refreshed = await bank.get(l.id)
        if refreshed and refreshed.playbook_id:
            linked += 1
    assert linked >= 1


@pytest.mark.asyncio
async def test_scan_and_evolve_multiple_domains(db_session):
    """scan_and_evolve 应处理多个达标域"""
    from greyfield_hive.services.evolution_master import EvolutionMasterService
    from greyfield_hive.services.lessons_bank import LessonsBank

    bank = LessonsBank(db_session)
    await _add_lessons(bank, "coding", 5)
    await _add_lessons(bank, "research", 5)
    await _add_lessons(bank, "ops", 2)  # 不足，不处理

    svc = EvolutionMasterService(db_session)
    results = await svc.scan_and_evolve()

    domains = {r.domain for r in results}
    assert "coding" in domains
    assert "research" in domains
    assert "ops" not in domains


@pytest.mark.asyncio
async def test_synthesize_content_contains_lessons(db_session):
    """合成的 Playbook content 应包含 lesson 内容摘要"""
    from greyfield_hive.services.evolution_master import EvolutionMasterService
    from greyfield_hive.services.lessons_bank import LessonsBank
    from greyfield_hive.services.playbook_service import PlaybookService

    bank = LessonsBank(db_session)
    await _add_lessons(bank, "coding", 5)

    svc = EvolutionMasterService(db_session)
    result = await svc.evolve_domain("coding")

    pb_svc = PlaybookService(db_session)
    pb = await pb_svc.get_by_id(result.playbook_id)
    assert len(pb.content) > 50
    # 内容应包含 Evolution Master 生成标记
    assert "Evolution" in pb.content or "最佳实践" in pb.content or "coding" in pb.content


# ── API 端点测试 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_evolve_domain(client):
    """POST /api/evolution/domain/{domain} 应触发进化并返回结果"""
    # 先通过 API 写入足够的 lessons
    for i in range(5):
        r = await client.post("/api/lessons", json={
            "domain": "coding",
            "content": f"编程最佳实践 {i+1}",
            "outcome": "success",
        })
        assert r.status_code == 201

    r = await client.post("/api/evolution/domain/coding")
    assert r.status_code == 200
    data = r.json()
    assert data["domain"] == "coding"
    assert data["lessons_used"] >= 5
    assert "playbook_slug" in data


@pytest.mark.asyncio
async def test_api_evolve_domain_not_enough(client):
    """经验不足时返回 204 No Content"""
    r = await client.post("/api/evolution/domain/empty-domain")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_api_scan_and_evolve(client):
    """POST /api/evolution/scan 应触发全域扫描"""
    # 写入两个域各 5 条
    for domain in ["coding", "research"]:
        for i in range(5):
            await client.post("/api/lessons", json={
                "domain": domain,
                "content": f"{domain} 经验 {i+1}",
                "outcome": "success",
            })

    r = await client.post("/api/evolution/scan")
    assert r.status_code == 200
    data = r.json()
    assert "evolved" in data
    assert isinstance(data["evolved"], list)
    assert len(data["evolved"]) >= 2


@pytest.mark.asyncio
async def test_api_get_evolution_status(client):
    """GET /api/evolution/status 返回各域 lesson 统计"""
    await client.post("/api/lessons", json={"domain": "coding", "content": "经验1", "outcome": "success"})

    r = await client.get("/api/evolution/status")
    assert r.status_code == 200
    data = r.json()
    assert "domains" in data
    # coding 域应该出现在 status 里
    domain_names = [d["domain"] for d in data["domains"]]
    assert "coding" in domain_names
