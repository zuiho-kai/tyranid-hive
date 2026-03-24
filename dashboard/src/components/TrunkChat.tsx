import { useEffect, useMemo, useRef } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { AtSign, ChevronDown, Send, Sparkles } from 'lucide-react'
import type { MissionDraft } from '../App'
import type { BusEvent, MissionMode, Synapse, Task } from '../api'
import {
  displaySynapse,
  displayTaskDescription,
  displayTaskTitle,
  formatMode,
  formatSpeaker,
  formatStage,
  formatState,
  getTaskBlockers,
  sanitizeText,
} from '../utils/display'

interface Props {
  selectedTask: Task | null
  events: BusEvent[]
  draft: MissionDraft
  synapses: Synapse[]
  submitting: boolean
  onDraftChange: Dispatch<SetStateAction<MissionDraft>>
  onSubmitMission: () => Promise<void>
}

interface ChatMessage {
  id: string
  ts: string
  speaker: string
  tone: 'user' | 'system' | 'progress'
  title: string
  content: string
}

const MODES: Array<{ id: MissionMode; label: string; note: string }> = [
  { id: 'auto', label: '自动路由', note: '默认模式，由系统自行判断怎么处理任务。' },
  { id: 'solo', label: '单代理', note: '由一个代理从头到尾处理。' },
  { id: 'trial', label: '对比评审', note: '让多个方案并排对比。' },
  { id: 'chain', label: '串行协作', note: '按顺序交给多个代理。' },
  { id: 'swarm', label: '并行协作', note: '把任务拆成并发子任务。' },
]

