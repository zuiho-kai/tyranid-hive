# 领域模型

日期：2026-03-26  
状态：Domain Model Draft v1

## 1. 目的

这份文档把前面的愿景和语义，收敛成可落地的领域模型。  
它不直接规定数据库表结构，但定义后续后端、接口、前端状态都应该围绕哪些核心对象建模。

这份文档回答：

- 系统里有哪些一等对象
- 它们之间是什么关系
- 哪些对象属于生命层，哪些属于执行层
- 任务和责任应该挂在哪

## 2. 建模原则

### 2.1 生命和执行体必须分模

子主脑是常驻生命，brood 和 unit 是执行体。  
如果把它们混成一类对象，后续一定会出现：

- 身份连续性丢失
- 执行日志污染人格层
- 任务责任归属不清

### 2.2 任务责任必须挂在人格主体上

任务不能只挂在模式、agent 名称或临时执行器上。  
默认责任主体必须是：

- 虫群主宰
- 某位子主脑

### 2.3 结构化 artifact 是必需品

长期协作不能靠“模型差不多记得”，而要靠 artifact 承接。  
每次交接、brood 放出、结果回收，都必须能留下结构化对象。

## 3. 核心对象总览

建议把系统的一等对象定义为：

- `Lifeform`
- `Lineage`
- `Task`
- `Assignment`
- `Handoff`
- `BroodRun`
- `UnitRun`
- `Artifact`
- `GovernanceRule`

其中：

- `Lifeform / Lineage` 属于生命层
- `BroodRun / UnitRun / Artifact` 主要属于执行层
- `GovernanceRule` 属于元治理层
- `Task / Assignment / Handoff` 是跨层连接件

## 4. 生命层模型

### 4.1 Lineage

`Lineage` 表示尚未必然人格化的谱系潜势。

建议属性：

- `lineage_id`
- `name`
- `description`
- `capability_scope`
- `differentiation_bias`
- `status`

它的意义是：

- 代表一个潜在分化方向
- 不是前台常驻角色
- 可以被虫群主宰用来判断“是否值得诞生新生命”

初始建议至少有：

- 实施谱系
- 研究谱系
- 市场谱系
- 审校谱系

### 4.2 Lifeform

`Lifeform` 是常驻生命体，是最核心的人格对象。

建议属性：

- `lifeform_id`
- `kind`
- `name`
- `title`
- `persona_summary`
- `lineage_id`
- `origin`
- `authority_scope`
- `status`
- `fitness_score`
- `memory_summary`
- `created_at`
- `last_awakened_at`
- `sealed_reason`

说明：

- `kind` 至少区分 `sovereign` 和 `submind`
- 虫群主宰本身也是 `Lifeform`
- 子主脑一旦诞生，就应长期存在于这张模型里

### 4.3 LifeformMemory

子主脑的长期连续性不能只靠拼接消息记录。

建议有独立记忆对象：

- `memory_id`
- `lifeform_id`
- `summary`
- `domain_patterns`
- `successful_playbooks`
- `failure_patterns`
- `relationship_notes`
- `updated_at`

它不是聊天全文，而是可复用的长期人格与经验摘要。

### 4.4 LifeformState

生命状态建议明确建模，而不是藏在零散字段里。

推荐状态：

- `active`
- `dormant`
- `sealed`

未来可扩展：

- `crystallizing`
- `retired`

## 5. 任务与责任模型

### 5.1 Task

`Task` 是用户意图和执行承载物。

建议属性：

- `task_id`
- `thread_id`
- `title`
- `user_input`
- `status`
- `current_owner_lifeform_id`
- `current_assignment_id`
- `result_summary`
- `blocking_reason`
- `created_at`
- `updated_at`

关键点：

- `current_owner_lifeform_id` 必须是一等字段
- 不能让任务只挂在模式或某个临时执行器上

### 5.2 Assignment

`Assignment` 表示某个时段内，任务责任被哪位生命接住。

建议属性：

- `assignment_id`
- `task_id`
- `owner_lifeform_id`
- `assigned_by_lifeform_id`
- `reason`
- `scope`
- `expected_output`
- `status`
- `started_at`
- `ended_at`

它是责任链的核心对象。

一个任务在不同时段可以有多个 assignment，但同一时刻只应有一个主 assignment。

### 5.3 Handoff

`Handoff` 是责任切换对象，不是单纯事件日志。

建议属性：

- `handoff_id`
- `task_id`
- `from_lifeform_id`
- `to_lifeform_id`
- `reason`
- `scope`
- `expected_output`
- `return_target_lifeform_id`
- `status`
- `created_at`

说明：

