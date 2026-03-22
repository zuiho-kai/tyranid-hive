"""Tyranid Hive CLI —— hive 命令行管理工具

用法：
  hive health                    检查服务状态
  hive stats                     查看任务统计
  hive tasks list                列出任务
  hive tasks create --title "…"  创建任务
  hive tasks show BT-xxx         查看任务详情
  hive tasks transition BT-xxx Planning  流转状态
  hive tasks cancel BT-xxx       取消任务
  hive synapses                  列出小主脑
"""

from __future__ import annotations

import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import box

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

app = typer.Typer(
    name="hive",
    help="🧬 Tyranid Hive 虫巢管理工具",
    no_args_is_help=True,
)
tasks_app = typer.Typer(help="任务管理")
app.add_typer(tasks_app, name="tasks")

console = Console()
err_console = Console(stderr=True, style="bold red")

# ── 全局选项 ──────────────────────────────────────────────────────────

_API_URL: str = "http://localhost:8765"


def _api_url_callback(value: str) -> str:
    global _API_URL
    _API_URL = value.rstrip("/")
    return value


api_url_option = typer.Option(
    "http://localhost:8765",
    "--api", "-a",
    help="Hive API 地址",
    callback=_api_url_callback,
    is_eager=True,
)


# ── HTTP 客户端 ────────────────────────────────────────────────────────

def _get(path: str, params: dict | None = None) -> dict:
    if httpx is None:
        err_console.print("错误：需要安装 httpx。请执行：pip install httpx")
        raise typer.Exit(1)
    try:
        r = httpx.get(f"{_API_URL}{path}", params=params or {}, timeout=10)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        err_console.print(f"无法连接到 {_API_URL}，请确认 hive 服务已启动。")
        raise typer.Exit(1)
    except httpx.HTTPStatusError as e:
        err_console.print(f"API 错误 {e.response.status_code}：{e.response.text[:200]}")
        raise typer.Exit(1)


def _post(path: str, json: dict) -> dict:
    if httpx is None:
        err_console.print("错误：需要安装 httpx。请执行：pip install httpx")
        raise typer.Exit(1)
    try:
        r = httpx.post(f"{_API_URL}{path}", json=json, timeout=10)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        err_console.print(f"无法连接到 {_API_URL}，请确认 hive 服务已启动。")
        raise typer.Exit(1)
    except httpx.HTTPStatusError as e:
        err_console.print(f"API 错误 {e.response.status_code}：{e.response.text[:200]}")
        raise typer.Exit(1)


# ── 颜色映射 ────────────────────────────────────────────────────────────

_STATE_COLORS: dict[str, str] = {
    "Incubating":    "cyan",
    "Planning":      "blue",
    "Reviewing":     "yellow",
    "Spawning":      "magenta",
    "Executing":     "green",
    "Consolidating": "bright_cyan",
    "Complete":      "bright_green",
    "Cancelled":     "red",
    "Dormant":       "dim",
}

_PRIORITY_COLORS: dict[str, str] = {
    "critical": "bold red",
    "high":     "red",
    "normal":   "white",
    "low":      "dim",
}


def _state(s: str) -> str:
    color = _STATE_COLORS.get(s, "white")
    return f"[{color}]{s}[/{color}]"


def _priority(p: str) -> str:
    color = _PRIORITY_COLORS.get(p, "white")
    return f"[{color}]{p}[/{color}]"


# ── health ───────────────────────────────────────────────────────────

@app.command()
def health(
    api: str = api_url_option,
) -> None:
    """检查 Hive 服务健康状态"""
    data = _get("/health")
    status = data.get("status", "unknown")
    color = "green" if status == "synapse_active" else "yellow"

    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 1))
    table.add_column(style="dim")
    table.add_column()
    table.add_row("状态", f"[{color}]{status}[/{color}]")
    table.add_row("服务", data.get("service", "-"))
    table.add_row("版本", data.get("version", "-"))
    table.add_row("数据库", "[green]ok[/green]" if data.get("db") == "ok" else "[red]error[/red]")
    table.add_row("Workers", "[green]ok[/green]" if data.get("workers") == "ok" else "[yellow]stopped[/yellow]")
    console.print(table)


