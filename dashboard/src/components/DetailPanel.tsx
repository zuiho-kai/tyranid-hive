import type { ReactNode } from 'react'
import type { MissionDraft } from '../App'
import type { BusEvent, Handoff, Lifeform, Synapse, Task } from '../api'
import {
  displayHandoffSource,
  displayHandoffTarget,
  displayTaskOwner,
  displayTaskTitle,
  displaySynapse,
  formatMode,
  formatPriority,
  formatSpeaker,
  formatStage,
  formatState,
  getTaskBlockers,
  getTaskRisks,
  getTaskSummary,
  sanitizeJson,
  sanitizeText,
} from '../utils/display'

interface Props {
  selectedTask: Task | null
  events: BusEvent[]
  handoffs: Handoff[]
  lifeforms: Lifeform[]
  draft: MissionDraft
  synapses: Synapse[]
}

interface ExecutionEntry {
  id: string
  ts: string
  speaker: string
  title: string
  content: string
  tone: 'state' | 'event' | 'progress'
}

export default function DetailPanel({
  selectedTask,
  events,
  handoffs,
  lifeforms,
  draft,
  synapses,
}: Props) {
  const latestEvent = events[0] ?? null
  const currentStage = typeof latestEvent?.payload?.stage === 'string'
    ? latestEvent.payload.stage
    : fallbackStage(selectedTask)
  const blockers = getTaskBlockers(selectedTask)
  const risks = getTaskRisks(selectedTask)
  const summary = getTaskSummary(selectedTask)
  const ownerName = selectedTask ? displayTaskOwner(selectedTask) : ''
  const entryName = selectedTask?.entry_lifeform?.display_name || selectedTask?.entry_lifeform?.name || '虫群主宰'
  const routeReason = selectedTask ? getRouteReason(selectedTask, synapses) : ''
  const splitItems = selectedTask ? getSplitItems(selectedTask, synapses) : []
  const executionEntries = selectedTask ? buildExecutionEntries(selectedTask, events, synapses) : []
  const rawEvents = events.slice(0, 30)

  return (
    <aside className="hidden h-full w-[380px] shrink-0 flex-col overflow-hidden rounded-[32px] border border-[var(--cl-border)] bg-[var(--cl-panel)] shadow-[0_20px_60px_rgba(119,83,56,0.10)] backdrop-blur-xl xl:flex">
      <div className="border-b border-[var(--cl-border)] px-5 pb-4 pt-5">
        <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--cl-warning)]">细节面板</div>
        <h2 className="mt-2 text-[26px] font-semibold tracking-[-0.03em] text-[var(--cl-text)]">
          {selectedTask ? '责任链与执行细节' : '默认配置'}
        </h2>
        <p className="mt-2 text-sm leading-6 text-[var(--cl-muted)]">
          {selectedTask
            ? '默认界面只看主线；这里展开负责人、交接原因、分化结构和原始事件。'
            : '选中任务后，这里会显示为什么这样处理，以及任务内部发生了什么。'}
        </p>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {selectedTask ? (
          <>
            <Panel title="概况">
              <MetricRow label="任务" value={displayTaskTitle(selectedTask)} />
              <MetricRow label="状态" value={formatState(selectedTask.state)} />
              <MetricRow label="阶段" value={formatStage(currentStage)} />
              <MetricRow label="模式" value={formatMode(selectedTask.exec_mode)} />
              <MetricRow label="优先级" value={formatPriority(selectedTask.priority)} />
              <MetricRow label="入口责任" value={sanitizeText(entryName, '虫群主宰')} />
              <MetricRow label="当前负责人" value={ownerName} />
            </Panel>

            <Panel title="当前责任">
              <MetricBlock
                title="为什么由她负责"
                content={selectedTask.current_assignment?.reason || routeReason || '当前没有记录更具体的责任原因。'}
              />
              {selectedTask.current_assignment?.scope ? (
                <MetricBlock title="处理范围" content={selectedTask.current_assignment.scope} />
              ) : null}
              {selectedTask.current_assignment?.expected_output ? (
                <MetricBlock title="期望产出" content={selectedTask.current_assignment.expected_output} />
              ) : null}
            </Panel>

            <Panel title="责任交接">
              {handoffs.length ? (
                <div className="space-y-3">
                  {handoffs.map(handoff => (
                    <div
                      key={handoff.id}
                      className="rounded-[20px] border border-[var(--cl-border)] bg-[rgba(255,255,255,0.72)] px-4 py-3"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-sm font-semibold text-[var(--cl-text)]">
                          {displayHandoffSource(handoff, lifeforms)} → {displayHandoffTarget(handoff, lifeforms)}
                        </div>
                        <div className="text-[11px] text-[var(--cl-dim)]">{formatTs(handoff.created_at || '')}</div>
                      </div>
                      <div className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[var(--cl-text)]">
                        {sanitizeText(handoff.reason, '未写明交接原因。')}
                      </div>
                      {handoff.scope ? (
                        <div className="mt-2 text-sm leading-6 text-[var(--cl-muted)]">
                          处理范围：{sanitizeText(handoff.scope, handoff.scope)}
                        </div>
                      ) : null}
                      {handoff.expected_output ? (
                        <div className="mt-1 text-sm leading-6 text-[var(--cl-muted)]">
                          期望产出：{sanitizeText(handoff.expected_output, handoff.expected_output)}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <Empty text="当前没有责任交接，说明任务还由同一位负责人推进。" />
              )}
            </Panel>

            <Panel title="为什么这样处理">
              {summary ? (
                <MetricBlock title="主宰摘要" content={summary} />
              ) : null}
              <MetricBlock
                title="路由判断"
                content={routeReason || '当前没有额外的路由说明。'}
              />
            </Panel>

            <Panel title="分化结构">
              {splitItems.length ? (
                <ListBlock items={splitItems} tone="neutral" />
              ) : (
                <Empty text="当前没有额外分化，按单线责任链推进。" />
              )}
            </Panel>

            <Panel title="阻塞与风险">
              {blockers.length ? (
                <ListBlock items={blockers} tone="danger" />
              ) : (
                <Empty text="当前没有阻塞项。" />
              )}
              {risks.length ? (
                <div className="mt-3">
                  <ListBlock items={risks} tone="warning" />
                </div>
              ) : null}
            </Panel>

            <Panel title="执行过程">
              {executionEntries.length ? (
                <details open className="rounded-[20px] border border-[var(--cl-border)] bg-[rgba(255,255,255,0.72)]">
                  <summary className="cursor-pointer list-none px-4 py-3 text-sm font-medium text-[var(--cl-text)]">
                    展开查看完整过程
                  </summary>
                  <div className="max-h-[420px] space-y-3 overflow-y-auto border-t border-[var(--cl-border)] px-4 py-4">
                    {executionEntries.map(entry => (
                      <div key={entry.id} className={`rounded-[18px] border px-3 py-3 ${entryClass(entry.tone)}`}>
                        <div className="flex items-center justify-between gap-3">
                          <span className="text-xs tracking-[0.06em] text-[var(--cl-dim)]">{entry.speaker}</span>
                          <span className="text-[11px] text-[var(--cl-dim)]">{formatTs(entry.ts)}</span>
                        </div>
                        <div className="mt-2 text-sm font-semibold text-[var(--cl-text)]">{entry.title}</div>
                        <div className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[var(--cl-text)]">{entry.content}</div>
                      </div>
                    ))}
                  </div>
                </details>
              ) : (
                <Empty text="还没有可展示的执行过程。" />
              )}
            </Panel>

            <Panel title="原始事件">
              {rawEvents.length ? (
                <details className="rounded-[20px] border border-[var(--cl-border)] bg-[rgba(255,255,255,0.72)]">
                  <summary className="cursor-pointer list-none px-4 py-3 text-sm font-medium text-[var(--cl-text)]">
                    展开查看事件账本
                  </summary>
                  <div className="max-h-[360px] space-y-3 overflow-y-auto border-t border-[var(--cl-border)] px-4 py-4">
                    {rawEvents.map(event => (
                      <div key={event.event_id} className="rounded-[18px] border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] px-3 py-3">
                        <div className="flex items-center justify-between gap-3">
                          <span className="text-xs tracking-[0.06em] text-[var(--cl-dim)]">{formatSpeaker(event.producer)}</span>
                          <span className="text-[11px] text-[var(--cl-dim)]">{formatTs(event.created_at)}</span>
                        </div>
                        <div className="mt-2 text-sm font-semibold text-[var(--cl-text)]">
                          {formatEventHeadline(event, synapses)}
                        </div>
                        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs leading-6 text-[var(--cl-muted)]">
                          {JSON.stringify(sanitizeJson(event.payload), null, 2)}
                        </pre>
                      </div>
                    ))}
                  </div>
                </details>
              ) : (
                <Empty text="当前没有可用的原始事件。" />
              )}
            </Panel>
          </>
        ) : (
          <>
            <Panel title="默认配置">
              <MetricRow label="模式" value={formatMode(draft.mode)} />
              <MetricRow label="优先级" value={formatPriority(draft.priority)} />
              <MetricRow label="可用执行核" value={String(synapses.length)} />
            </Panel>

            <Panel title="使用方式">
              <ListBlock
                items={[
                  '先在中间栏直接写任务，不用先挑角色。',
                  '默认只看责任主线，想看细节再展开。',
                  '右侧会解释为什么这样路由，以及内部执行发生了什么。',
                ]}
                tone="neutral"
              />
            </Panel>
          </>
        )}
      </div>
    </aside>
  )
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-[24px] border border-[var(--cl-border)] bg-[rgba(255,255,255,0.64)] p-4">
      <div className="mb-3 text-[11px] uppercase tracking-[0.16em] text-[var(--cl-dim)]">{title}</div>
      {children}
    </section>
  )
}

function MetricRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5">
      <span className="max-w-[42%] text-xs tracking-[0.04em] text-[var(--cl-dim)]">{label}</span>
      <span className={`max-w-[58%] text-right text-sm leading-6 text-[var(--cl-text)] ${mono ? 'font-mono text-[12px]' : ''}`}>
        {value}
      </span>
    </div>
  )
}