- `Assignment` 表示“谁在负责”
- `Handoff` 表示“责任如何切换过去”

二者不能混成一个对象。

## 6. 执行层模型

### 6.1 BroodRun

`BroodRun` 表示某位生命为一项任务放出的执行群组。

建议属性：

- `brood_run_id`
- `task_id`
- `owner_lifeform_id`
- `assignment_id`
- `trigger_reason`
- `execution_mode`
- `contract_summary`
- `status`
- `started_at`
- `ended_at`

说明：

- 它属于执行层
- 它不拥有任务人格主权
- 它只是某位生命的执行延伸

### 6.2 UnitRun

`UnitRun` 表示 brood 内的最小执行单元。

建议属性：

- `unit_run_id`
- `brood_run_id`
- `unit_type`
- `scope`
- `input_summary`
- `output_summary`
- `status`
- `started_at`
- `ended_at`

`unit_type` 可以是：

- search
- fetch
- synthesize
- code
- test
- verify

这是执行分类，不是前台人格分类。

### 6.3 ExecutionMode

执行模式建议作为 `BroodRun` 的结构属性，而不是前台主语。

推荐值：

- `solo`
- `trial`
- `chain`
- `swarm`

规则：

- 这是执行结构
- 默认不直接暴露给普通用户
- 可以在细节层展示

### 6.4 Contract

每次 brood 放出前，都应有明确 contract。

建议 contract 至少包含：

- 本轮目标
- 返回格式
- 成功条件
- 失败条件
- 回收条件

它可以独立成对象，也可以先作为 `BroodRun` 的结构化字段存在。

## 7. Artifact 模型

### 7.1 Artifact

`Artifact` 是跨生命、跨阶段承接工作的结构化成果。

建议属性：

- `artifact_id`
- `task_id`
- `producer_type`
- `producer_id`
- `artifact_type`
- `title`
- `summary`
- `payload`
- `created_at`

其中：

- `producer_type` 可区分 `lifeform / brood / unit`
- `artifact_type` 可区分 `brief / contract / synthesis / review / report / memory_note`

### 7.2 为什么 artifact 需要独立对象

因为以下内容都不该只散落在聊天消息里：

- 交接说明
- brood contract
- 中间收束结果
- 验证结论
- 对上层生命的建议

如果没有独立 artifact，对长期复用和后续审计都很差。

## 8. 元治理模型

### 8.1 GovernanceRule

当前阶段规则先人工冻结，但数据层应预留对象。

建议属性：

- `rule_id`
- `rule_type`
- `name`
- `version`
- `content`
- `status`
- `created_at`
- `updated_at`

`rule_type` 可包括：

- differentiation
- awakening
- brood_trigger
- review_trigger
- crystallization

### 8.2 为什么先建模再冻结

虽然当前不允许系统自改制度，但仍应把规则层单独建模，避免未来把制度和任务数据彻底揉死。

## 9. 对象关系

### 9.1 关键关系

核心关系建议如下：

- 一个 `Lineage` 可对应多个 `Lifeform`
- 一个 `Task` 在同一时刻只有一个主 `Assignment`
- 一个 `Assignment` 可由多个 `Handoff` 前后串联
- 一个 `Assignment` 可放出多个 `BroodRun`
- 一个 `BroodRun` 可包含多个 `UnitRun`
- `Artifact` 可由 `Lifeform`、`BroodRun`、`UnitRun` 产生

### 9.2 推荐心智模型

可以这样理解：

- `Lifeform` 是谁
- `Assignment` 是谁在负责
- `Handoff` 是责任怎么转过去
- `BroodRun` 是她放出了什么执行群组
- `UnitRun` 是群组里每个执行单位做了什么
- `Artifact` 是留下了什么可承接成果

## 10. 面向当前仓库的最小落地顺序

如果后面进入实现阶段，建议顺序是：

1. 先给现有 `task` 补 `current_owner_lifeform_id`
2. 再引入 `assignment` 和 `handoff`
3. 再给现有执行事件抽出 `brood_run` 和 `unit_run`
4. 最后补 `artifact` 和 `governance_rule`

这样可以先把责任链立住，再慢慢把执行层和元治理层分开。

## 11. 本文结论

从这份文档开始，默认采用以下领域模型判断：

1. `Lifeform` 是常驻生命体，一等建模对象。
2. `Task` 的责任必须挂在 `Lifeform` 上。
3. `Assignment` 和 `Handoff` 必须分开建模。
4. `BroodRun` 和 `UnitRun` 属于执行层，不是人格层。
5. `Artifact` 是长期承接工作的必需对象。
6. `GovernanceRule` 当前先冻结，但数据层应预留。