# ── stats ────────────────────────────────────────────────────────────

@app.command()
def stats(
    api: str = api_url_option,
) -> None:
    """查看任务统计"""
    data = _get("/api/tasks/stats")

    table = Table(title="任务统计", box=box.ROUNDED)
    table.add_column("指标", style="dim")
    table.add_column("数值", justify="right")

    table.add_row("总计", str(data.get("total", 0)))
    table.add_row("[green]活跃[/green]", str(data.get("active", 0)))
    table.add_row("[bright_green]完成[/bright_green]", str(data.get("complete", 0)))
    table.add_row("[red]取消[/red]", str(data.get("cancelled", 0)))
    console.print(table)

    by_state: dict = data.get("by_state", {})
    if by_state:
        t2 = Table(title="各状态分布", box=box.SIMPLE)
        t2.add_column("状态")
        t2.add_column("数量", justify="right")
        for state_name, count in sorted(by_state.items()):
            t2.add_row(_state(state_name), str(count))
        console.print(t2)


# ── tasks ────────────────────────────────────────────────────────────

@tasks_app.command("list", help="列出任务")
def tasks_list(
    state:    Optional[str] = typer.Option(None, "--state",    "-s", help="按状态过滤"),
    priority: Optional[str] = typer.Option(None, "--priority", "-p", help="按优先级过滤"),
    search:   Optional[str] = typer.Option(None, "--search",   "-q", help="关键词搜索（title/description/id）"),
    sort_by:  str            = typer.Option("updated_at", "--sort-by", help="排序字段: updated_at/created_at/priority/state"),
    order:    str            = typer.Option("desc", "--order", "-o", help="排序方向: asc/desc"),
    limit:    int            = typer.Option(20,  "--limit",    "-n", help="最多显示条数"),
    api:      str            = api_url_option,
) -> None:
    """列出任务列表"""
    params: dict = {"limit": limit, "sort_by": sort_by, "order": order}
    if state:
        params["state"] = state
    if priority:
        params["priority"] = priority
    if search:
        params["q"] = search

    tasks = _get("/api/tasks", params=params)
    if not tasks:
        console.print("[dim]没有匹配的任务[/dim]")
        return

    table = Table(box=box.ROUNDED)
    table.add_column("ID",       style="bold")
    table.add_column("标题",     max_width=40)
    table.add_column("状态",     no_wrap=True)
    table.add_column("优先级",   no_wrap=True)
    table.add_column("执行者",   style="dim")
    table.add_column("更新时间", style="dim")

    for t in tasks:
        updated = (t.get("updated_at") or "")[:16].replace("T", " ")
        table.add_row(
            t["id"],
            t.get("title", ""),
            _state(t.get("state", "")),
            _priority(t.get("priority", "normal")),
            t.get("assignee_synapse") or "-",
            updated,
        )

    console.print(table)
    console.print(f"[dim]共 {len(tasks)} 条[/dim]")


@tasks_app.command("show", help="查看任务详情")
def tasks_show(
    task_id: str = typer.Argument(..., help="任务 ID，如 BT-20240101-ABCDEF"),
    api:     str = api_url_option,
) -> None:
    """查看单个任务详情"""
    t = _get(f"/api/tasks/{task_id}")

    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 1))
    table.add_column(style="bold dim", no_wrap=True)
    table.add_column()

    table.add_row("ID",      t["id"])
    table.add_row("标题",    t.get("title", ""))
    table.add_row("描述",    t.get("description", "") or "[dim]（空）[/dim]")
    table.add_row("状态",    _state(t.get("state", "")))
    table.add_row("优先级",  _priority(t.get("priority", "normal")))
    table.add_row("执行者",  t.get("assignee_synapse") or "-")
    table.add_row("创建者",  t.get("creator", ""))
    table.add_row("创建时间", (t.get("created_at") or "")[:19].replace("T", " "))
    table.add_row("更新时间", (t.get("updated_at") or "")[:19].replace("T", " "))
    console.print(table)

    # 进度日志
    prog = t.get("progress_log") or []
    if prog:
        console.print("\n[bold]进度日志[/bold]")
        for entry in prog[-5:]:  # 最近 5 条
            ts = (entry.get("ts") or "")[:16].replace("T", " ")
            console.print(f"  [{ts}] [dim]{entry.get('agent', '')}[/dim]: {entry.get('content', '')}")

    # Todos
    todos = t.get("todos") or []
    if todos:
        console.print("\n[bold]待办清单[/bold]")
        for td in todos:
            mark = "[green]✓[/green]" if td.get("done") else "[ ]"
            console.print(f"  {mark} {td.get('title', '')}")

    # 流转记录
    flow = t.get("flow_log") or []
    if flow:
        console.print("\n[bold]状态历史[/bold]")
        for entry in flow:
            ts = (entry.get("ts") or "")[:16].replace("T", " ")
            frm = entry.get("from") or "—"
            to  = entry.get("to", "")
            console.print(f"  [{ts}] {_state(frm)} → {_state(to)}  [dim]{entry.get('agent', '')}[/dim]")


