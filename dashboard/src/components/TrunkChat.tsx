import { useEffect, useMemo, useRef } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { Plus, Send, Sparkles } from 'lucide-react'
import type { ChannelKey, MissionDraft } from '../App'
import type { BusEvent, MissionMode, Synapse, Task } from '../api'

interface Props {
  selectedTask: Task | null
  selectedChannel: ChannelKey
  events: BusEvent[]
  draft: MissionDraft
  synapses: Synapse[]
  submitting: boolean
  onDraftChange: Dispatch<SetStateAction<MissionDraft>>
  onSubmitMission: () => Promise<void>
  onSelectChannel: (channel: ChannelKey) => void
}

interface ChatMessage {
  id: string
  ts: string
  speaker: string
  tone: 'user' | 'system' | 'progress' | 'raw'
  title: string
  content: string
  detail?: string
}

const MODES: Array<{ id: MissionMode; label: string; note: string }> = [
  { id: 'auto', label: 'Auto', note: 'Let the hive choose the route' },
  { id: 'solo', label: 'Solo', note: 'Single Codex executor' },
  { id: 'trial', label: 'Trial', note: 'A/B race and choose the winner' },
  { id: 'chain', label: 'Chain', note: 'Sequential handoff between synapses' },
  { id: 'swarm', label: 'Swarm', note: 'Parallel units with separate asks' },
]

