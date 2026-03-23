#!/usr/bin/env python3
"""Tyranid Hive Demo —— 端到端演示 Solo / Trial / Chain 三种执行模式

用法：
  python demo/run_demo.py [--mode solo|trial|chain|all] [--base-url URL]

环境变量（必须设置）：
  HIVE_API_URL   Hive 服务地址，默认 http://localhost:8765
  ANTHROPIC_API_KEY  LLM API Key（由 Hive 服务读取，demo 本身不直接使用）
"""

import argparse
import asyncio
import os
import sys
import time

import httpx

BASE_URL = os.getenv("HIVE_API_URL", "http://localhost:8765")


def check_env() -> None:
    """检查必要环境变量"""
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ 缺少环境变量 ANTHROPIC_API_KEY")
        print("   请先执行: export ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)


async def wait_for_server(client: httpx.AsyncClient, timeout: int = 10) -> None:
    """等待 Hive 服务就绪"""
    for _ in range(timeout):
        try:
            r = await client.get(f"{BASE_URL}/health")
            if r.status_code == 200:
                print(f"✅ Hive 服务就绪: {BASE_URL}")
                return
        except Exception:
            pass
        await asyncio.sleep(1)
    print(f"❌ Hive 服务未响应: {BASE_URL}")
    print("   请先启动服务: python -m greyfield_hive.main")
    sys.exit(1)


async def create_task(client: httpx.AsyncClient, title: str, description: str,
                      meta: dict | None = None) -> dict:
    r = await client.post(f"{BASE_URL}/api/tasks", json={
        "title": title,
        "description": description,
        "priority": "normal",
        "creator": "demo",
        "meta": meta or {},
    })
    r.raise_for_status()
    return r.json()


async def demo_solo(client: httpx.AsyncClient) -> None:
    print("\n── Solo Mode Demo ──────────────────────────────")
    task = await create_task(
        client,
        title="分析 Python 列表推导式的性能",
        description="对比 for 循环和列表推导式在不同数据量下的性能差异，给出建议",
    )
    task_id = task["id"]
    print(f"✅ 任务创建: {task_id}")

    r = await client.post(f"{BASE_URL}/api/tasks/{task_id}/dispatch", json={
        "synapse": "code-expert",
        "message": task["description"],
    })
    r.raise_for_status()
    print(f"✅ Solo 派发完成，synapse=code-expert")
    print(f"   查看结果: GET {BASE_URL}/api/tasks/{task_id}")


async def demo_trial(client: httpx.AsyncClient) -> None:
    print("\n── Trial Mode Demo ─────────────────────────────")
    task = await create_task(
        client,
        title="实现一个高效的字符串去重函数",
        description="用 Python 实现字符串去重，保持原始顺序，要求时间复杂度 O(n)",
    )
    task_id = task["id"]
    print(f"✅ 任务创建: {task_id}")

    r = await client.post(f"{BASE_URL}/api/tasks/{task_id}/trial", json={
        "synapses": ["code-expert", "research-analyst"],
        "message": task["description"],
        "domain": "coding",
    })
    r.raise_for_status()
    result = r.json()
    winner = result.get("winner", "未知")
    print(f"✅ Trial 完成，胜者={winner}")
    print(f"   查看结果: GET {BASE_URL}/api/tasks/{task_id}")


async def demo_chain(client: httpx.AsyncClient) -> None:
    print("\n── Chain Mode Demo ─────────────────────────────")
    task = await create_task(
        client,
        title="代码审查 + 优化建议",
        description="第一阶段：审查代码质量；第二阶段：基于审查结果给出优化方案",
    )
    task_id = task["id"]
    print(f"✅ 任务创建: {task_id}")

    r = await client.post(f"{BASE_URL}/api/tasks/{task_id}/chain", json={
        "synapses": ["code-expert", "research-analyst"],
        "message": task["description"],
        "domain": "coding",
    })
    r.raise_for_status()
    print(f"✅ Chain 完成，stages=2")
    print(f"   查看结果: GET {BASE_URL}/api/tasks/{task_id}")


async def main(mode: str) -> None:
    check_env()
    async with httpx.AsyncClient(timeout=60.0) as client:
        await wait_for_server(client)
        if mode in ("solo", "all"):
            await demo_solo(client)
        if mode in ("trial", "all"):
            await demo_trial(client)
        if mode in ("chain", "all"):
            await demo_chain(client)
    print("\n✅ Demo 完成")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tyranid Hive Demo")
    parser.add_argument("--mode", choices=["solo", "trial", "chain", "all"],
                        default="all", help="演示模式（默认 all）")
    parser.add_argument("--base-url", default=None, help="Hive API 地址")
    args = parser.parse_args()
    if args.base_url:
        BASE_URL = args.base_url
    asyncio.run(main(args.mode))
