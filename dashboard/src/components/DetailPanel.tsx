import type { ReactNode } from 'react'
import type { MissionDraft } from '../App'
import type { BusEvent, Synapse, Task } from '../api'
import {
  displaySynapse,
  displayTaskDescription,
  displayTaskTitle,
  formatMode,
  formatPriority,
  formatSpeaker,
  formatStage,
  formatState,
  getTaskBlockers,
  getTaskRisks,
  getTaskSummary,
  sanitizeText,
} from '../utils/display'

interface Props {
  selectedTask: Task | null
  events: BusEvent[]
  draft: MissionDraft
  synapses: Synapse[]
}

export default function DetailPanel({
  selectedTask,
  events,
  draft,
  synapses,
}: Props) {
  const taskEvents = selectedTask
    ? events.filter(event => event.trace_id === selectedTask.trace_id || event.payload?.task_id === selectedTask.id)
    : []
  const latestEvent = taskEvents[0] ?? null
  const currentStage = typeof latestEvent?.payload?.stage === 'string' ? latestEvent.payload.stage : 'idle'
  const blockers = getTaskBlockers(selectedTask)
  const risks = getTaskRisks(selectedTask)
  const summary = getTaskSummary(selectedTask)
  const assignee = synapses.find(synapse => synapse.id === selectedTask?.assignee_synapse) ?? null
  const latestProgress = selectedTask?.progress_log.at(-1) ?? null

  return (
    <aside className="hidden h-full w-[320px] shrink-0 flex-col overflow-hidden rounded-[32px] border border-[var(--cl-border)] bg-[var(--cl-panel)] shadow-[0_20px_60px_rgba(119,83,56,0.10)] backdrop-blur-xl xl:flex">
      <div className="border-b border-[var(--cl-border)] px-5 pb-4 pt-5">
        <div className="text-[11px] uppercase tracking-[0.26em] text-[var(--cl-warning)]">侧边信息</div>
        <h2 className="mt-2 text-[28px] font-semibold tracking-[-0.03em] text-[var(--cl-text)]">
          {selectedTask ? '任务概览' : '使用说明'}
        </h2>
        <p className="mt-2 text-sm leading-6 text-[var(--cl-muted)]">
          {selectedTask
            ? '这里只放必要信息：状态、阻塞和最近更新。'
            : '先在左侧选择任务，或者在中间底部直接创建新任务。'}
        </p>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {selectedTask ? (
          <>
            <Panel title="当前状态">
              <MetricRow label="任务" value={displayTaskTitle(selectedTask)} />
              <MetricRow label="状态" value={formatState(selectedTask.state)} />
              <MetricRow label="模式" value={formatMode(selectedTask.exec_mode)} />
              <MetricRow label="优先级" value={formatPriority(selectedTask.priority)} />
              <MetricRow label="阶段" value={formatStage(currentStage)} />
              <MetricRow label="负责人" value={assignee ? displaySynapse(assignee).name : '未分配'} />
              <MetricRow label="更新时间" value={formatTs(selectedTask.updated_at)} />
            </Panel>

            <Panel title="阻塞与风险">
              {summary ? (
                <div className="rounded-[22px] border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] px-4 py-3 text-sm leading-7 text-[var(--cl-text)]">
                  {summary}
                </div>
              ) : null}
              {blockers.length ? (
                <ListBlock title="等待补充" items={blockers} tone="danger" />
              ) : null}
              {risks.length ? (
                <ListBlock title="风险提示" items={risks} tone="warning" />
              ) : null}
              {!summary && blockers.length === 0 && risks.length === 0 ? (
                <Empty text="当前没有明确阻塞或风险。" />
              ) : null}
            </Panel>

            <Panel title="最近更新">
              <MetricRow label="任务 ID" value={selectedTask.id} mono />
              <MetricRow label="说明" value={displayTaskDescription(selectedTask) || '暂无说明'} />
              {latestProgress ? (
                <>
                  <MetricRow label="最近输出" value={formatSpeaker(latestProgress.agent)} />
                  <div className="mt-3 rounded-[22px] border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] px-4 py-3 text-sm leading-7 text-[var(--cl-text)]">
                    {sanitizeText(latestProgress.content, '[空输出]')}
                  </div>
                </>
              ) : latestEvent ? (
                <>
                  <MetricRow label="最近事件" value={formatSpeaker(latestEvent.producer)} />
                  <div className="mt-3 rounded-[22px] border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] px-4 py-3 text-sm leading-7 text-[var(--cl-text)]">
                    最近有系统事件更新。
                  </div>
                </>
              ) : (
                <Empty text="还没有新的执行输出。" />
              )}
            </Panel>
          </>
        ) : (
          <>
            <Panel title="怎么用">
              <ListBlock
                title="基础操作"
                items={[
                  '左侧选择任务，查看主对话。',
                  '中间区域只看任务主线和关键输出。',
                  '底部输入框用于创建新任务。',
                  '高级模式都收进了“高级选项”，默认不用碰。',
                ]}
                tone="neutral"
              />
            </Panel>

            <Panel title="当前默认值">
              <MetricRow label="模式" value={formatMode(draft.mode)} />
              <MetricRow label="优先级" value={formatPriority(draft.priority)} />
              <MetricRow label="可用代理" value={String(synapses.length)} />
            </Panel>
          </>
        )}
      </div>
    </aside>
  )
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-[28px] border border-[var(--cl-border)] bg-[rgba(255,255,255,0.64)] p-4">
      <div className="mb-3 text-[11px] uppercase tracking-[0.2em] text-[var(--cl-dim)]">{title}</div>
      {children}
    </section>
  )
}

function MetricRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5">
      <span className="max-w-[40%] text-xs uppercase tracking-[0.14em] text-[var(--cl-dim)]">{label}</span>
      <span className={`max-w-[60%] text-right text-sm leading-6 text-[var(--cl-text)] ${mono ? 'font-mono text-[12px]' : ''}`}>{value}</span>
    </div>
  )
}

function ListBlock({
  title,
  items,
  tone,
}: {
  title: string
  items: string[]
  tone: 'danger' | 'warning' | 'neutral'
}) {
  const toneClass = tone === 'danger'
    ? 'border-[var(--cl-border)] bg-[var(--cl-danger-soft)]'
    : tone === 'warning'
      ? 'border-[var(--cl-border)] bg-[var(--cl-warning-soft)]'
      : 'border-[var(--cl-border)] bg-[var(--cl-panel-strong)]'

  return (
    <div className={`rounded-[22px] border px-4 py-3 ${toneClass}`}>
      <div className="mb-2 text-[11px] uppercase tracking-[0.2em] text-[var(--cl-dim)]">{title}</div>
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
    <div className="rounded-[22px] border border-dashed border-[var(--cl-border)] bg-[rgba(255,255,255,0.48)] px-4 py-4 text-sm text-[var(--cl-dim)]">
      {text}
    </div>
  )
}

function formatTs(value: string) {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