@tasks_app.command("create", help="创建新任务")
def tasks_create(
    title:       str           = typer.Option(..., "--title",    "-t", help="任务标题"),
    description: str           = typer.Option("",  "--desc",    "-d", help="任务描述"),
    priority:    str           = typer.Option("normal", "--priority", "-p",
                                              help="优先级：critical/high/normal/low"),
    api:         str           = api_url_option,
) -> None:
    """创建新战团任务"""
    payload = {"title": title, "description": description, "priority": priority}
    task = _post("/api/tasks", json=payload)
    console.print(f"[green]✓[/green] 战团已孵化：[bold]{task['id']}[/bold]")
    console.print(f"  标题：{task['title']}")
    console.print(f"  状态：{_state(task['state'])}")


@tasks_app.command("transition", help="流转任务状态")
def tasks_transition(
    task_id:   str = typer.Argument(..., help="任务 ID"),
    new_state: str = typer.Argument(..., help="目标状态"),
    reason:    str = typer.Option("", "--reason", "-r", help="流转原因"),
    api:       str = api_url_option,
) -> None:
    """手动流转任务状态"""
    payload = {"new_state": new_state, "agent": "cli", "reason": reason}
    task = _post(f"/api/tasks/{task_id}/transition", json=payload)
    console.print(f"[green]✓[/green] {task_id} → {_state(task['state'])}")


@tasks_app.command("patch", help="部分更新任务字段")
def tasks_patch(
    task_id:     str            = typer.Argument(..., help="任务 ID"),
    title:       Optional[str]  = typer.Option(None, "--title",       "-t", help="新标题"),
    description: Optional[str]  = typer.Option(None, "--description", "--desc", "-d", help="新描述"),
    priority:    Optional[str]  = typer.Option(None, "--priority",    "-p", help="新优先级"),
    api:         str            = api_url_option,
) -> None:
    """部分更新任务字段（title / description / priority）"""
    payload: dict = {}
    if title is not None:
        payload["title"] = title
    if description is not None:
        payload["description"] = description
    if priority is not None:
        payload["priority"] = priority
    if not payload:
        err_console.print("错误：请至少指定一个要更新的字段（--title / --description / --priority）")
        raise typer.Exit(2)
    if httpx is None:
        err_console.print("错误：需要安装 httpx。请执行：pip install httpx")
        raise typer.Exit(1)
    try:
        r = httpx.patch(f"{_API_URL}/api/tasks/{task_id}", json=payload, timeout=10)
        r.raise_for_status()
        task = r.json()
        console.print(f"[green]✓[/green] 任务 [bold]{task_id}[/bold] 已更新")
        for k, v in payload.items():
            console.print(f"  {k}: {v}")
    except httpx.ConnectError:
        err_console.print(f"无法连接到 {_API_URL}，请确认 hive 服务已启动。")
        raise typer.Exit(1)
    except httpx.HTTPStatusError as e:
        err_console.print(f"API 错误 {e.response.status_code}：{e.response.text[:200]}")
        raise typer.Exit(1)


