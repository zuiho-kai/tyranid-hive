# Phase 1 实施规格：人格责任链落地

日期：2026-03-26  
状态：Spec Draft v1

## 1. 目标

这份规格用于把 `docs/vision/` 的 3 份文档，翻译成当前 `tyranid-hive` 仓库里一轮最小可落地改造。

Phase 1 不追求一次做完完整虫巢生命系统。  
Phase 1 只做一件事：

**把现有“任务状态机 + agent 调度器”，推进成“人格责任链 + 执行明细可展开”的系统。**

也就是：

- 默认层先看谁在负责
- 任务责任真正挂到人格主体上
- handoff 成为一等对象
- brood / unit 细节进入可选细节层
- 保留现有执行核，不推倒重来

## 2. 本阶段范围

### 2.1 要做的

- 引入 `Lifeform` 最小模型
- 给任务增加 `current_owner_lifeform`
- 引入 `Assignment` 与 `Handoff`
- 让现有 route / dispatch / stage event 能映射到人格责任链
- 前端主线程改为“主宰 / 子主脑 / 交接卡片”语义
- 细节面板继续保留执行模式、事件、执行过程

### 2.2 暂时不做的

- 不做完整的子主脑诞生系统
- 不做自动演化元治理
- 不做复杂长期记忆图谱
- 不做适存计算重构
- 不做完整 brood / unit 独立持久化表

Phase 1 的原则是：

- 先立责任链
- 再立生命连续性
- 最后再扩执行层和元治理层

## 3. 当前仓库现状

当前仓库已有的基础：

- [task.py](D:\虫群\tyranid-hive\src\greyfield_hive\models\task.py)
  - 已有任务状态机、`exec_mode`、`assignee_synapse`
- [submind.py](D:\虫群\tyranid-hive\src\greyfield_hive\models\submind.py)
  - 已有 `Submind` ORM，但更像现成专家实体，不是完整生命层
- [event.py](D:\虫群\tyranid-hive\src\greyfield_hive\models\event.py)
  - 已有 `HiveEvent` 持久化事件
- [task_service.py](D:\虫群\tyranid-hive\src\greyfield_hive\services\task_service.py)
  - 已有任务 CRUD、状态流转、dispatch
- [mode_router.py](D:\虫群\tyranid-hive\src\greyfield_hive\services\mode_router.py)
  - 已有 `solo / trial / chain / swarm`
- [tasks.py](D:\虫群\tyranid-hive\src\greyfield_hive\api\tasks.py)
  - 任务 API 仍以 task 状态和 synapse 语义为主
- [events.py](D:\虫群\tyranid-hive\src\greyfield_hive\api\events.py)
  - 已有事件查询接口
- [api.ts](D:\虫群\tyranid-hive\dashboard\src\api.ts)
  - 前端任务模型仍围绕 `assignee_synapse / exec_mode / flow_log`
- [TrunkChat.tsx](D:\虫群\tyranid-hive\dashboard\src\components\TrunkChat.tsx)
  - 中间栏仍然主要由 `flow_log + progress_log` 拼接
- [DetailPanel.tsx](D:\虫群\tyranid-hive\dashboard\src\components\DetailPanel.tsx)
  - 右栏已有“为什么这样路由 / 分化情况 / 执行过程”的雏形

当前主要缺口：

1. 任务责任没有挂在人格主体上
2. `assignee_synapse` 仍然是执行器语义，不是生命语义
3. handoff 只是推断，不是一等数据
4. 现有 `Submind` 模型不是“虫群娘化子主脑”语义
5. 前端主线程仍然在展示大量状态机痕迹

## 4. Phase 1 的设计原则

### 4.1 不推翻现有执行核

`mode_router / dispatcher / chain_runner / swarm_runner / trial_race` 暂时保留。

Phase 1 做的是在它们外面补一层人格责任链，不是先重写执行核。

### 4.2 不强行把现有 synapse 直接当最终人格

现有：

- `overmind`
- `code-expert`
- `research-analyst`
- `finance-scout`
- `evolution-master`

这些更接近执行核入口，不应直接等于最终人格体系。

Phase 1 的正确做法是：

- 先引入 `Lifeform`
- 再让 `Lifeform` 暂时映射到现有 synapse
- 后续再逐步摆脱 synapse 直出

### 4.3 先建立“虫群主宰 + 当前负责人”

Phase 1 不要求一开始就有大量常驻子主脑。  
但至少要立住：

- 虫群主宰
- 当前负责的子主脑
- 责任如何切换

## 5. 数据模型改造

### 5.1 新增 `Lifeform`

新增模型文件：

- `src/greyfield_hive/models/lifeform.py`

建议最小字段：

- `id`
- `key`
- `kind`
- `name`
- `display_name`
- `persona_summary`
- `lineage`
- `status`
- `backing_synapse`
- `created_at`
- `updated_at`

建议取值：

- `kind`: `sovereign | submind`
- `status`: `active | dormant | sealed`

