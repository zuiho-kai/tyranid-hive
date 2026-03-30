import { useEffect, useMemo, useRef, useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { PanelRight, PanelRightClose, Send, Sparkles } from 'lucide-react'
import type { MissionDraft } from '../App'
import type { BusEvent, Handoff, Lifeform, Task } from '../api'
import {
  displayHandoffSource,
  displayHandoffTarget,
  displayLifeformName,
  displayTaskDescription,
  displayTaskOwner,
  displayTaskTitle,
  formatSpeaker,
  formatStage,
  formatState,
  getTaskBlockers,
  sanitizeText,
} from '../utils/display'

interface Props {
  selectedTask: Task | null
  events: BusEvent[]
  handoffs: Handoff[]
  lifeforms: Lifeform[]
  draft: MissionDraft
  submitting: boolean
  showDetail: boolean
  showDetailToggle: boolean
  onDraftChange: Dispatch<SetStateAction<MissionDraft>>
  onSubmitMission: () => Promise<void>
  onToggleDetail: () => void
}

interface ChatMessage {
  id: string
  ts: string
  speaker: string
  tone: 'user' | 'sovereign' | 'handoff' | 'progress' | 'system'
  title: string
  content: string
}

export default function TrunkChat({
  selectedTask,
  events,
  handoffs,
  lifeforms,
  draft,
  submitting,
  showDetail,
  showDetailToggle,
  onDraftChange,
  onSubmitMission,
  onToggleDetail,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [composerExpanded, setComposerExpanded] = useState(!selectedTask)
  const messages = useMemo(
    () => buildMessages(selectedTask, handoffs, lifeforms),
    [handoffs, lifeforms, selectedTask],
  )
  const latestEvent = events[0] ?? null
  const currentStage = typeof latestEvent?.payload?.stage === 'string'
    ? latestEvent.payload.stage
    : fallbackStage(selectedTask)
  const blockers = getTaskBlockers(selectedTask)
  const ownerName = selectedTask ? displayTaskOwner(selectedTask) : ''

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages.length])

  useEffect(() => {
    if (!selectedTask) {
      setComposerExpanded(true)
    } else if (!draft.message.trim()) {
      setComposerExpanded(false)
    }
  }, [draft.message, selectedTask])

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-[var(--cl-border)] bg-[rgba(255,255,255,0.55)] px-6 py-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--cl-warning)]">
              {selectedTask ? '任务主线' : '新建任务'}
            </div>
            <h2
              data-testid="selected-task-title"
              className="mt-2 max-w-4xl text-[30px] font-semibold leading-[1.15] tracking-[-0.04em] text-[var(--cl-text)]"
            >
              {selectedTask ? displayTaskTitle(selectedTask) : '把问题写清楚，虫群主宰会先接住'}
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--cl-muted)]">
              {selectedTask
                ? displayTaskDescription(selectedTask) || '这里只显示责任主线，不把所有内部执行细节都堆进来。'
                : '直接描述你要解决的问题、现在的情况和期望结果。默认自动路由，不需要先选代理。'}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {selectedTask ? (
              <>
                <StatusPill label="当前负责人" value={ownerName} testId="console-owner" />
                <StatusPill label="状态" value={formatState(selectedTask.state)} testId="console-state" />
                <StatusPill label="阶段" value={formatStage(currentStage)} testId="console-stage" />
                {blockers.length ? (
                  <StatusPill label="待补充" value={`${blockers.length} 项`} testId="console-progress" />
                ) : null}
              </>
            ) : null}
            {showDetailToggle ? (
              <button
                type="button"
                onClick={onToggleDetail}
                className="inline-flex items-center gap-2 rounded-full border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] px-3 py-2 text-sm text-[var(--cl-text)]"
              >
                {showDetail ? <PanelRightClose className="h-4 w-4" /> : <PanelRight className="h-4 w-4" />}
                {showDetail ? '收起细节' : '查看细节'}
              </button>
            ) : null}
          </div>
        </div>
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
        {messages.length === 0 ? (
          <EmptyThreadState />
        ) : (
          <div className="space-y-3" data-testid="transcript">
            {messages.map(message => (
              <div
                key={message.id}
                data-testid="chat-message"
                className={`rounded-[24px] border px-4 py-3 shadow-[0_12px_28px_rgba(119,83,56,0.06)] ${bubbleClass(message.tone)}`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs tracking-[0.08em] text-[var(--cl-dim)]">{message.speaker}</span>
                  <span className="text-[11px] text-[var(--cl-dim)]">{formatTs(message.ts)}</span>
                </div>
                <div className="mt-2 text-sm font-semibold text-[var(--cl-text)]">{message.title}</div>
                <div className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[var(--cl-text)]">{message.content}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="border-t border-[var(--cl-border)] bg-[rgba(255,250,244,0.82)] px-6 py-5">
        {composerExpanded ? (
          <div className="rounded-[30px] border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] p-4 shadow-[0_20px_50px_rgba(119,83,56,0.08)]">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="text-sm font-semibold text-[var(--cl-text)]">发起新任务</div>
              <div className="flex items-center gap-3">
                <div className="text-xs text-[var(--cl-dim)]">默认自动路由</div>
                {selectedTask ? (
                  <button
                    type="button"
                    onClick={() => setComposerExpanded(false)}
                    className="text-xs text-[var(--cl-dim)]"
                  >
                    收起
                  </button>
                ) : null}
              </div>
            </div>

            <textarea
              data-testid="mission-input"
              rows={5}
              value={draft.message}
              onChange={event => onDraftChange(current => ({ ...current, message: event.target.value }))}
              placeholder="直接写任务，例如：修复 Windows 启动报错，并说明原因。"
              className="min-h-[144px] w-full resize-none rounded-[26px] border border-[var(--cl-border)] bg-[rgba(255,255,255,0.86)] px-4 py-3 text-sm leading-7 text-[var(--cl-text)] outline-none placeholder:text-[var(--cl-dim)]"
            />
            <div className="mt-3 rounded-[22px] border border-[var(--cl-border)] bg-[rgba(255,255,255,0.6)] px-4 py-3 text-sm leading-6 text-[var(--cl-muted)]">
              只需要描述任务本身。系统会自动判断是否需要补充信息、是否需要分化，以及交给谁处理。
            </div>

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
        ) : (
          <button
            type="button"
            onClick={() => setComposerExpanded(true)}
            className="flex w-full items-center justify-between rounded-[24px] border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] px-4 py-3 text-left shadow-[0_12px_28px_rgba(119,83,56,0.06)]"
          >
            <div>
              <div className="text-sm font-semibold text-[var(--cl-text)]">发起新任务</div>
              <div className="mt-1 text-sm text-[var(--cl-muted)]">写一个新问题，系统会自动接住。</div>
            </div>
            <div className="text-sm text-[var(--cl-primary)]">展开</div>
          </button>
        )}
      </div>
    </div>
  )
}

function EmptyThreadState() {
  return (
    <div className="rounded-[28px] border border-[var(--cl-border)] bg-[rgba(255,255,255,0.52)] px-6 py-5">
      <h3 className="text-2xl font-semibold tracking-[-0.04em] text-[var(--cl-text)]">建议这样写任务</h3>
      <p className="mt-2 text-sm leading-7 text-[var(--cl-muted)]">
        直接写目标、现状和希望得到的结果。大多数时候，不需要先选模式，也不需要先选代理。
      </p>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <TipCard title="目标" text="你想解决什么问题？" />
        <TipCard title="现状" text="现在卡在哪里，或者手上已经有什么材料？" />
        <TipCard title="结果" text="最后你希望看到什么输出？" />
      </div>
    </div>
  )
}

function TipCard({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-[22px] border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] px-4 py-4">
      <div className="text-sm font-semibold text-[var(--cl-text)]">{title}</div>
      <div className="mt-1 text-sm leading-6 text-[var(--cl-muted)]">{text}</div>
    </div>
  )
}

function StatusPill({ label, value, testId }: { label: string; value: string; testId?: string }) {
  return (
    <div
      data-testid={testId}
      className="rounded-full border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] px-3 py-1.5 text-xs tracking-[0.04em] text-[var(--cl-muted)]"
    >
      <span className="text-[var(--cl-dim)]">{label}</span>
      <span className="ml-2 text-[var(--cl-text)]">{value}</span>
    </div>
  )
}

function buildMessages(selectedTask: Task | null, handoffs: Handoff[], lifeforms: Lifeform[]): ChatMessage[] {
  if (!selectedTask) return []

  const messages: ChatMessage[] = [
    {
      id: `task-${selectedTask.id}`,
      ts: selectedTask.created_at,
      speaker: '用户',
      tone: 'user',
      title: '用户输入',
      content: displayTaskDescription(selectedTask) || displayTaskTitle(selectedTask),
    },
  ]

  const entryLifeform = displayLifeformName(selectedTask.entry_lifeform, '虫群主宰')
  messages.push({
    id: `entry-${selectedTask.id}`,
    ts: selectedTask.created_at,
    speaker: entryLifeform,
    tone: 'sovereign',
    title: `${entryLifeform}接住任务`,
    content: '先判断任务结构，再决定是亲自处理、交给已有子主脑，还是继续分化。',
  })

  handoffs.forEach((handoff, index) => {
    const fromName = displayHandoffSource(handoff, lifeforms)
    const toName = displayHandoffTarget(handoff, lifeforms)
    const lines = [
      sanitizeText(handoff.reason, ''),
      handoff.scope ? `处理范围：${sanitizeText(handoff.scope, handoff.scope)}` : '',
      handoff.expected_output ? `期望产出：${sanitizeText(handoff.expected_output, handoff.expected_output)}` : '',
    ].filter(Boolean)

    messages.push({
      id: handoff.id || `handoff-${index}`,
      ts: handoff.created_at || selectedTask.updated_at,
      speaker: fromName,
      tone: 'handoff',
      title: `将任务交给${toName}`,
      content: lines.join('\n') || '责任已切换，后续由新的负责人继续推进。',
    })
  })

  selectedTask.progress_log.forEach((entry, index) => {
    messages.push({
      id: `progress-${index}-${entry.ts}`,
      ts: entry.ts,
      speaker: formatSpeaker(entry.agent),
      tone: 'progress',
      title: entry.agent.includes('overmind') ? '判断输出' : '执行进展',
      content: sanitizeText(entry.content, '[空输出]'),
    })
  })

  const latestState = selectedTask.flow_log[selectedTask.flow_log.length - 1]
  if (latestState && ['WaitingInput', 'Complete', 'Dormant', 'Cancelled'].includes(latestState.to)) {
    messages.push({
      id: `state-${latestState.ts}`,
      ts: latestState.ts,
      speaker: '系统',
      tone: 'system',
      title: `状态更新为${formatState(latestState.to)}`,
      content: sanitizeText(latestState.reason, '状态已更新。'),
    })
  }

  return messages.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime())
}

function formatTs(value: string) {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function bubbleClass(tone: ChatMessage['tone']) {
  if (tone === 'user') return 'border-[var(--cl-border)] bg-[rgba(93,124,87,0.10)]'
  if (tone === 'sovereign') return 'border-[var(--cl-border)] bg-[rgba(177,133,76,0.12)]'
  if (tone === 'handoff') return 'border-[var(--cl-border)] bg-[rgba(109,121,181,0.10)]'
  if (tone === 'progress') return 'border-[var(--cl-border)] bg-[rgba(79,131,169,0.10)]'
  return 'border-[var(--cl-border)] bg-[var(--cl-panel-strong)]'
}

function fallbackStage(task: Task | null) {
  if (!task) return 'idle'
  if (task.state === 'Spawning') return 'routing'
  if (task.state === 'Executing' || task.state === 'Complete') return 'execution'
  if (task.state === 'Planning' || task.state === 'Reviewing' || task.state === 'WaitingInput') return 'overmind'
  return 'mission'
}