export default function TrunkChat({
  selectedTask,
  selectedChannel,
  events,
  draft,
  synapses,
  submitting,
  onDraftChange,
  onSubmitMission,
  onSelectChannel,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const taskEvents = useMemo(
    () => (selectedTask ? events.filter(event => matchesTask(selectedTask, event)) : []),
    [events, selectedTask],
  )
  const messages = useMemo(
    () => buildMessages(selectedTask, events, selectedChannel),
    [events, selectedChannel, selectedTask],
  )
  const latestEvent = taskEvents[0] ?? null
  const currentStage = typeof latestEvent?.payload?.stage === 'string' ? latestEvent.payload.stage : 'idle'
  const currentState = selectedTask?.state ?? 'Draft'
  const currentMode = selectedTask?.exec_mode ?? draft.mode
  const progressCount = selectedTask?.progress_log.length ?? 0

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages.length])

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-white/10 bg-[rgba(255,255,255,0.02)] px-6 py-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-[11px] uppercase tracking-[0.34em] text-[#a895c2]">Mission Console</div>
            <h2 data-testid="selected-task-title" className="mt-2 text-[30px] font-semibold tracking-[-0.04em] text-[#f8f3ed]">
              {selectedTask ? selectedTask.title : 'Submit the next mission'}
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[#a79bb8]">
              Task from the center pane, watch the route unfold, then drill into Trial, Chain, Swarm, or Ledger without losing the main thread.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <StatusPill label="Mode" value={currentMode} />
              <StatusPill label="State" value={currentState} testId="console-state" />
              <StatusPill label="Stage" value={currentStage} testId="console-stage" />
              <StatusPill label="Progress" value={String(progressCount)} testId="console-progress" />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {(['trunk', 'trial', 'chain', 'swarm', 'ledger'] as ChannelKey[]).map(channel => (
              <button
                key={channel}
                type="button"
                data-testid={`console-channel-${channel}`}
                onClick={() => onSelectChannel(channel)}
                className={`rounded-full border px-3 py-1.5 text-xs uppercase tracking-[0.2em] transition ${
                  selectedChannel === channel
                    ? 'border-[#b498ef] bg-[rgba(180,152,239,0.18)] text-[#f8f3ed]'
                    : 'border-white/10 bg-white/[0.04] text-[#9185a6] hover:border-white/20 hover:text-[#f8f3ed]'
                }`}
              >
                {channel}
              </button>
            ))}
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
                  <div className={`max-w-[min(100%,820px)] rounded-[26px] border px-4 py-3 shadow-[0_20px_40px_rgba(0,0,0,0.18)] ${
                    bubbleClass(message.tone)
                  }`}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-xs uppercase tracking-[0.22em] text-[#cabee0]">{message.speaker}</span>
                      <span className="text-[11px] text-[#9488a7]">{formatTs(message.ts)}</span>
                    </div>
                    <div className="mt-2 text-sm font-semibold text-[#f8f3ed]">{message.title}</div>
                    <div className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[#dfd8e8]">{message.content}</div>
                    {message.detail ? (
                      <pre className="mt-3 overflow-x-auto rounded-2xl border border-white/10 bg-black/20 p-3 text-[11px] leading-6 text-[#afa5bf]">
                        {message.detail}
                      </pre>
                    ) : null}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div className="border-t border-white/10 bg-[rgba(8,7,12,0.86)] px-6 py-5">
        <div className="rounded-[28px] border border-white/10 bg-[rgba(255,255,255,0.04)] p-4 shadow-[0_20px_50px_rgba(0,0,0,0.28)]">
          <div className="mb-3 flex flex-wrap gap-2">
            {MODES.map(mode => (
              <button
                key={mode.id}
                type="button"
                data-testid={`mode-${mode.id}`}
                onClick={() => onDraftChange(current => ({ ...current, mode: mode.id }))}
                className={`rounded-full border px-3 py-2 text-left text-xs transition ${
                  draft.mode === mode.id
                    ? 'border-[#68cf95] bg-[rgba(104,207,149,0.16)] text-[#f8f3ed]'
                    : 'border-white/10 bg-white/[0.04] text-[#9d90b1] hover:border-white/20 hover:text-[#f8f3ed]'
                }`}
                title={mode.note}
              >
                {mode.label}
              </button>
            ))}
          </div>

          <ModeConfig draft={draft} onDraftChange={onDraftChange} synapses={synapses} />

          <div className="mt-4 flex gap-3">
            <textarea
              data-testid="mission-input"
              rows={4}
              value={draft.message}
              onChange={event => onDraftChange(current => ({ ...current, message: event.target.value }))}
              placeholder="Describe the task exactly as you would assign it to an AI team. The first meaningful line becomes the mission title."
              className="min-h-[124px] flex-1 resize-none rounded-[24px] border border-white/10 bg-[rgba(0,0,0,0.22)] px-4 py-3 text-sm leading-7 text-[#f8f3ed] outline-none placeholder:text-[#6f6480]"
            />

            <div className="flex w-[180px] shrink-0 flex-col gap-3">
              <div className="rounded-[24px] border border-white/10 bg-black/20 px-4 py-3">
                <div className="text-[11px] uppercase tracking-[0.22em] text-[#8d7fa6]">Priority</div>
                <select
                  data-testid="priority-select"
                  value={draft.priority}
                  onChange={event => onDraftChange(current => ({ ...current, priority: event.target.value }))}
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-white/[0.05] px-3 py-2 text-sm text-[#f8f3ed] outline-none"
                >
                  <option value="low">Low</option>
                  <option value="normal">Normal</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>

              <button
                type="button"
                data-testid="launch-mission"
                onClick={() => void onSubmitMission()}
                disabled={submitting || !draft.message.trim()}
                className="flex flex-1 items-center justify-center gap-2 rounded-[24px] border border-[#68cf95]/30 bg-[linear-gradient(135deg,rgba(104,207,149,0.94),rgba(123,166,255,0.8))] px-4 py-4 text-sm font-semibold text-[#09110d] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitting ? <Sparkles className="h-4 w-4 animate-pulse" /> : <Send className="h-4 w-4" />}
                {submitting ? 'Dispatching' : 'Launch Mission'}
              </button>
            </div>
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
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full border border-white/10 bg-[rgba(255,255,255,0.05)] text-[#b9aaee]">
          <Sparkles className="h-7 w-7" />
        </div>
        <h3 className="mt-5 text-3xl font-semibold tracking-[-0.04em] text-[#f8f3ed]">Task the hive from here</h3>
        <p className="mt-3 text-base leading-8 text-[#a79bb8]">
          Pick a mode, write the assignment in plain language, and this console will turn the event bus into an observable mission transcript.
        </p>
      </div>
    </div>
  )
}

function StatusPill({ label, value, testId }: { label: string; value: string; testId?: string }) {
  return (
    <div
      data-testid={testId}
      className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs uppercase tracking-[0.18em] text-[#d6cce7]"
    >
      <span className="text-[#8d7fa6]">{label}</span>
      <span className="ml-2 text-[#f8f3ed]">{value}</span>
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
          label="Candidate A"
          value={draft.trialCandidates[0]}
          options={synapses}
          onChange={value => onDraftChange(current => ({ ...current, trialCandidates: [value, current.trialCandidates[1]] }))}
        />
        <SelectField
          label="Candidate B"
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
              label={`Stage ${index + 1}`}
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
                className="mt-6 rounded-2xl border border-white/10 px-3 py-2 text-xs text-[#cdbfe2]"
              >
                Remove
              </button>
            ) : null}
          </div>
        ))}
        <button
          type="button"
          onClick={() => onDraftChange(current => ({ ...current, chainStages: [...current.chainStages, current.chainStages.at(-1) ?? 'code-expert'] }))}
          className="inline-flex items-center gap-2 rounded-2xl border border-white/10 px-3 py-2 text-xs text-[#cdbfe2]"
        >
          <Plus className="h-3.5 w-3.5" />
          Add stage
        </button>
      </div>
    )
  }

  if (draft.mode === 'swarm') {
    return (
      <div className="space-y-3">
        {draft.swarmUnits.map((unit, index) => (
          <div key={`swarm-${index}`} className="grid gap-3 rounded-[22px] border border-white/10 bg-black/10 p-3 md:grid-cols-[180px_1fr_auto]">
            <SelectField
              label={`Unit ${index + 1}`}
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
              <span className="mb-1.5 block text-[11px] uppercase tracking-[0.22em] text-[#8d7fa6]">Unit assignment</span>
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
                className="w-full rounded-2xl border border-white/10 bg-white/[0.05] px-3 py-2 text-sm text-[#f8f3ed] outline-none"
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
              className="mt-6 rounded-2xl border border-white/10 px-3 py-2 text-xs text-[#cdbfe2]"
            >
              Remove
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() =>
            onDraftChange(current => ({
              ...current,
              swarmUnits: [...current.swarmUnits, { synapse: 'code-expert', message: 'Add another independent unit' }],
            }))
          }
          className="inline-flex items-center gap-2 rounded-2xl border border-white/10 px-3 py-2 text-xs text-[#cdbfe2]"
        >
          <Plus className="h-3.5 w-3.5" />
          Add unit
        </button>
      </div>
    )
  }

  return (
    <div className="rounded-[22px] border border-white/10 bg-black/10 px-4 py-3 text-sm leading-7 text-[#a79bb8]">
      {draft.mode === 'auto'
        ? 'Auto mode lets the backend select the route after the mission enters the hive.'
        : 'Solo mode sends the task through a single executor after the routing gate.'}
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
      <span className="mb-1.5 block text-[11px] uppercase tracking-[0.22em] text-[#8d7fa6]">{label}</span>
      <select
        value={value}
        onChange={event => onChange(event.target.value)}
        className="w-full rounded-2xl border border-white/10 bg-white/[0.05] px-3 py-2 text-sm text-[#f8f3ed] outline-none"
      >
        {options.map(option => (
          <option key={option.id} value={option.id}>
            {option.name}
          </option>
        ))}
      </select>
    </label>
  )
}

function buildMessages(selectedTask: Task | null, events: BusEvent[], channel: ChannelKey): ChatMessage[] {
  if (!selectedTask) return []

  const taskEvents = events.filter(event => matchesTask(selectedTask, event))
  const progressMessages = selectedTask.progress_log.map((entry, index) => ({
    id: `progress-${index}-${entry.ts}`,
    ts: entry.ts,
    speaker: entry.agent,
    tone: channel === 'ledger' ? 'raw' as const : 'progress' as const,
    title: 'Progress',
    content: entry.content,
  }))

  const flowMessages = selectedTask.flow_log.map((entry, index) => ({
    id: `flow-${index}-${entry.ts}`,
    ts: entry.ts,
    speaker: entry.agent || 'system',
    tone: channel === 'ledger' ? 'raw' as const : 'system' as const,
    title: `${entry.from ?? 'Start'} → ${entry.to}`,
    content: entry.reason || 'State transition',
  }))

  const eventMessages = taskEvents
    .filter(event => eventFitsChannel(event, channel))
    .map(event => ({
      id: event.event_id,
      ts: event.created_at,
      speaker: event.producer,
      tone: channel === 'ledger' ? 'raw' as const : deriveTone(event.event_type),
      title: event.event_type,
      content: summarizeEvent(event),
      detail: channel === 'ledger' ? JSON.stringify(event.payload, null, 2) : undefined,
    }))

  const seed: ChatMessage[] = [
    {
      id: `task-${selectedTask.id}`,
      ts: selectedTask.created_at,
      speaker: selectedTask.creator || 'user',
      tone: 'user',
      title: selectedTask.title,
      content: selectedTask.description?.trim() || selectedTask.title,
    },
  ]

  return [...seed, ...flowMessages, ...progressMessages, ...eventMessages]
    .sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime())
}