Phase 1 约束：

- 必须先有一条虫群主宰记录
- 可预置少量已分化子主脑记录
- `backing_synapse` 用于兼容现有执行核

### 5.2 扩展 `Task`

修改文件：

- `src/greyfield_hive/models/task.py`

新增字段：

- `current_owner_lifeform_id`
- `entry_lifeform_id`
- `last_handoff_id`

保留字段：

- `assignee_synapse`
- `exec_mode`
- `flow_log`
- `progress_log`

原因：

- 旧字段先保留，方便兼容现有 API 和前端
- 新字段用于建立责任人格链

### 5.3 新增 `Assignment`

新增模型文件：

- `src/greyfield_hive/models/assignment.py`

最小字段：

- `id`
- `task_id`
- `owner_lifeform_id`
- `assigned_by_lifeform_id`
- `reason`
- `scope`
- `expected_output`
- `status`
- `created_at`
- `ended_at`

状态建议：

- `active`
- `completed`
- `aborted`

### 5.4 新增 `Handoff`

新增模型文件：

- `src/greyfield_hive/models/handoff.py`

最小字段：

- `id`
- `task_id`
- `from_lifeform_id`
- `to_lifeform_id`
- `reason`
- `scope`
- `expected_output`
- `return_to_lifeform_id`
- `created_at`

### 5.5 暂不新增 `BroodRun` / `UnitRun` 表

Phase 1 不单独建表。

先做兼容策略：

- 继续用 `HiveEvent`
- 在 `payload/meta` 中补标准字段
- 由前端和 API 映射成 brood / unit 细节视图

原因：

- 这样风险最低
- 能先把 UI 和责任链做通
- Phase 2 再考虑独立表

## 6. 后端服务改造

### 6.1 新增 `LifeformService`

新增文件：

- `src/greyfield_hive/services/lifeform_service.py`

职责：

- 获取虫群主宰
- 按 id / key 查询生命体
- 初始化默认生命体
- 根据 `backing_synapse` 做兼容映射

Phase 1 最小要求：

- `overmind` 必须映射到虫群主宰
- 至少能查到“当前负责人”的生命对象

### 6.2 扩展 `TaskService`

修改文件：

- `src/greyfield_hive/services/task_service.py`

新增能力：

- 创建任务时写入 `entry_lifeform_id = 虫群主宰`
- 创建默认 `Assignment`
- 提供 `assign_lifeform(...)`
- 提供 `handoff(...)`
- 任务状态变更时同步维护 `current_owner_lifeform_id`

目标：

- 不再只有 `assignee_synapse`
- 真正能说清“现在谁在负责”

### 6.3 扩展 `ModeRouter`

修改文件：

- `src/greyfield_hive/services/mode_router.py`

新增要求：

- `route_reason` 不只写执行模式
- 同时写人格责任原因
- 当进入 `solo / trial / chain / swarm` 前，明确记录：
  - 当前 owner 是谁
  - 是她亲自处理，还是她放 brood
  - 是否发生 handoff

新增标准 meta 字段建议：

- `owner_lifeform_id`
- `owner_display_name`
- `handoff_reason`
- `responsibility_scope`
- `return_target_lifeform_id`
- `brood_summary`

### 6.4 扩展 `execution_events`

修改文件：

- `src/greyfield_hive/services/execution_events.py`

要求：

- 统一补充与人格责任链相关的事件字段
- 让事件既可用于审计，也可供前端细节面板消费

建议事件新增字段：

- `lifeform_id`
- `lifeform_kind`
- `brood_id` 或 `brood_key`
- `unit_key`
- `contract_summary`

### 6.5 `dispatcher` / `orchestrator` 的角色收口

修改文件：

- `src/greyfield_hive/workers/dispatcher.py`
- `src/greyfield_hive/workers/orchestrator.py`

要求：

- 默认由虫群主宰接球
- 只有在明确决定委派时才创建 `handoff`
- 不再直接把“路由到 code-expert”当作前台主语

## 7. API 改造

### 7.1 扩展 `/api/tasks`

修改文件：

- `src/greyfield_hive/api/tasks.py`

`_task_to_dict` 新增返回：

- `current_owner`
- `entry_lifeform`
- `current_assignment`
- `last_handoff`

建议结构：

```json
{
  "current_owner": {
    "id": "LF-...",
    "kind": "sovereign",
    "name": "虫群主宰",
    "display_name": "虫群主宰"
  }
}
```

### 7.2 新增 `/api/lifeforms`

新增文件：

- `src/greyfield_hive/api/lifeforms.py`

首轮只做只读接口：

- `GET /api/lifeforms`
- `GET /api/lifeforms/{lifeform_id}`

用途：

- 前端展示虫群主宰和当前子主脑
- 后台调试和后续管理

### 7.3 新增 `/api/tasks/{task_id}/handoffs`

首轮只做读接口即可：

- `GET /api/tasks/{task_id}/handoffs`