function MetricBlock({ title, content }: { title: string; content: string }) {
  return (
    <div className="rounded-[20px] border border-[var(--cl-border)] bg-[rgba(255,255,255,0.72)] px-4 py-3">
      <div className="text-xs tracking-[0.06em] text-[var(--cl-dim)]">{title}</div>
      <div className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[var(--cl-text)]">
        {sanitizeText(content, content)}
      </div>
    </div>
  )
}

function ListBlock({
  items,
  tone,
}: {
  items: string[]
  tone: 'danger' | 'warning' | 'neutral'
}) {
  const toneClass = tone === 'danger'
    ? 'border-[var(--cl-border)] bg-[var(--cl-danger-soft)]'
    : tone === 'warning'
      ? 'border-[var(--cl-border)] bg-[var(--cl-warning-soft)]'
      : 'border-[var(--cl-border)] bg-[var(--cl-panel-strong)]'

  return (
    <div className={`rounded-[20px] border px-4 py-3 ${toneClass}`}>
      <div className="space-y-2">
        {items.map(item => (
          <div key={item} className="text-sm leading-6 text-[var(--cl-text)]">
            {sanitizeText(item, item)}
          </div>
        ))}
      </div>
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return (
    <div className="rounded-[20px] border border-dashed border-[var(--cl-border)] bg-[rgba(255,255,255,0.48)] px-4 py-4 text-sm text-[var(--cl-dim)]">
      {text}
    </div>
  )
}

function entryClass(tone: ExecutionEntry['tone']) {
  if (tone === 'progress') return 'border-[var(--cl-border)] bg-[rgba(79,131,169,0.10)]'
  if (tone === 'event') return 'border-[var(--cl-border)] bg-[rgba(177,133,76,0.10)]'
  return 'border-[var(--cl-border)] bg-[var(--cl-panel-strong)]'
}

function fallbackStage(task: Task | null) {
  if (!task) return 'idle'
  if (task.state === 'Spawning') return 'routing'
  if (task.state === 'Executing' || task.state === 'Complete') return 'execution'
  if (task.state === 'Planning' || task.state === 'Reviewing' || task.state === 'WaitingInput') return 'overmind'
  return 'mission'
}

function getRouteReason(task: Task, synapses: Synapse[]) {
  const storedReason = readMetaString(task.meta, 'route_reason')
  if (storedReason) return storedReason

  if (task.current_assignment?.reason) return sanitizeText(task.current_assignment.reason, task.current_assignment.reason)
  if (task.state === 'WaitingInput') return '当前缺少关键输入，所以任务停在等待补充，而不是继续执行。'
  if (task.exec_mode === 'trial') return '这次任务存在多条可比较路径，所以进入对比评审。'
  if (task.exec_mode === 'chain') return '这次任务存在严格的线性依赖，所以采用串行协作。'
  if (task.exec_mode === 'swarm') return '这次任务可以拆成多个相对独立的执行单元，所以采用并行分化。'
  if (task.assignee_synapse) return `当前任务按单线推进，执行层会由${synapseName(task.assignee_synapse, synapses)}承接。`
  return '当前任务由虫群主宰先接住，再决定是否需要进一步委派。'
}

function getSplitItems(task: Task, synapses: Synapse[]) {
  const plan = Array.isArray(task.meta?.split_plan) ? task.meta.split_plan : []
  if (plan.length) {
    return plan
      .filter(item => item && typeof item === 'object')
      .map(item => {
        const kind = typeof item.type === 'string' ? item.type : 'step'
        const synapse = typeof item.synapse === 'string' ? synapseName(item.synapse, synapses) : '未指定对象'
        const order = typeof item.order === 'number' ? ` ${item.order}` : ''
        const message = typeof item.message === 'string' ? `，负责：${sanitizeText(item.message, item.message)}` : ''
        if (kind === 'candidate') return `候选执行者：${synapse}`
        if (kind === 'unit') return `并行单元${order}：${synapse}${message}`
        return `步骤${order}：${synapse}${message}`
      })
  }

  if (task.exec_mode === 'trial' && Array.isArray(task.meta?.trial_candidates)) {
    return task.meta.trial_candidates.map(candidate => `候选执行者：${synapseName(candidate, synapses)}`)
  }
  if (task.exec_mode === 'chain' && Array.isArray(task.meta?.chain_stages)) {
    return task.meta.chain_stages.map((stage, index) => `步骤 ${index + 1}：${synapseName(stage, synapses)}`)
  }
  if (task.exec_mode === 'swarm' && Array.isArray(task.meta?.swarm_units)) {
    return task.meta.swarm_units
      .filter(unit => unit && typeof unit === 'object')
      .map((unit, index) => {
        const synapse = typeof unit.synapse === 'string' ? synapseName(unit.synapse, synapses) : '未指定对象'
        const message = sanitizeText(unit.message, '未写明目标')
        return `并行单元 ${index + 1}：${synapse}，负责：${message}`
      })
  }

  return []
}

function buildExecutionEntries(task: Task, events: BusEvent[], synapses: Synapse[]): ExecutionEntry[] {
  const flowEntries: ExecutionEntry[] = task.flow_log.map((entry, index) => ({
    id: `flow-${index}-${entry.ts}`,
    ts: entry.ts,
    speaker: formatSpeaker(entry.agent || 'system'),
    title: `${formatState(entry.from ?? 'Start')} -> ${formatState(entry.to)}`,
    content: sanitizeText(entry.reason, '状态发生变化。'),
    tone: 'state',
  }))

  const progressEntries: ExecutionEntry[] = task.progress_log.map((entry, index) => ({
    id: `progress-${index}-${entry.ts}`,
    ts: entry.ts,
    speaker: formatSpeaker(entry.agent),
    title: entry.agent.includes('overmind') ? '主宰判断' : '执行输出',
    content: sanitizeText(entry.content, '[空输出]'),
    tone: 'progress',
  }))

  const interestingEventTypes = new Set([
    'task.dispatch.request',
    'task.mode.selected',
    'task.execution.started',
    'task.execution.completed',
    'task.execution.failed',
    'task.stage.started',
    'task.stage.completed',
    'task.stage.failed',
    'agent.dispatch.start',
  ])

  const eventEntries: ExecutionEntry[] = events
    .filter(event => interestingEventTypes.has(event.event_type))
    .map(event => ({
      id: `event-${event.event_id}`,
      ts: event.created_at,
      speaker: formatSpeaker(event.producer),
      title: formatEventHeadline(event, synapses),
      content: formatEventContent(event, synapses),
      tone: 'event',
    }))

  return [...flowEntries, ...eventEntries, ...progressEntries]
    .sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime())
}