export default function TrunkChat({
  selectedTask,
  events,
  draft,
  synapses,
  submitting,
  onDraftChange,
  onSubmitMission,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const taskEvents = useMemo(
    () => (selectedTask ? events.filter(event => matchesTask(selectedTask, event)) : []),
    [events, selectedTask],
  )
  const messages = useMemo(
    () => buildMessages(selectedTask),
    [selectedTask],
  )
  const latestEvent = taskEvents[0] ?? null
  const currentStage = typeof latestEvent?.payload?.stage === 'string' ? latestEvent.payload.stage : 'idle'
  const blockers = getTaskBlockers(selectedTask)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages.length])

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-[var(--cl-border)] bg-[rgba(255,255,255,0.55)] px-6 py-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="text-[11px] uppercase tracking-[0.28em] text-[var(--cl-warning)]">当前任务</div>
            <h2 data-testid="selected-task-title" className="mt-2 truncate text-[30px] font-semibold tracking-[-0.04em] text-[var(--cl-text)]">
              {selectedTask ? displayTaskTitle(selectedTask) : '新任务'}
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--cl-muted)]">
              {selectedTask
                ? displayTaskDescription(selectedTask) || '这里展示该任务的主对话和关键进展。'
                : '先在底部输入需求，创建新任务后会在这里显示对话过程。'}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <StatusPill label="状态" value={selectedTask ? formatState(selectedTask.state) : '未开始'} testId="console-state" />
            <StatusPill label="模式" value={formatMode(selectedTask?.exec_mode ?? draft.mode)} />
            <StatusPill label="阶段" value={formatStage(currentStage)} testId="console-stage" />
            {blockers.length ? <StatusPill label="阻塞" value={`${blockers.length} 项`} testId="console-progress" /> : null}
          </div>
        </div>
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
        {messages.length === 0 ? (
          <HeroState />
        ) : (
          <div className="space-y-4" data-testid="transcript">
            {messages.map(message => {
              const userTone = message.tone === 'user'
              return (
                <div key={message.id} data-testid="chat-message" className={`flex ${userTone ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[min(100%,840px)] rounded-[28px] border px-4 py-3 shadow-[0_18px_36px_rgba(119,83,56,0.08)] ${bubbleClass(message.tone)}`}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-xs uppercase tracking-[0.18em] text-[var(--cl-dim)]">{message.speaker}</span>
                      <span className="text-[11px] text-[var(--cl-dim)]">{formatTs(message.ts)}</span>
                    </div>
                    <div className="mt-2 text-sm font-semibold text-[var(--cl-text)]">{message.title}</div>
                    <div className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[var(--cl-text)]">{message.content}</div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div className="border-t border-[var(--cl-border)] bg-[rgba(255,250,244,0.82)] px-6 py-5">
        <div className="rounded-[30px] border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] p-4 shadow-[0_20px_50px_rgba(119,83,56,0.08)]">
          <div className="mb-3 text-sm font-semibold text-[var(--cl-text)]">发起新任务</div>

          <textarea
            data-testid="mission-input"
            rows={5}
            value={draft.message}
            onChange={event => onDraftChange(current => ({ ...current, message: event.target.value }))}
            placeholder="直接输入你要解决的问题、要改的东西，或者期望结果。第一行会作为任务标题。"
            className="min-h-[148px] w-full resize-none rounded-[26px] border border-[var(--cl-border)] bg-[rgba(255,255,255,0.86)] px-4 py-3 text-sm leading-7 text-[var(--cl-text)] outline-none placeholder:text-[var(--cl-dim)]"
          />

          <details className="mt-4 rounded-[24px] border border-[var(--cl-border)] bg-[rgba(255,255,255,0.58)] px-4 py-3">
            <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-medium text-[var(--cl-text)]">
              <span>高级选项</span>
              <ChevronDown className="h-4 w-4 text-[var(--cl-dim)]" />
            </summary>

            <div className="mt-4 space-y-4">
              <div>
                <div className="mb-2 text-[11px] uppercase tracking-[0.2em] text-[var(--cl-dim)]">执行模式</div>
                <div className="flex flex-wrap gap-2">
                  {MODES.map(mode => (
                    <button
                      key={mode.id}
                      type="button"
                      data-testid={`mode-${mode.id}`}
                      onClick={() => onDraftChange(current => ({ ...current, mode: mode.id }))}
                      className={`rounded-full border px-3 py-2 text-xs transition ${
                        draft.mode === mode.id
                          ? 'border-[var(--cl-success)] bg-[var(--cl-success-soft)] text-[var(--cl-text)]'
                          : 'border-[var(--cl-border)] bg-[var(--cl-panel-strong)] text-[var(--cl-muted)] hover:border-[rgba(93,72,47,0.24)] hover:text-[var(--cl-text)]'
                      }`}
                      title={mode.note}
                    >
                      {mode.label}
                    </button>
                  ))}
                </div>
              </div>

              <ModeConfig draft={draft} onDraftChange={onDraftChange} synapses={synapses} />

              <div>
                <div className="mb-2 text-[11px] uppercase tracking-[0.2em] text-[var(--cl-dim)]">优先级</div>
                <select
                  data-testid="priority-select"
                  value={draft.priority}
                  onChange={event => onDraftChange(current => ({ ...current, priority: event.target.value }))}
                  className="w-full rounded-[18px] border border-[var(--cl-border)] bg-white px-3 py-2 text-sm text-[var(--cl-text)] outline-none"
                >
                  <option value="low">低</option>
                  <option value="normal">普通</option>
                  <option value="high">高</option>
                  <option value="critical">紧急</option>
                </select>
              </div>

              <div>
                <div className="mb-2 text-[11px] uppercase tracking-[0.2em] text-[var(--cl-dim)]">指定代理</div>
                <div className="flex flex-wrap gap-2">
                  {synapses.map(synapse => {
                    const display = displaySynapse(synapse)
                    return (
                      <button
                        key={synapse.id}
                        type="button"
                        onClick={() => onDraftChange(current => ({ ...current, message: appendMention(current.message, synapse.id) }))}
                        className="inline-flex items-center gap-1.5 rounded-full border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] px-3 py-1.5 text-xs text-[var(--cl-muted)] transition hover:border-[rgba(93,72,47,0.24)] hover:text-[var(--cl-text)]"
                      >
                        <AtSign className="h-3.5 w-3.5" />
                        {display.name}
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>
          </details>

          <div className="mt-4 flex justify-end">
            <button
              type="button"
              data-testid="launch-mission"
              onClick={() => void onSubmitMission()}
              disabled={submitting || !draft.message.trim()}
              className="flex min-w-[180px] items-center justify-center gap-2 rounded-[24px] border border-[var(--cl-success)] bg-[linear-gradient(135deg,var(--cl-success),var(--cl-primary))] px-4 py-4 text-sm font-semibold text-[#fffdf9] transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? <Sparkles className="h-4 w-4 animate-pulse" /> : <Send className="h-4 w-4" />}
              {submitting ? '提交中' : '创建任务'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function HeroState() {
  return (
    <div className="grid min-h-full place-items-center">
      <div className="max-w-2xl text-center">
        <h3 className="text-3xl font-semibold tracking-[-0.04em] text-[var(--cl-text)]">先创建一个任务</h3>
        <p className="mt-3 text-base leading-8 text-[var(--cl-muted)]">
          这里保留主对话，不再塞一堆流程视图。你只需要输入任务，系统自己判断后续怎么走。
        </p>
      </div>
    </div>
  )
}

function StatusPill({ label, value, testId }: { label: string; value: string; testId?: string }) {
  return (
    <div
      data-testid={testId}
      className="rounded-full border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] px-3 py-1.5 text-xs uppercase tracking-[0.14em] text-[var(--cl-muted)]"
    >
      <span className="text-[var(--cl-dim)]">{label}</span>
      <span className="ml-2 text-[var(--cl-text)]">{value}</span>
    </div>
  )
}

function ModeConfig({
  draft,
  onDraftChange,
  synapses,
}: {
  draft: MissionDraft
  onDraftChange: React.Dispatch<React.SetStateAction<MissionDraft>>
  synapses: Synapse[]
}) {
  if (draft.mode === 'trial') {
    return (
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <SelectField
          label="方案 A"
          value={draft.trialCandidates[0]}
          options={synapses}
          onChange={value => onDraftChange(current => ({ ...current, trialCandidates: [value, current.trialCandidates[1]] }))}
        />
        <SelectField
          label="方案 B"
          value={draft.trialCandidates[1]}
          options={synapses}
          onChange={value => onDraftChange(current => ({ ...current, trialCandidates: [current.trialCandidates[0], value] }))}
        />
      </div>
    )
  }

  if (draft.mode === 'chain') {
    return (
      <div className="space-y-3">
        {draft.chainStages.map((stage, index) => (
          <div key={`chain-${index}`} className="flex gap-3">
            <SelectField
              label={`步骤 ${index + 1}`}
              value={stage}
              options={synapses}
              onChange={value =>
                onDraftChange(current => ({
                  ...current,
                  chainStages: current.chainStages.map((item, itemIndex) => (itemIndex === index ? value : item)),
                }))
              }
            />
            {draft.chainStages.length > 2 ? (
              <button
                type="button"
                onClick={() =>
                  onDraftChange(current => ({
                    ...current,
                    chainStages: current.chainStages.filter((_, itemIndex) => itemIndex !== index),
                  }))
                }
                className="mt-6 rounded-[18px] border border-[var(--cl-border)] px-3 py-2 text-xs text-[var(--cl-muted)]"
              >
                删除
              </button>
            ) : null}
          </div>
        ))}
      </div>
    )
  }

  if (draft.mode === 'swarm') {
    return (
      <div className="space-y-3">
        {draft.swarmUnits.map((unit, index) => (
          <div key={`swarm-${index}`} className="grid gap-3 rounded-[22px] border border-[var(--cl-border)] bg-[rgba(255,255,255,0.66)] p-3 md:grid-cols-[180px_1fr_auto]">
            <SelectField
              label={`并行单元 ${index + 1}`}
              value={unit.synapse}
              options={synapses}
              onChange={value =>
                onDraftChange(current => ({
                  ...current,
                  swarmUnits: current.swarmUnits.map((item, itemIndex) =>
                    itemIndex === index ? { ...item, synapse: value } : item,
                  ),
                }))
              }
            />
            <label className="block">
              <span className="mb-1.5 block text-[11px] uppercase tracking-[0.2em] text-[var(--cl-dim)]">分工说明</span>
              <input
                data-testid={`swarm-message-${index}`}
                value={unit.message}
                onChange={event =>
                  onDraftChange(current => ({
                    ...current,
                    swarmUnits: current.swarmUnits.map((item, itemIndex) =>
                      itemIndex === index ? { ...item, message: event.target.value } : item,
                    ),
                  }))
                }
                className="w-full rounded-[18px] border border-[var(--cl-border)] bg-white px-3 py-2 text-sm text-[var(--cl-text)] outline-none"
              />
            </label>
            <button
              type="button"
              onClick={() =>
                onDraftChange(current => ({
                  ...current,
                  swarmUnits: current.swarmUnits.filter((_, itemIndex) => itemIndex !== index),
                }))
              }
              className="mt-6 rounded-[18px] border border-[var(--cl-border)] px-3 py-2 text-xs text-[var(--cl-muted)]"
            >
              删除
            </button>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="rounded-[22px] border border-[var(--cl-border)] bg-[rgba(255,255,255,0.66)] px-4 py-3 text-sm leading-7 text-[var(--cl-muted)]">
      {draft.mode === 'auto'
        ? '默认推荐自动路由。多数情况下你不需要手动指定模式。'
        : '单代理适合简单任务；如果后端判断信息不足，任务会自动进入等待补充。'}
    </div>
  )
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: Synapse[]
  onChange: (value: string) => void
}) {
  return (
    <label className="block flex-1">
      <span className="mb-1.5 block text-[11px] uppercase tracking-[0.2em] text-[var(--cl-dim)]">{label}</span>
      <select
        value={value}
        onChange={event => onChange(event.target.value)}
        className="w-full rounded-[18px] border border-[var(--cl-border)] bg-white px-3 py-2 text-sm text-[var(--cl-text)] outline-none"
      >
        {options.map(option => {
          const display = displaySynapse(option)
          return (
            <option key={option.id} value={option.id}>
              {display.name}
            </option>
          )
        })}
      </select>
    </label>
  )
}

function buildMessages(selectedTask: Task | null): ChatMessage[] {
  if (!selectedTask) return []

  const seed: ChatMessage = {
    id: `task-${selectedTask.id}`,
    ts: selectedTask.created_at,
    speaker: formatSpeaker(selectedTask.creator || 'user'),
    tone: 'user',
    title: displayTaskTitle(selectedTask),
    content: displayTaskDescription(selectedTask) || displayTaskTitle(selectedTask),
  }

  const flowMessages = selectedTask.flow_log.map((entry, index) => ({
    id: `flow-${index}-${entry.ts}`,
    ts: entry.ts,
    speaker: formatSpeaker(entry.agent || 'system'),
    tone: 'system' as const,
    title: `${formatState(entry.from ?? 'Start')} → ${formatState(entry.to)}`,
    content: sanitizeText(entry.reason, '状态发生变化'),
  }))

  const progressMessages = selectedTask.progress_log.map((entry, index) => ({
    id: `progress-${index}-${entry.ts}`,
    ts: entry.ts,
    speaker: formatSpeaker(entry.agent),
    tone: 'progress' as const,
    title: entry.agent === 'overmind' ? '主脑输出' : '执行输出',
    content: sanitizeText(entry.content, '[空输出]'),
  }))

  return [seed, ...flowMessages, ...progressMessages]
    .sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime())
}

function matchesTask(task: Task, event: BusEvent) {
  if (event.trace_id && task.trace_id && event.trace_id === task.trace_id) return true

  const payload = event.payload ?? {}
  return [payload.task_id, payload.parent_id, payload.task_uuid, payload.trace_id].includes(task.id)
    || payload.task_uuid === task.task_uuid
    || payload.trace_id === task.trace_id
}

function formatTs(value: string) {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function bubbleClass(tone: ChatMessage['tone']) {
  if (tone === 'user') return 'border-[var(--cl-border)] bg-[var(--cl-success-soft)]'
  if (tone === 'progress') return 'border-[var(--cl-border)] bg-[var(--cl-info-soft)]'
  return 'border-[var(--cl-border)] bg-[var(--cl-panel-strong)]'
}

function appendMention(message: string, synapseId: string) {
  const mention = `@${synapseId}`
  const trimmed = message.trimEnd()
  if (!trimmed) return `${mention} `
  if (trimmed.includes(mention)) return message
  return `${trimmed}\n${mention} `
}
