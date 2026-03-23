import type { CSSProperties } from 'react'
import type { BusEvent, Task } from '../api'

interface Props {
  selectedTask: Task | null
  events: BusEvent[]
}

type ChatTone = 'task' | 'progress' | 'flow' | 'event'

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

const SHELL_STYLE: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
  background: '#13131a',
  color: '#e2e8f0',
}

const HEADER_STYLE: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '14px 16px 12px',
  borderBottom: '1px solid #1e2030',
  flexShrink: 0,
}

const SCROLL_STYLE: CSSProperties = {
  flex: 1,
  overflowY: 'auto',
  padding: '16px',
}

const EMPTY_STYLE: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  height: '100%',
  color: '#475569',
  fontSize: 13,
  textAlign: 'center',
  padding: 24,
}

export default function TrunkChat({ selectedTask, events }: Props) {
  if (!selectedTask) {
    return (
      <div style={SHELL_STYLE}>
        <div style={HEADER_STYLE}>
          <div>
            <div style={{ fontSize: 11, letterSpacing: 1, textTransform: 'uppercase', color: '#64748b' }}>Trunk Chat</div>
            <div style={{ marginTop: 4, fontSize: 14, fontWeight: 700 }}>No task selected</div>
          </div>
        </div>
        <div style={EMPTY_STYLE}>Select a task to inspect its conversation trail.</div>
      </div>
    )
  }

  const messages = buildMessages(selectedTask, events)

  return (
    <div style={SHELL_STYLE}>
      <div style={HEADER_STYLE}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 11, letterSpacing: 1, textTransform: 'uppercase', color: '#64748b' }}>Trunk Chat</div>
          <div style={{ marginTop: 4, fontSize: 14, fontWeight: 700, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {selectedTask.title}
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2, marginLeft: 16 }}>
          <span style={{ fontSize: 11, color: '#94a3b8' }}>{messages.length} messages</span>
          <span style={{ fontSize: 11, color: '#64748b' }}>{selectedTask.state}</span>
        </div>
      </div>

      <div style={SCROLL_STYLE}>
        {messages.length === 0 ? (
          <div style={EMPTY_STYLE}>No task narrative is available yet.</div>
        ) : (
          messages.map(message => {
            const palette = bubblePalette(message.tone)
            const alignRight = message.tone === 'progress'

            return (
              <div
                key={message.id}
                style={{
                  display: 'flex',
                  justifyContent: alignRight ? 'flex-end' : 'flex-start',
                  marginBottom: 12,
                }}
              >
                <div style={{ width: 'min(100%, 520px)' }}>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: alignRight ? 'flex-end' : 'flex-start',
                      gap: 8,
                      marginBottom: 4,
                      fontSize: 11,
                      color: '#64748b',
                    }}
                  >
                    <span style={{ color: palette.label, fontWeight: 600 }}>{message.speaker}</span>
                    <span>{formatTime(message.ts)}</span>
                  </div>
                  <div
                    style={{
                      background: palette.bg,
                      border: `1px solid ${palette.border}`,
                      borderRadius: 14,
                      padding: '12px 14px',
                      boxShadow: '0 10px 30px rgba(0, 0, 0, 0.16)',
                    }}
                  >
                    {message.title && (
                      <div style={{ fontSize: 12, fontWeight: 700, color: palette.label, marginBottom: 6 }}>
                        {message.title}
                      </div>
                    )}
                    <div style={{ fontSize: 13, lineHeight: 1.6, color: '#e2e8f0', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                      {message.content}
                    </div>
                    {message.meta && (
                      <div style={{ marginTop: 8, fontSize: 11, color: '#94a3b8' }}>
                        {message.meta}
                      </div>
                    )}
                    {message.detail && (
                      <pre
                        style={{
                          margin: '10px 0 0',
                          padding: '10px 12px',
                          background: 'rgba(0, 0, 0, 0.22)',
                          borderRadius: 10,
                          overflowX: 'auto',
                          fontSize: 11,
                          lineHeight: 1.5,
                          color: '#cbd5e1',
                          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
                        }}
                      >
                        {message.detail}
                      </pre>
                    )}
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

function buildMessages(task: Task, events: BusEvent[]): ChatMessage[] {
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
      return { bg: '#1b2332', border: '#2e3d59', label: '#7dd3fc' }
    case 'progress':
      return { bg: '#1f2937', border: '#334155', label: '#a78bfa' }
    case 'flow':
      return { bg: '#1d2a25', border: '#29443b', label: '#4ade80' }
    case 'event':
      return { bg: '#2a1f33', border: '#4c2b63', label: '#f0abfc' }
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