function formatEventHeadline(event: BusEvent, synapses: Synapse[]) {
  const synapse = typeof event.payload?.synapse === 'string' ? synapseName(event.payload.synapse, synapses) : ''
  const stage = typeof event.payload?.stage === 'string' ? sanitizeText(event.payload.stage, event.payload.stage) : ''

  switch (event.event_type) {
    case 'task.dispatch.request':
      return synapse ? `派发给${synapse}` : '创建派发请求'
    case 'task.mode.selected':
      return '确定执行模式'
    case 'task.execution.started':
      return '开始执行'
    case 'task.execution.completed':
      return '执行完成'
    case 'task.execution.failed':
      return '执行失败'
    case 'task.stage.started':
      return stage ? `${stage}开始` : '阶段开始'
    case 'task.stage.completed':
      return stage ? `${stage}完成` : '阶段完成'
    case 'task.stage.failed':
      return stage ? `${stage}失败` : '阶段失败'
    case 'agent.dispatch.start':
      return synapse ? `${synapse}已接手` : '执行者开始处理'
    default:
      return sanitizeText(event.event_type, event.event_type)
  }
}

function formatEventContent(event: BusEvent, synapses: Synapse[]) {
  const payload = event.payload ?? {}
  const mode = typeof payload.mode === 'string' ? payload.mode : ''
  const synapse = typeof payload.synapse === 'string' ? synapseName(payload.synapse, synapses) : ''
  const stage = typeof payload.stage === 'string' ? sanitizeText(payload.stage, payload.stage) : ''
  const source = typeof payload.source === 'string' ? sanitizeText(payload.source, payload.source) : ''
  const nextState = typeof payload.next_state === 'string' ? formatState(payload.next_state) : ''
  const winner = typeof payload.winner === 'string' ? synapseName(payload.winner, synapses) : ''

  switch (event.event_type) {
    case 'task.dispatch.request':
      return synapse
        ? `目标执行者：${synapse}${nextState ? `，完成后进入${nextState}` : ''}`
        : '已经创建新的派发请求。'
    case 'task.mode.selected':
      return `模式：${formatMode(mode)}${source ? `，来源：${source}` : ''}`
    case 'task.execution.started':
      return mode ? `执行模式：${formatMode(mode)}` : '开始进入执行阶段。'
    case 'task.execution.completed':
      return winner ? `执行完成，当前结果来自${winner}。` : '执行阶段正常结束。'
    case 'task.execution.failed':
      return '执行阶段结束，但存在失败。'
    case 'task.stage.started':
      return stage ? `阶段：${stage}` : '阶段开始。'
    case 'task.stage.completed':
      return winner ? `阶段完成，当前胜出结果：${winner}` : '阶段完成。'
    case 'task.stage.failed':
      return '该阶段失败或提前结束。'
    case 'agent.dispatch.start':
      return synapse ? `${synapse}已开始处理。` : '执行者已开始处理。'
    default:
      return JSON.stringify(sanitizeJson(payload), null, 2)
  }
}

function synapseName(id: unknown, synapses: Synapse[]) {
  if (typeof id !== 'string') return '未命名对象'
  const synapse = synapses.find(item => item.id === id)
  return synapse ? displaySynapse(synapse).name : sanitizeText(id, id)
}

function readMetaString(meta: Record<string, unknown> | undefined, key: string) {
  const value = meta?.[key]
  return typeof value === 'string' ? sanitizeText(value, value) : ''
}

function formatTs(value: string) {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}