@tasks_app.command("delete", help="删除任务（硬删除）")
def tasks_delete(
    task_id: str = typer.Argument(..., help="任务 ID"),
    yes:     bool = typer.Option(False, "--yes", "-y", help="跳过确认"),
    api:     str  = api_url_option,
) -> None:
    """硬删除单个任务"""
    if not yes:
        typer.confirm(f"确认删除任务 {task_id}？此操作不可撤销", abort=True)
    if httpx is None:
        err_console.print("错误：需要安装 httpx。请执行：pip install httpx")
        raise typer.Exit(1)
    try:
        r = httpx.delete(f"{_API_URL}/api/tasks/{task_id}", timeout=10)
        if r.status_code == 204:
            console.print(f"[green]✓[/green] 任务 [bold]{task_id}[/bold] 已删除")
        elif r.status_code == 404:
            err_console.print(f"任务不存在：{task_id}")
            raise typer.Exit(1)
        else:
            r.raise_for_status()
    except httpx.ConnectError:
        err_console.print(f"无法连接到 {_API_URL}，请确认 hive 服务已启动。")
        raise typer.Exit(1)


@tasks_app.command("cleanup", help="清理旧的已完成/已取消任务")
def tasks_cleanup(
    days: int = typer.Option(30, "--days", "-d", help="删除 N 天前的完成/取消任务"),
    yes:  bool = typer.Option(False, "--yes", "-y", help="跳过确认"),
    api:  str  = api_url_option,
) -> None:
    """清理 N 天前已完成/已取消的任务"""
    if not yes:
        typer.confirm(f"确认删除 {days} 天前已完成/取消的任务？", abort=True)
    if httpx is None:
        err_console.print("错误：需要安装 httpx。请执行：pip install httpx")
        raise typer.Exit(1)
    try:
        r = httpx.delete(f"{_API_URL}/api/tasks/cleanup", params={"days": days}, timeout=10)
        r.raise_for_status()
        data = r.json()
        count = data.get("deleted", 0)
        console.print(f"[green]✓[/green] 已清理 [bold]{count}[/bold] 条任务")
    except httpx.ConnectError:
        err_console.print(f"无法连接到 {_API_URL}，请确认 hive 服务已启动。")
        raise typer.Exit(1)
    except httpx.HTTPStatusError as e:
        err_console.print(f"API 错误 {e.response.status_code}：{e.response.text[:200]}")
        raise typer.Exit(1)


@tasks_app.command("cancel", help="取消任务")
def tasks_cancel(
    task_id: str = typer.Argument(..., help="任务 ID"),
    reason:  str = typer.Option("用户取消", "--reason", "-r"),
    api:     str = api_url_option,
) -> None:
    """取消任务（流转到 Cancelled 状态）"""
    payload = {"new_state": "Cancelled", "agent": "cli", "reason": reason}
    task = _post(f"/api/tasks/{task_id}/transition", json=payload)
    console.print(f"[yellow]✓[/yellow] {task_id} 已取消（{_state(task['state'])}）")


# ── synapses ─────────────────────────────────────────────────────────

@app.command()
def synapses(
    api: str = api_url_option,
) -> None:
    """列出所有小主脑"""
    data = _get("/api/synapses")

    table = Table(title="小主脑列表", box=box.ROUNDED)
    table.add_column("ID",  style="bold")
    table.add_column("",    no_wrap=True)   # emoji
    table.add_column("名称")
    table.add_column("Tier", justify="center")
    table.add_column("职责", style="dim")

    _TIER_COLORS = {1: "bold red", 2: "orange3", 3: "yellow", 4: "green", 5: "cyan"}
    for s in data:
        tier = s.get("tier", 0)
        tier_str = f"[{_TIER_COLORS.get(tier, 'white')}]T{tier}[/{_TIER_COLORS.get(tier, 'white')}]"
        table.add_row(
            s.get("id", ""),
            s.get("emoji", ""),
            s.get("name", ""),
            tier_str,
            s.get("role", ""),
        )

    console.print(table)


# ── 入口 ──────────────────────────────────────────────────────────────

def main() -> None:
    app()


if __name__ == "__main__":
    main()