用途：

- 前端主线程展示 handoff 卡片
- 右侧详情显示完整责任链

### 7.4 暂不新增 `/api/broods`

Phase 1 先不拆新接口。

执行细节仍然从：

- `/api/events`
- `task.meta`

拼装。

## 8. 前端改造

### 8.1 API 类型层

修改文件：

- `dashboard/src/api.ts`

新增类型：

- `Lifeform`
- `Assignment`
- `Handoff`

扩展 `Task`：

- `current_owner?: Lifeform | null`
- `entry_lifeform?: Lifeform | null`
- `current_assignment?: Assignment | null`
- `last_handoff?: Handoff | null`

### 8.2 中间主线程

修改文件：

- `dashboard/src/components/TrunkChat.tsx`

目标：

- 主线程优先显示责任人格链
- 减少状态机消息感

具体改法：

1. 顶部状态摘要改成：
   - 当前负责人
   - 当前阶段
   - 是否待补充

2. 消息流不再直接按 `flow_log + progress_log` 生拼

3. 改成 4 类卡片：
   - 用户输入
   - 虫群主宰接球 / 收束
   - handoff 卡片
   - 当前负责人输出

4. `flow_log` 只作为辅助来源，不再直接等于主线程

### 8.3 右侧细节面板

修改文件：

- `dashboard/src/components/DetailPanel.tsx`

保留现有优点，但重新分组：

- 当前负责人
- 为什么由她负责
- handoff 记录
- brood / unit 执行细节
- 原始事件账本

这里继续允许展示：

- `solo / trial / chain / swarm`
- `task.stage.*`
- route reason
- event payload

因为这里本来就是细节层。

### 8.4 展示工具层

修改文件：

- `dashboard/src/utils/display.ts`

新增职责：

- 把 `Lifeform` 渲染成前台人格名
- 把 `Handoff` 渲染成责任交接语言
- 把“执行器字段”翻译成“人格 + brood”语言

### 8.5 左侧任务列表

修改文件：

- `dashboard/src/components/ChannelSidebar.tsx`
- `dashboard/src/components/TaskList.tsx`

首轮只加一项：

- 任务卡片显示“当前负责人”

不要再继续堆更多筛选器或术语。

## 9. 迁移方案

### 9.1 数据迁移顺序

建议顺序：

1. 新增 `lifeforms / assignments / handoffs` 表
2. 给 `tasks` 加 `current_owner_lifeform_id / entry_lifeform_id / last_handoff_id`
3. 初始化虫群主宰记录
4. 为历史任务回填 `entry_lifeform_id = 虫群主宰`
5. 为历史任务回填 `current_owner_lifeform_id`

### 9.2 历史任务回填规则

最小回填规则：

- 如果 `assignee_synapse == overmind` 或为空，当前负责人回填为虫群主宰
- 如果 `assignee_synapse` 是现有专家入口，则映射到对应已存在子主脑或兼容 lifeform
- 没法可靠判断的，统一回填为虫群主宰

原则：

- 宁可保守，不要虚构责任链

### 9.3 兼容期

Phase 1 必须允许以下字段并存：

- 旧：`assignee_synapse`
- 新：`current_owner_lifeform_id`

前端展示优先级：

1. `current_owner`
2. `last_handoff.to`
3. `assignee_synapse`

## 10. 验收标准

Phase 1 完成后，以下行为必须成立：

1. 新建任务后，任务对象能明确返回虫群主宰为入口负责人。
2. 当任务交给某位子主脑时，API 能返回结构化 `handoff`。
3. 中间主线程默认能看出“谁在负责”，而不是只看状态机跳转。
4. 右侧细节能继续看到执行模式、分化细节和事件账本。
5. 旧任务在兼容期不会因为缺失新字段而直接崩 UI。

## 11. Phase 1 实施顺序

建议按下面顺序做：

### Step 1

后端模型与迁移：

- `lifeform.py`
- `assignment.py`
- `handoff.py`
- `task.py` 增字段

### Step 2

服务层：

- `lifeform_service.py`
- `task_service.py` 增 assignment / handoff
- `mode_router.py` 补责任人格 meta

### Step 3

API：

- `tasks.py` 扩展返回结构
- 新增 `lifeforms.py`
- 新增 `tasks/{id}/handoffs`

### Step 4

前端：

- `api.ts`
- `TrunkChat.tsx`
- `DetailPanel.tsx`
- `display.ts`
- `TaskList.tsx`

### Step 5

回归：

- 新任务：主宰亲自处理
- 新任务：主宰 handoff 给子主脑
- 多路执行：主线程不被 unit 日志淹没
- 历史任务：兼容显示

## 12. 非目标提醒

这轮不要顺手做这些：

- 子主脑命名体系定稿
- 完整 brood 独立持久化
- 适存算法重写
- 元治理自动演化
- 所有旧状态机术语彻底删干净

这轮只要把“责任人格链”立住，就已经值回票价。

