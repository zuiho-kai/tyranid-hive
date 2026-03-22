# 快速开始 —— 让 Claude Code 成为虫群的执行层

> Tyranid Hive 提供任务编排骨架；Claude Code（或 openclaw）作为真正的执行者。
> 本文带你从零到"一个任务、两个 Agent、一次赛马"的完整体验。

---

## 前提

| 依赖 | 版本 |
|------|------|
| Python | 3.10+ |
| Claude Code CLI | 最新版（`npm i -g @anthropic-ai/claude-code`） |
| ANTHROPIC_API_KEY | 已设置为环境变量 |

---

## 第一步：启动 Hive 服务

```bash
# 克隆并安装
git clone https://github.com/zuiho-kai/tyranid-hive
cd tyranid-hive
pip install -e ".[dev]"

# 启动（默认端口 8765）
python start.py
# 或 docker-compose up
```

访问 http://localhost:8765/docs 查看完整 API 文档。
Dashboard：http://localhost:8765/dashboard（如有）

---

## 第二步：创建一个任务

```bash
# 通过 CLI
hive tasks create "实现一个斐波那契函数" --priority high

# 或通过 API
curl -X POST http://localhost:8765/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "实现斐波那契函数", "description": "需要递推和记忆化两种版本"}'
```

记录返回的 `id`（如 `T-abc123`）。

---

## 第三步：触发赛马（Trial Race）

赛马是 Hive 最核心的体验：两个 Agent 并行处理同一任务，胜者的经验自动入库。

```bash
# code-expert vs research-analyst 赛马
curl -X POST http://localhost:8765/api/tasks/T-abc123/trial \
  -H "Content-Type: application/json" \
  -d '{
    "synapses": ["code-expert", "research-analyst"],
    "message": "实现斐波那契函数，需要递推和记忆化两种版本，并附简单测试",
    "domain": "coding"
  }'
```

Hive 会：
1. 并行调用 `claude` CLI（一次以 `code-expert` 角色，一次以 `research-analyst` 角色）
2. 等待两者完成
3. 比较结果，选出胜者
4. 将胜者的执行经验写入基因库（Lessons Bank）

---

## 第四步：直接派发（单 Agent）

```bash
# 派发给 code-expert，基因上下文自动注入
curl -X POST http://localhost:8765/api/tasks/T-abc123/dispatch \
  -H "Content-Type: application/json" \
  -d '{"synapse": "code-expert", "message": "请实现功能"}'
```

---

## Claude Code 如何感知 Hive 上下文？

Dispatcher 调用 Claude Code 时，会设置以下环境变量：

| 变量 | 内容 |
|------|------|
| `HIVE_TASK_ID` | 当前任务 ID |
| `HIVE_TRACE_ID` | 追踪 ID |
| `HIVE_SYNAPSE` | 本次扮演的角色名 |
| `HIVE_API_URL` | Hive API 地址（默认 http://localhost:8765）|

同时，Dispatcher 会把历史经验（Lessons）和作战手册（Playbooks）**注入到提示词前缀**中，
Claude Code 无需额外配置即可获得基因库上下文。

---

## 在你自己的项目中使用 Synapse

如果你希望 Claude Code 在你的项目目录中工作并汇报进度，在项目根目录放置
`CLAUDE.md`（参考 `genes/synapses/CLAUDE.md` 模板），内容大致为：

```markdown
# Synapse 身份说明

你是 Tyranid Hive 虫群的一个小主脑（Synapse）。

环境变量 HIVE_TASK_ID、HIVE_SYNAPSE、HIVE_API_URL 由 Hive 在启动时注入。

## 汇报进度

完成关键步骤后，通过 Hive API 汇报进度：

    curl -X POST $HIVE_API_URL/api/tasks/$HIVE_TASK_ID/progress \
      -H "Content-Type: application/json" \
      -d '{"agent": "'$HIVE_SYNAPSE'", "content": "步骤 N 已完成：..."}'
```

完整模板见 `genes/synapses/CLAUDE.md`。

---

## 经验会自动积累

每次赛马或派发完成后，Hive 自动：
- 将执行结果（成功/失败 + 输出摘要）写入 **Lessons Bank**
- 基因检索策略会优先召回最近使用、高频成功的经验
- 当某条 Playbook 被使用 ≥10 次且成功率 ≥80%，自动**结晶**（标为黄金路径）

随着使用次数增加，每次 Agent 调用都会获得越来越丰富的历史经验。

---

## CLI 快速参考

```bash
hive tasks list                          # 查看任务列表
hive tasks create "标题" -p high         # 创建任务
hive tasks patch <id> --title "新标题"   # 修改任务
hive tasks transition <id> Executing     # 手动流转状态
hive tasks cancel <id>                   # 取消任务
hive synapses                            # 查看在线 Synapse
```