function eventFitsChannel(event: BusEvent, channel: ChannelKey) {
  const stage = typeof event.payload?.stage === 'string' ? event.payload.stage : ''

  if (channel === 'ledger') return true
  if (channel === 'trial') return stage.startsWith('trial') || event.topic === 'trial.closed'
  if (channel === 'chain') return stage.startsWith('chain')
  if (channel === 'swarm') return stage.startsWith('swarm')
  if (channel === 'trunk') return !stage.startsWith('chain') && !stage.startsWith('swarm') && !stage.startsWith('trial')
  return true
}

function summarizeEvent(event: BusEvent) {
  const payload = event.payload ?? {}
  if (event.event_type === 'task.submitted') {
    return `${payload.title ?? 'Mission'} entered the hive in ${payload.mode ?? 'auto'} mode.`
  }
  if (event.event_type === 'task.mode.selected') {
    return `Mode selected: ${payload.mode ?? 'unknown'} (${payload.source ?? 'system'}).`
  }
  if (event.event_type === 'task.analysis.started') {
    return 'Overmind is analyzing the task.'
  }
  if (event.event_type === 'task.analysis.completed') {
    return 'Overmind finished analysis and routing output.'
  }
  if (event.event_type === 'task.execution.started') {
    return `Execution started in ${payload.mode ?? 'unknown'} mode.`
  }
  if (event.event_type === 'task.execution.completed') {
    return `Execution completed in ${payload.mode ?? 'unknown'} mode.`
  }
  if (event.event_type === 'task.execution.failed') {
    return `Execution failed in ${payload.mode ?? 'unknown'} mode.`
  }
  if (event.event_type === 'task.stage.started') {
    return `Stage ${payload.stage ?? event.payload?.stage ?? 'unknown'} started.`
  }
  if (event.event_type === 'task.stage.completed') {
    return `Stage ${payload.stage ?? event.payload?.stage ?? 'unknown'} completed.`
  }
  if (event.event_type === 'task.stage.failed') {
    return `Stage ${payload.stage ?? event.payload?.stage ?? 'unknown'} failed.`
  }
  return event.event_type
}

function deriveTone(eventType: string): ChatMessage['tone'] {
  if (eventType.includes('failed')) return 'raw'
  if (eventType.includes('stage')) return 'progress'
  return 'system'
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
  if (tone === 'user') return 'border-[#68cf95]/30 bg-[rgba(104,207,149,0.12)]'
  if (tone === 'progress') return 'border-[#8cb7ff]/22 bg-[rgba(93,128,214,0.14)]'
  if (tone === 'raw') return 'border-[#d89292]/20 bg-[rgba(130,42,52,0.18)]'
  return 'border-white/10 bg-[rgba(255,255,255,0.04)]'
}
