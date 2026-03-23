import { useState, useRef, useEffect } from 'react'
import type { BusEvent, Task } from '../api'
import type { UserMessage } from '../App'

interface Props {
  selectedTask: Task | null
  events: BusEvent[]
  userMessages: UserMessage[]
  onSendMessage: (taskId: string, content: string) => void
}

type ChatTone = 'task' | 'progress' | 'flow' | 'event' | 'user'

interface ChatMessage {
  id: string
  ts: string
  tone: ChatTone
  speaker: string
  title?: string
  content: string
  meta?: string
  detail?: string
}

export default function TrunkChat({ selectedTask, events, userMessages, onSendMessage }: Props) {
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const messages = selectedTask ? buildMessages(selectedTask, events, userMessages) : []

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages.length])

  const handleSend = () => {
    const text = input.trim()
    if (!text || !selectedTask) return
    onSendMessage(selectedTask.id, text)
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }

  if (!selectedTask) {
    return (
      <div className="flex flex-col h-full bg-ww-surface text-ww-main">
        <div className="flex items-center justify-between px-4 pt-3.5 pb-3 border-b border-ww-subtle shrink-0">
          <div>
            <div className="text-[11px] tracking-wider uppercase text-ww-dim">Trunk Chat</div>
            <div className="mt-1 text-sm font-bold">No task selected</div>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center text-ww-dim text-[13px] text-center p-6">
          <div>
            <div className="text-3xl mb-3 opacity-30">💬</div>
            <div>Select a task to inspect its conversation trail.</div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-ww-surface text-ww-main">
      <div className="flex items-center justify-between px-4 pt-3.5 pb-3 border-b border-ww-subtle shrink-0">
        <div className="min-w-0">
          <div className="text-[11px] tracking-wider uppercase text-ww-dim">Trunk Chat</div>
          <div className="mt-1 text-sm font-bold whitespace-nowrap overflow-hidden text-ellipsis">
            {selectedTask.title}
          </div>
        </div>
        <div className="flex flex-col items-end gap-0.5 ml-4">
          <span className="text-[11px] text-ww-muted">{messages.length} messages</span>
          <span className="inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold bg-ww-info-soft text-ww-info">
            {selectedTask.state}
          </span>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-ww-dim text-[13px] text-center p-6">
            No task narrative is available yet.
          </div>
        ) : (
          messages.map(message => {
            const palette = bubblePalette(message.tone)
            const isUser = message.tone === 'user'
            const alignRight = isUser || message.tone === 'progress'

            return (
              <div
                key={message.id}
                className={`flex mb-3 animate-fade-in ${alignRight ? 'justify-end' : 'justify-start'}`}
              >
                {!alignRight && (
                  <div className="w-8 h-8 rounded-full shrink-0 mr-2.5 flex items-center justify-center text-sm"
                    style={{ background: palette.bg, border: `1px solid ${palette.border}` }}>
                    {speakerIcon(message.speaker, message.tone)}
                  </div>
                )}
                <div className={`${isUser ? 'w-[min(75%,480px)]' : 'w-[min(100%,520px)]'}`}>
                  <div className={`flex gap-2 mb-1 text-[11px] text-ww-dim ${alignRight ? 'justify-end' : 'justify-start'}`}>
                    <span className="font-semibold" style={{ color: palette.label }}>{message.speaker}</span>
                    <span>{formatTime(message.ts)}</span>
                  </div>
                  <div
                    className="rounded-[14px] px-3.5 py-3 shadow-lg"
                    style={{ background: palette.bg, border: `1px solid ${palette.border}` }}
                  >
                    {message.title && (
                      <div className="text-xs font-bold mb-1.5" style={{ color: palette.label }}>
                        {message.title}
                      </div>
                    )}
                    <div className="text-[13px] leading-relaxed text-ww-main whitespace-pre-wrap break-words">
                      {message.content}
                    </div>
                    {message.meta && (
                      <div className="mt-2 text-[11px] text-ww-muted">{message.meta}</div>
                    )}
                    {message.detail && (
                      <pre className="mt-2.5 p-2.5 bg-black/20 rounded-[10px] overflow-x-auto text-[11px] leading-normal text-ww-muted font-mono">
                        {message.detail}
                      </pre>
                    )}
                  </div>
                </div>
                {alignRight && (
                  <div className="w-8 h-8 rounded-full shrink-0 ml-2.5 flex items-center justify-center text-sm"
                    style={{ background: palette.bg, border: `1px solid ${palette.border}` }}>
                    {speakerIcon(message.speaker, message.tone)}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      <div className="shrink-0 border-t border-ww-subtle bg-ww-topbar px-4 py-3">
        <div className="flex items-end gap-2.5">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder="Send a message..."
            rows={1}
            className="flex-1 px-3.5 py-2.5 rounded-xl border border-ww-subtle bg-ww-surface text-ww-main text-[13px] outline-none resize-none placeholder:text-ww-dim focus:border-ww-active transition-colors leading-relaxed"
            style={{ maxHeight: 120 }}
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={!input.trim()}
            className="px-4 py-2.5 rounded-xl bg-opus-primary text-white text-[13px] font-semibold cursor-pointer border-none hover:bg-opus-dark transition-colors disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}

function buildMessages(task: Task, events: BusEvent[], userMsgs: UserMessage[]): ChatMessage[] {
  const taskEvents = events.filter(event => matchesTask(task, event))

  const messages: ChatMessage[] = [
    {
      id: `task-${task.id}`,
      ts: task.created_at,
      tone: 'task',
      speaker: task.creator || 'task',
      title: 'Task opened',
      content: task.description?.trim() || task.title,
      meta: compactMeta([
        `priority ${task.priority}`,
        `state ${task.state}`,
        task.assignee_synapse ? `assignee ${task.assignee_synapse}` : null,
      ]),
    },
    ...task.flow_log.map((entry, index) => ({
      id: `flow-${index}-${entry.ts}`,
      ts: entry.ts,
      tone: 'flow' as const,
      speaker: entry.agent || 'flow',
      title: `${entry.from ?? 'Start'} -> ${entry.to}`,
      content: entry.reason?.trim() || 'State transition recorded.',
      meta: compactMeta([entry.from ? `from ${entry.from}` : null, `to ${entry.to}`]),
    })),
    ...task.progress_log.map((entry, index) => ({
      id: `progress-${index}-${entry.ts}`,
      ts: entry.ts,
      tone: 'progress' as const,
      speaker: entry.agent || 'agent',
      title: 'Progress update',
      content: entry.content,
    })),
    ...taskEvents.map(event => ({
      id: `event-${event.event_id}`,
      ts: event.created_at,
      tone: 'event' as const,
      speaker: event.producer || 'event-bus',
      title: event.topic,
      content: event.event_type,
      meta: event.trace_id ? `trace ${shorten(event.trace_id)}` : undefined,
      detail: formatPayload(event.payload),
    })),
    ...userMsgs.map(msg => ({
      id: msg.id,
      ts: msg.ts,
      tone: 'user' as const,
      speaker: 'You',
      content: msg.content,
    })),
  ]

  return messages
    .filter(message => message.content.trim().length > 0)
    .sort((a, b) => toTime(a.ts) - toTime(b.ts))
}

function matchesTask(task: Task, event: BusEvent): boolean {
  if (event.trace_id && task.trace_id && event.trace_id === task.trace_id) return true

  const payload = event.payload ?? {}
  const taskId = readString(payload.task_id)
  const taskUuid = readString(payload.task_uuid)
  const traceId = readString(payload.trace_id)
  const parentId = readString(payload.parent_id)

  return [
    taskId === task.id,
    taskUuid === task.task_uuid,
    traceId === task.trace_id,
    parentId === task.id,
  ].some(Boolean)
}

function readString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null
}

function formatPayload(payload: Record<string, unknown>): string | undefined {
  if (Object.keys(payload).length === 0) return undefined
  try {
    return JSON.stringify(payload, null, 2)
  } catch {
    return undefined
  }
}

function compactMeta(parts: Array<string | null | undefined>): string | undefined {
  const filtered = parts.filter((part): part is string => !!part)
  return filtered.length > 0 ? filtered.join(' | ') : undefined
}

function bubblePalette(tone: ChatTone): { bg: string; border: string; label: string } {
  switch (tone) {
    case 'task':
      return { bg: 'rgba(230, 195, 106, 0.08)', border: 'rgba(230, 195, 106, 0.2)', label: '#e6c36a' }
    case 'progress':
      return { bg: 'rgba(155, 126, 189, 0.1)', border: 'rgba(155, 126, 189, 0.25)', label: '#9b7ebd' }
    case 'flow':
      return { bg: 'rgba(139, 215, 200, 0.08)', border: 'rgba(139, 215, 200, 0.2)', label: '#8bd7c8' }
    case 'event':
      return { bg: 'rgba(242, 183, 168, 0.08)', border: 'rgba(242, 183, 168, 0.2)', label: '#f2b7a8' }
    case 'user':
      return { bg: 'rgba(91, 155, 213, 0.12)', border: 'rgba(91, 155, 213, 0.3)', label: '#5b9bd5' }
  }
}

function speakerIcon(speaker: string, tone: ChatTone): string {
  switch (tone) {
    case 'user': return '👤'
    case 'task': return '📋'
    case 'progress': return '⚙️'
    case 'flow': return '🔄'
    case 'event': return '📡'
    default: return speaker.charAt(0).toUpperCase()
  }
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function toTime(iso: string): number {
  const value = new Date(iso).getTime()
  return Number.isNaN(value) ? 0 : value
}

function shorten(value: string): string {
  return value.length > 12 ? `${value.slice(0, 6)}...${value.slice(-4)}` : value
}
