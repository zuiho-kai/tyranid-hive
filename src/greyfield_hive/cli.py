"""Tyranid Hive CLI —— hive 命令行管理工具

用法：
  hive health                         检查服务状态
  hive stats                          查看任务统计
  hive tasks list                     列出任务
  hive tasks create --title "…"       创建任务
  hive tasks show BT-xxx              查看任务详情
  hive tasks transition BT-xxx …      流转状态
  hive tasks cancel BT-xxx            取消任务
  hive tasks children BT-xxx          列出子任务
  hive tasks dispatch BT-xxx --synapse=code-expert  派发任务
  hive tasks subtask BT-xxx --title "…"             创建子任务
  hive tasks blocked BT-xxx           检查依赖阻塞状态
  hive synapses                       列出小主脑
  hive fitness leaderboard            适存度排行榜
  hive fitness show <synapse_id>      小主脑适存度详情
  hive lessons list                   列出经验教训
  hive lessons add --domain … --content …  添加经验
  hive lessons search <domain>        搜索经验
  hive lessons bump <id>              增加命中计数
  hive lessons delete <id>            删除经验
  hive playbooks list                 列出作战手册
  hive playbooks show <slug>          查看手册内容
  hive playbooks add --slug … --title …  创建手册
  hive playbooks search <domain>      搜索手册
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
tasks_app     = typer.Typer(help="任务管理")
fitness_app   = typer.Typer(help="适存度排行榜")
lessons_app   = typer.Typer(help="经验教训基因库")
playbooks_app = typer.Typer(help="作战手册管理")
genes_app     = typer.Typer(help="基因库整体导出/导入")
app.add_typer(tasks_app,     name="tasks")
app.add_typer(fitness_app,   name="fitness")
app.add_typer(lessons_app,   name="lessons")
app.add_typer(playbooks_app, name="playbooks")
app.add_typer(genes_app,     name="genes")

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


@tasks_app.command("children", help="列出任务的所有直接子任务")
def tasks_children(
    task_id: str = typer.Argument(..., help="父任务 ID"),
    api:     str = api_url_option,
) -> None:
    """列出父任务下的所有子任务"""
    if httpx is None:
        err_console.print("错误：需要安装 httpx。请执行：pip install httpx")
        raise typer.Exit(1)
    try:
        r = httpx.get(f"{_API_URL}/api/tasks/{task_id}/children", timeout=10)
        if r.status_code == 404:
            err_console.print(f"任务不存在：{task_id}")
            raise typer.Exit(1)
        r.raise_for_status()
        tasks = r.json()
        if not tasks:
            console.print(f"[yellow]任务 {task_id} 暂无子任务[/yellow]")
            return
        table = Table(title=f"子任务列表（父：{task_id}）", show_header=True, header_style="bold cyan")
        table.add_column("ID",       style="dim", width=26)
        table.add_column("标题",     min_width=20)
        table.add_column("状态",     width=14)
        table.add_column("优先级",   width=8)
        table.add_column("派发对象", width=18)
        for t in tasks:
            table.add_row(
                t["id"],
                t["title"][:50],
                _state(t.get("state") or ""),
                _priority(t.get("priority") or ""),
                t.get("assignee_synapse") or "—",
            )
        console.print(table)
    except httpx.ConnectError:
        err_console.print(f"无法连接到 {_API_URL}，请确认 hive 服务已启动。")
        raise typer.Exit(1)
    except httpx.HTTPStatusError as e:
        err_console.print(f"API 错误 {e.response.status_code}：{e.response.text[:200]}")
        raise typer.Exit(1)


@tasks_app.command("dispatch", help="派发任务给指定小主脑")
def tasks_dispatch(
    task_id: str = typer.Argument(..., help="任务 ID"),
    synapse: str = typer.Option("overmind", "--synapse", "-s", help="小主脑 ID，传 'auto' 自动选最优"),
    message: str = typer.Option("", "--message", "-m", help="附加消息/指令"),
    api:     str = api_url_option,
) -> None:
    """向事件总线发布 task.dispatch 事件，由对应小主脑处理"""
    data = _post(f"/api/tasks/{task_id}/dispatch", {"synapse": synapse, "message": message})
    actual_synapse = data.get("synapse", synapse)
    console.print(
        f"[green]✓[/green] 任务 [bold]{task_id}[/bold] 已派发给 "
        f"[cyan]{actual_synapse}[/cyan]"
    )


@tasks_app.command("subtask", help="创建子任务")
def tasks_subtask(
    parent_id:  str            = typer.Argument(..., help="父任务 ID"),
    title:      str            = typer.Option(..., "--title", "-t", help="子任务标题"),
    assignee:   Optional[str]  = typer.Option(None, "--assignee", "-a", help="分配给小主脑"),
    priority:   str            = typer.Option("normal", "--priority", "-p", help="优先级"),
    api:        str            = api_url_option,
) -> None:
    """在指定父任务下创建子任务"""
    payload: dict = {"title": title, "parent_id": parent_id, "priority": priority}
    if assignee:
        payload["assignee_synapse"] = assignee
    data = _post("/api/tasks", payload)
    console.print(
        f"[green]✓[/green] 子任务已创建 [bold]{data['id']}[/bold] "
        f"父={parent_id} 标题={title}"
    )


@tasks_app.command("blocked", help="检查任务的依赖阻塞状态")
def tasks_blocked(
    task_id: str = typer.Argument(..., help="任务 ID"),
    api:     str = api_url_option,
) -> None:
    """显示任务是否被依赖阻塞及未完成的前置依赖"""
    data = _get(f"/api/tasks/{task_id}/blocked")
    if data.get("is_blocked"):
        console.print(f"[yellow]⚠[/yellow]  任务 [bold]{task_id}[/bold] 被以下依赖阻塞：")
        for dep in data.get("pending_deps", []):
            console.print(
                f"  • [dim]{dep['id']}[/dim]  "
                f"{_state(dep.get('state',''))}  {dep.get('title','')[:50]}"
            )
    else:
        console.print(f"[green]✓[/green]  任务 [bold]{task_id}[/bold] 无阻塞，可自由执行")


@tasks_app.command("analyze", help="主脑分析任务（需要 ANTHROPIC_API_KEY）")
def tasks_analyze(
    task_id: str = typer.Argument(..., help="任务 ID"),
    api:     str = api_url_option,
) -> None:
    """调用 Overmind LLM 分析任务，拆解子任务并推荐状态"""
    if httpx is None:
        err_console.print("错误：需要安装 httpx。请执行：pip install httpx")
        raise typer.Exit(1)
    try:
        r = httpx.post(f"{_API_URL}/api/tasks/{task_id}/analyze", timeout=60)
        if r.status_code == 404:
            err_console.print(f"任务不存在：{task_id}")
            raise typer.Exit(1)
        if r.status_code == 503:
            err_console.print(f"[yellow]⚠[/yellow] {r.json().get('detail', 'LLM 不可用')}")
            raise typer.Exit(1)
        r.raise_for_status()
        data = r.json()
        analysis = data.get("analysis", {})
        console.print(f"[green]✓[/green] 分析完成 [bold]{task_id}[/bold]")
        console.print(f"  概要：{analysis.get('summary', '')}")
        console.print(f"  领域：{analysis.get('domain', '')}  建议状态：{analysis.get('recommended_state', '')}")
        todos = analysis.get("todos", [])
        if todos:
            console.print(f"  Todos（{len(todos)} 条）：")
            for i, t in enumerate(todos, 1):
                console.print(f"    {i}. {t}")
        risks = analysis.get("risks", [])
        if risks:
            console.print(f"  风险：{'; '.join(risks)}")
    except httpx.ConnectError:
        err_console.print(f"无法连接到 {_API_URL}，请确认 hive 服务已启动。")
        raise typer.Exit(1)
    except httpx.HTTPStatusError as e:
        err_console.print(f"API 错误 {e.response.status_code}：{e.response.text[:200]}")
        raise typer.Exit(1)


@tasks_app.command("trial", help="赛马：两个 Synapse 并行竞争同一任务")
def tasks_trial(
    task_id:  str = typer.Argument(..., help="任务 ID"),
    synapses: str = typer.Option("code-expert,research-analyst", "--synapses", "-s",
                                  help="两个 synapse，逗号分隔"),
    message:  str = typer.Option("", "--message", "-m", help="任务消息（留空使用任务描述）"),
    domain:   str = typer.Option("", "--domain",  "-d", help="领域（留空自动推断）"),
    api:      str = api_url_option,
) -> None:
    """触发赛马：两个 synapse 并行处理任务，胜者经验自动入库"""
    parts = [s.strip() for s in synapses.split(",") if s.strip()]
    if len(parts) != 2:
        err_console.print("错误：--synapses 必须包含恰好两个名称，用逗号分隔")
        raise typer.Exit(1)
    if httpx is None:
        err_console.print("错误：需要安装 httpx。请执行：pip install httpx")
        raise typer.Exit(1)
    try:
        payload: dict = {"synapses": parts}
        if message:
            payload["message"] = message
        if domain:
            payload["domain"] = domain
        console.print(f"[cyan]▶[/cyan] 赛马开始：{parts[0]} vs {parts[1]}…")
        r = httpx.post(f"{_API_URL}/api/tasks/{task_id}/trial", json=payload, timeout=120)
        if r.status_code == 404:
            err_console.print(f"任务不存在：{task_id}")
            raise typer.Exit(1)
        r.raise_for_status()
        data = r.json()
        winner = data.get("winner")
        results = data.get("results", {})
        console.print(f"[green]✓[/green] 赛马完成  胜者：[bold]{winner or '无（均失败）'}[/bold]")
        for synapse, res in results.items():
            icon = "✅" if res.get("success") else "❌"
            console.print(f"  {icon} {synapse}  rc={res.get('returncode', '?')}")
    except httpx.ConnectError:
        err_console.print(f"无法连接到 {_API_URL}，请确认 hive 服务已启动。")
        raise typer.Exit(1)
    except httpx.HTTPStatusError as e:
        err_console.print(f"API 错误 {e.response.status_code}：{e.response.text[:200]}")
        raise typer.Exit(1)


@tasks_app.command("chain", help="Chain Mode：多个 Synapse 顺序协作")
def tasks_chain(
    task_id:  str = typer.Argument(..., help="任务 ID"),
    synapses: str = typer.Option("code-expert,research-analyst", "--synapses", "-s",
                                  help="synapse 列表，逗号分隔（至少两个）"),
    message:  str = typer.Option("", "--message", "-m", help="任务消息（留空使用任务描述）"),
    domain:   str = typer.Option("", "--domain",  "-d", help="领域（留空自动推断）"),
    api:      str = api_url_option,
) -> None:
    """顺序执行多个 synapse，每阶段输出传入下一阶段"""
    parts = [s.strip() for s in synapses.split(",") if s.strip()]
    if len(parts) < 2:
        err_console.print("错误：--synapses 至少需要两个名称，用逗号分隔")
        raise typer.Exit(1)
    if httpx is None:
        err_console.print("错误：需要安装 httpx。请执行：pip install httpx")
        raise typer.Exit(1)
    try:
        payload: dict = {"synapses": parts}
        if message:
            payload["message"] = message
        if domain:
            payload["domain"] = domain
        console.print(f"[cyan]▶[/cyan] Chain Mode 开始：{' → '.join(parts)}…")
        r = httpx.post(f"{_API_URL}/api/tasks/{task_id}/chain", json=payload, timeout=180)
        if r.status_code == 404:
            err_console.print(f"任务不存在：{task_id}")
            raise typer.Exit(1)
        r.raise_for_status()
        data = r.json()
        success = data.get("success", False)
        results = data.get("results", [])
        icon = "✅" if success else "❌"
        console.print(f"[{'green' if success else 'red'}]{icon}[/] Chain 执行{'完成' if success else '中止'}")
        for res in results:
            stage_icon = "✅" if res.get("success") else "❌"
            console.print(f"  {stage_icon} {res.get('synapse', '?')}  rc={res.get('returncode', '?')}")
        if data.get("final_output"):
            console.print(f"\n[bold]最终输出：[/bold]\n{data['final_output'][:300]}")
    except httpx.ConnectError:
        err_console.print(f"无法连接到 {_API_URL}，请确认 hive 服务已启动。")
        raise typer.Exit(1)
    except httpx.HTTPStatusError as e:
        err_console.print(f"API 错误 {e.response.status_code}：{e.response.text[:200]}")
        raise typer.Exit(1)


@tasks_app.command("swarm", help="Swarm Mode：并发 Unit 池，批量独立任务")
def tasks_swarm(
    task_id:         str = typer.Argument(..., help="任务 ID"),
    units:           str = typer.Option(..., "--units", "-u",
                                        help="unit 列表，格式：synapse1:message1,synapse2:message2"),
    max_concurrent:  int = typer.Option(5, "--max-concurrent", "-c", help="最大并发数 (1-20)"),
    api:             str = api_url_option,
) -> None:
    """并发执行多个独立 unit（每个 unit 有独立 synapse + message）"""
    unit_list = []
    for part in units.split(","):
        part = part.strip()
        if ":" not in part:
            err_console.print(f"错误：unit 格式应为 synapse:message，收到：{part!r}")
            raise typer.Exit(1)
        synapse, msg = part.split(":", 1)
        unit_list.append({"synapse": synapse.strip(), "message": msg.strip()})
    if not unit_list:
        err_console.print("错误：--units 至少需要一个 unit")
        raise typer.Exit(1)
    if httpx is None:
        err_console.print("错误：需要安装 httpx。请执行：pip install httpx")
        raise typer.Exit(1)
    try:
        payload = {"units": unit_list, "max_concurrent": max_concurrent}
        console.print(f"[cyan]▶[/cyan] Swarm Mode 开始：{len(unit_list)} 个 units…")
        r = httpx.post(f"{_API_URL}/api/tasks/{task_id}/swarm", json=payload, timeout=300)
        if r.status_code == 404:
            err_console.print(f"任务不存在：{task_id}")
            raise typer.Exit(1)
        r.raise_for_status()
        data = r.json()
        ok = data.get("success_count", 0)
        total = data.get("total", 0)
        rate = data.get("success_rate", 0)
        console.print(f"[bold]Swarm 完成[/bold]：{ok}/{total} 成功  成功率 {rate:.0%}")
        for res in data.get("results", []):
            icon = "✅" if res.get("success") else "❌"
            console.print(f"  {icon} {res.get('synapse', '?')}  rc={res.get('returncode', '?')}  {res.get('elapsed_sec', 0):.1f}s")
            if res.get("stdout"):
                console.print(f"     {res['stdout'][:80]}")
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


# ── fitness ──────────────────────────────────────────────────────────

@fitness_app.command("leaderboard")
def fitness_leaderboard(
    limit: int = typer.Option(20, "--limit", "-n", help="排行榜条数"),
    api:   str = api_url_option,
) -> None:
    """显示小主脑适存度排行榜"""
    data = _get("/api/fitness/leaderboard", params={"limit": limit})
    scores = data.get("scores", [])

    if not scores:
        console.print("[dim]暂无战功记录[/dim]")
        return

    table = Table(title=f"适存度排行榜（Top {limit}）", box=box.ROUNDED)
    table.add_column("#",            justify="right", style="dim")
    table.add_column("小主脑",       style="bold")
    table.add_column("适存度",       justify="right", style="bright_magenta")
    table.add_column("原始战功",     justify="right")
    table.add_column("战功数",       justify="right")
    table.add_column("成功",         justify="right", style="green")
    table.add_column("失败",         justify="right", style="red")
    table.add_column("成功率",       justify="right")

    for i, s in enumerate(scores, 1):
        rate = s.get("success_rate", 0)
        rate_color = "green" if rate >= 0.8 else "yellow" if rate >= 0.5 else "red"
        table.add_row(
            str(i),
            s.get("synapse_id", ""),
            f"{s.get('fitness', 0):.3f}",
            f"{s.get('raw_biomass', 0):.2f}",
            str(s.get("mark_count", 0)),
            str(s.get("success_count", 0)),
            str(s.get("fail_count", 0)),
            f"[{rate_color}]{rate:.0%}[/{rate_color}]",
        )

    console.print(table)


@fitness_app.command("show")
def fitness_show(
    synapse_id: str = typer.Argument(..., help="小主脑 ID（如 code-expert）"),
    api:        str = api_url_option,
) -> None:
    """查看单个小主脑的适存度详情"""
    data = _get(f"/api/fitness/{synapse_id}")

    console.print(f"\n[bold]小主脑：[/bold]{synapse_id}")
    console.print(f"  适存度   [bright_magenta]{data.get('fitness', 0):.4f}[/bright_magenta]")
    console.print(f"  原始战功 {data.get('raw_biomass', 0):.4f}")
    console.print(f"  战功数   {data.get('mark_count', 0)}")
    console.print(f"  成功     {data.get('success_count', 0)}")
    console.print(f"  失败     {data.get('fail_count', 0)}")
    rate = data.get("success_rate", 0)
    rate_color = "green" if rate >= 0.8 else "yellow" if rate >= 0.5 else "red"
    console.print(f"  成功率   [{rate_color}]{rate:.0%}[/{rate_color}]")

    marks = data.get("recent_marks", [])
    if marks:
        console.print("\n[bold]最近战功：[/bold]")
        m_table = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
        m_table.add_column("时间",      style="dim", no_wrap=True)
        m_table.add_column("类型",      style="cyan")
        m_table.add_column("领域")
        m_table.add_column("战功值",    justify="right", style="bright_magenta")
        m_table.add_column("原始分",    justify="right")
        for m in marks:
            m_table.add_row(
                (m.get("created_at") or "")[:19],
                m.get("mark_type", ""),
                m.get("domain", ""),
                f"{m.get('biomass_delta', 0):.3f}",
                f"{m.get('score', 0):.2f}",
            )
        console.print(m_table)


# ── lessons ────────────────────────────────────────────────────────────

_OUTCOME_COLORS: dict[str, str] = {
    "success": "green",
    "failure": "red",
    "partial": "yellow",
}


def _outcome(o: str) -> str:
    color = _OUTCOME_COLORS.get(o, "white")
    return f"[{color}]{o}[/{color}]"


@lessons_app.command("list", help="列出经验教训")
def lessons_list(
    domain:  Optional[str] = typer.Option(None, "--domain", "-d", help="按领域过滤"),
    limit:   int            = typer.Option(30,   "--limit",  "-n", help="最多显示条数"),
    api:     str            = api_url_option,
) -> None:
    """列出基因库中的经验教训"""
    params: dict = {"limit": limit}
    if domain:
        params["domain"] = domain
    data = _get("/api/lessons", params=params)
    if not data:
        console.print("[yellow]暂无经验教训[/yellow]")
        return
    table = Table(title="经验教训基因库", show_header=True, header_style="bold cyan")
    table.add_column("ID",      style="dim", width=12)
    table.add_column("领域",    width=12)
    table.add_column("结果",    width=10)
    table.add_column("命中数",  justify="right", width=8)
    table.add_column("内容",    min_width=30)
    for l in data:
        table.add_row(
            (l["id"] or "")[:10],
            l.get("domain", ""),
            _outcome(l.get("outcome", "")),
            str(l.get("frequency", 0)),
            (l.get("content") or "")[:60],
        )
    console.print(table)


@lessons_app.command("add", help="添加经验教训")
def lessons_add(
    domain:  str = typer.Option(..., "--domain", "-d", help="领域（如 coding/research）"),
    content: str = typer.Option(..., "--content", "-c", help="经验内容"),
    outcome: str = typer.Option("success", "--outcome", "-o", help="结果: success/failure/partial"),
    api:     str = api_url_option,
) -> None:
    """向基因库添加一条经验教训"""
    data = _post("/api/lessons", {"domain": domain, "content": content, "outcome": outcome})
    console.print(f"[green]✓[/green] 经验已入库 [bold]{data['id'][:10]}[/bold] domain={domain} outcome={outcome}")


@lessons_app.command("search", help="按领域和关键词搜索经验")
def lessons_search(
    domain:  str = typer.Argument(..., help="领域"),
    tags:    str = typer.Option("", "--tags", "-t", help="空格分隔的关键词"),
    top_k:   int = typer.Option(5,  "--top-k", "-k", help="返回最多 N 条"),
    api:     str = api_url_option,
) -> None:
    """检索最相关的经验教训（按衰减评分排序）"""
    tag_list = [t for t in tags.strip().split() if t] if tags.strip() else []
    data = _post("/api/lessons/search", {"domain": domain, "tags": tag_list, "top_k": top_k})
    if not data:
        console.print("[yellow]未找到相关经验[/yellow]")
        return
    for i, l in enumerate(data, 1):
        color = _OUTCOME_COLORS.get(l.get("outcome", ""), "white")
        console.print(f"[dim]{i}.[/dim] [{color}]{l.get('outcome','?')}[/{color}] "
                      f"[cyan]{l.get('domain','')}[/cyan] 命中={l.get('frequency',0)}")
        console.print(f"   {(l.get('content') or '')[:120]}")
        console.print()


@lessons_app.command("bump", help="增加经验的命中计数")
def lessons_bump(
    lesson_id: str = typer.Argument(..., help="经验 ID"),
    api:       str = api_url_option,
) -> None:
    """手动 bump 一条经验的命中频率"""
    if httpx is None:
        err_console.print("错误：需要安装 httpx。")
        raise typer.Exit(1)
    try:
        r = httpx.post(f"{_API_URL}/api/lessons/{lesson_id}/bump", timeout=10)
        if r.status_code == 404:
            err_console.print(f"经验不存在：{lesson_id}")
            raise typer.Exit(1)
        r.raise_for_status()
        data = r.json()
        console.print(f"[green]✓[/green] bump 成功，frequency={data.get('frequency', '?')}")
    except httpx.ConnectError:
        err_console.print(f"无法连接到 {_API_URL}。")
        raise typer.Exit(1)


@lessons_app.command("delete", help="删除经验教训")
def lessons_delete(
    lesson_id: str  = typer.Argument(..., help="经验 ID"),
    yes:       bool = typer.Option(False, "--yes", "-y", help="跳过确认"),
    api:       str  = api_url_option,
) -> None:
    """硬删除一条经验教训"""
    if not yes:
        typer.confirm(f"确认删除经验 {lesson_id}？", abort=True)
    if httpx is None:
        err_console.print("错误：需要安装 httpx。")
        raise typer.Exit(1)
    try:
        r = httpx.delete(f"{_API_URL}/api/lessons/{lesson_id}", timeout=10)
        if r.status_code == 404:
            err_console.print(f"经验不存在：{lesson_id}")
            raise typer.Exit(1)
        if r.status_code in (200, 204):
            console.print(f"[green]✓[/green] 已删除 {lesson_id}")
        else:
            r.raise_for_status()
    except httpx.ConnectError:
        err_console.print(f"无法连接到 {_API_URL}。")
        raise typer.Exit(1)


# ── playbooks ───────────────────────────────────────────────────────────

@playbooks_app.command("list", help="列出作战手册")
def playbooks_list(
    domain:  Optional[str] = typer.Option(None, "--domain", "-d", help="按领域过滤"),
    api:     str            = api_url_option,
) -> None:
    """列出所有作战手册"""
    params: dict = {}
    if domain:
        params["domain"] = domain
    data = _get("/api/playbooks", params=params)
    if not data:
        console.print("[yellow]暂无作战手册[/yellow]")
        return
    table = Table(title="作战手册", show_header=True, header_style="bold cyan")
    table.add_column("Slug",     style="dim", width=20)
    table.add_column("标题",     min_width=20)
    table.add_column("领域",     width=12)
    table.add_column("版本",     width=6, justify="right")
    table.add_column("使用数",   width=8, justify="right")
    table.add_column("成功率",   width=10, justify="right")
    for p in data:
        rate = p.get("success_rate") or 0
        rate_color = "green" if rate >= 0.8 else "yellow" if rate >= 0.5 else "red"
        table.add_row(
            (p.get("slug") or "")[:18],
            (p.get("title") or "")[:30],
            p.get("domain", ""),
            f"v{p.get('version', 1)}",
            str(p.get("use_count", 0)),
            f"[{rate_color}]{rate:.0%}[/{rate_color}]",
        )
    console.print(table)


@playbooks_app.command("show", help="查看手册详情")
def playbooks_show(
    slug: str = typer.Argument(..., help="手册 Slug"),
    api:  str = api_url_option,
) -> None:
    """显示手册完整内容"""
    if httpx is None:
        err_console.print("错误：需要安装 httpx。")
        raise typer.Exit(1)
    try:
        r = httpx.get(f"{_API_URL}/api/playbooks/slug/{slug}", timeout=10)
        if r.status_code == 404:
            err_console.print(f"手册不存在：{slug}")
            raise typer.Exit(1)
        r.raise_for_status()
        p = r.json()
    except httpx.ConnectError:
        err_console.print(f"无法连接到 {_API_URL}。")
        raise typer.Exit(1)
    rate = p.get("success_rate") or 0
    rate_color = "green" if rate >= 0.8 else "yellow" if rate >= 0.5 else "red"
    console.print(f"\n[bold]{p.get('title', slug)}[/bold]  v{p.get('version', 1)}")
    console.print(f"  领域：{p.get('domain', '')}  "
                  f"使用数：{p.get('use_count', 0)}  "
                  f"成功率：[{rate_color}]{rate:.0%}[/{rate_color}]")
    console.print()
    console.print(p.get("content", ""))
    console.print()


@playbooks_app.command("add", help="创建作战手册")
def playbooks_add(
    slug:    str            = typer.Option(..., "--slug",    "-s", help="唯一标识（如 coding-guide）"),
    title:   str            = typer.Option(..., "--title",   "-t", help="手册标题"),
    domain:  str            = typer.Option(..., "--domain",  "-d", help="所属领域"),
    content: str            = typer.Option(..., "--content", "-c", help="手册内容"),
    api:     str            = api_url_option,
) -> None:
    """创建一本新的作战手册"""
    data = _post("/api/playbooks", {
        "slug": slug, "title": title, "domain": domain, "content": content,
    })
    console.print(f"[green]✓[/green] 手册已创建 slug=[bold]{data.get('slug')}[/bold] v{data.get('version', 1)}")


@playbooks_app.command("search", help="按领域和关键词搜索手册")
def playbooks_search(
    domain: str = typer.Argument(..., help="领域"),
    tags:   str = typer.Option("", "--tags", "-t", help="空格分隔的关键词"),
    top_k:  int = typer.Option(3,  "--top-k", "-k", help="返回最多 N 条"),
    api:    str = api_url_option,
) -> None:
    """检索最相关的作战手册（按质量评分排序）"""
    tag_list = [t for t in tags.strip().split() if t] if tags.strip() else []
    data = _post("/api/playbooks/search", {"domain": domain, "tags": tag_list, "top_k": top_k})
    if not data:
        console.print("[yellow]未找到相关手册[/yellow]")
        return
    for i, p in enumerate(data, 1):
        rate = p.get("success_rate") or 0
        rate_color = "green" if rate >= 0.8 else "yellow" if rate >= 0.5 else "red"
        console.print(f"[dim]{i}.[/dim] [bold]{p.get('title', '')}[/bold] "
                      f"v{p.get('version',1)} [{rate_color}]{rate:.0%}[/{rate_color}]")
        console.print(f"   {(p.get('content') or '')[:120]}")
        console.print()


# ── genes ────────────────────────────────────────────────────────────────

import json as _json
from pathlib import Path as _Path


@genes_app.command("export", help="导出全部经验教训 + 作战手册为 JSON 文件")
def genes_export(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="输出文件路径（默认打印到 stdout）"),
    api:    str            = api_url_option,
) -> None:
    """将 lessons + playbooks 导出为可移植的 JSON bundle"""
    data = _get("/api/genes/export")
    dump = _json.dumps(data, ensure_ascii=False, indent=2)
    if output:
        _Path(output).write_text(dump, encoding="utf-8")
        console.print(
            f"[green]✓[/green] 已导出 "
            f"{data.get('lessons_count', 0)} 条经验 + "
            f"{data.get('playbooks_count', 0)} 本手册 → {output}"
        )
    else:
        console.print(dump)


@genes_app.command("import", help="从 JSON 文件批量导入经验教训 + 作战手册")
def genes_import(
    file: str = typer.Argument(..., help="JSON bundle 文件路径"),
    api:  str = api_url_option,
) -> None:
    """从 genes export 生成的 JSON bundle 批量导入"""
    path = _Path(file)
    if not path.exists():
        err_console.print(f"文件不存在：{file}")
        raise typer.Exit(1)
    try:
        bundle = _json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        err_console.print(f"JSON 解析失败：{e}")
        raise typer.Exit(1)
    result = _post("/api/genes/import", {
        "lessons":   bundle.get("lessons", []),
        "playbooks": bundle.get("playbooks", []),
    })
    console.print(
        f"[green]✓[/green] 导入完成  "
        f"经验 +{result.get('lessons_added', 0)}  "
        f"手册 +{result.get('playbooks_added', 0)}  "
        f"手册跳过 {result.get('playbooks_skipped', 0)}"
    )


# ── 入口 ──────────────────────────────────────────────────────────────

def main() -> None:
    app()


if __name__ == "__main__":
    main()
