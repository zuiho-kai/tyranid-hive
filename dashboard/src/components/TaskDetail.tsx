import { useState } from 'react'
import type { Task } from '../api'
import { fetchEvents } from '../api'
import type { BusEvent } from '../api'

const NEXT_STATES: Record<string, string[]> = {
  Incubating:    ['Planning', 'Cancelled'],
  Planning:      ['Reviewing', 'Dormant', 'Cancelled'],
  Reviewing:     ['Spawning', 'Planning', 'Cancelled'],
  Spawning:      ['Executing', 'Dormant', 'Cancelled'],
  Executing:     ['Consolidating', 'Complete', 'Dormant', 'Cancelled'],
  Consolidating: ['Complete', 'Executing', 'Cancelled'],
  Dormant:       ['Planning', 'Executing'],
}

const STATE_COLOR: Record<string, string> = {
  Incubating: '#6366f1', Planning: '#8b5cf6', Reviewing: '#a78bfa',
  Spawning: '#06b6d4', Executing: '#22c55e', Consolidating: '#f59e0b',
  Complete: '#475569', Dormant: '#ef4444', Cancelled: '#374151',
}

interface Props {
  task: Task | null
  onTransition: (id: string, state: string) => Promise<void>
  onRefresh: () => void
}

export default function TaskDetail({ task, onTransition, onRefresh: _onRefresh }: Props) {
  const [transitioning, setTransitioning] = useState(false)
  const [events, setEvents] = useState<BusEvent[] | null>(null)
  const [showEvents, setShowEvents] = useState(false)

  if (!task) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#374151', fontSize: 14 }}>
        选择左侧战团查看详情
      </div>
    )
  }

  const nextStates = NEXT_STATES[task.state] ?? []
  const dot = STATE_COLOR[task.state] ?? '#64748b'

  const doTransition = async (s: string) => {
    setTransitioning(true)
    try { await onTransition(task.id, s) } finally { setTransitioning(false) }
  }

  const loadEvents = async () => {
    if (!showEvents) {
      const ev = await fetchEvents(task.id)
      setEvents(ev)
    }
    setShowEvents(v => !v)
  }

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
      {/* 头部 */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', background: dot, display: 'inline-block' }} />
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>{task.title}</h2>
        </div>
        <div style={{ display: 'flex', gap: 12, fontSize: 12, color: '#64748b' }}>
          <span>{task.id}</span>
          <span>·</span>
          <span style={{ color: dot }}>{task.state}</span>
          {task.assignee_synapse && <><span>·</span><span>→ {task.assignee_synapse}</span></>}
          {task.exec_mode && <><span>·</span><span>模式: {task.exec_mode}</span></>}
        </div>
      </div>

      {task.description && (
        <div style={{ padding: '10px 14px', background: '#13131a', borderRadius: 8, fontSize: 13, color: '#94a3b8', marginBottom: 16, lineHeight: 1.6 }}>
          {task.description}
        </div>
      )}

      {/* 操作按钮 */}
      {nextStates.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: '#475569', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>流转到</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {nextStates.map(s => (
              <button
                key={s}
                onClick={() => doTransition(s)}
                disabled={transitioning}
                style={{
                  padding: '5px 12px', border: `1px solid ${STATE_COLOR[s] ?? '#2d3148'}`,
                  borderRadius: 6, background: 'transparent', color: STATE_COLOR[s] ?? '#94a3b8',
                  cursor: 'pointer', fontSize: 12,
                }}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Todos */}
      {(task.todos?.length ?? 0) > 0 && (
        <Section title="子任务">
          {task.todos.map((todo, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', padding: '4px 0', fontSize: 13 }}>
              <span style={{ color: todo.done ? '#22c55e' : '#475569', marginTop: 2 }}>{todo.done ? '✓' : '○'}</span>
              <span style={{ color: todo.done ? '#475569' : '#e2e8f0', textDecoration: todo.done ? 'line-through' : 'none' }}>{todo.title}</span>
            </div>
          ))}
        </Section>
      )}

      {/* 流转记录 */}
      {(task.flow_log?.length ?? 0) > 0 && (
        <Section title="流转记录">
          {[...task.flow_log].reverse().map((entry, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, fontSize: 12, padding: '3px 0', color: '#64748b' }}>
              <span style={{ color: '#374151', flexShrink: 0 }}>{fmtTime(entry.ts)}</span>
              <span>{entry.from ?? '—'} → <span style={{ color: STATE_COLOR[entry.to] ?? '#94a3b8' }}>{entry.to}</span></span>
              <span style={{ color: '#374151' }}>by {entry.agent}</span>
              {entry.reason && <span style={{ color: '#475569' }}>({entry.reason})</span>}
            </div>
          ))}
        </Section>
      )}

      {/* 执行进度 */}
      {(task.progress_log?.length ?? 0) > 0 && (
        <Section title="执行进度">
          {[...task.progress_log].reverse().map((p, i) => (
            <div key={i} style={{ padding: '4px 0', fontSize: 12 }}>
              <div style={{ color: '#475569', marginBottom: 2 }}>{fmtTime(p.ts)} · {p.agent}</div>
              <div style={{ color: '#94a3b8', lineHeight: 1.5 }}>{p.content}</div>
            </div>
          ))}
        </Section>
      )}

      {/* 事件链路 */}
      <button onClick={loadEvents} style={{ fontSize: 12, color: '#64748b', background: 'none', border: 'none', cursor: 'pointer', padding: '4px 0', marginTop: 8 }}>
        {showEvents ? '▾ 隐藏事件链路' : '▸ 查看事件链路'}
      </button>
      {showEvents && events && (
        <div style={{ marginTop: 8 }}>
          {events.length === 0 ? <span style={{ fontSize: 12, color: '#374151' }}>暂无事件记录</span> : events.map(e => (
            <div key={e.event_id} style={{ fontSize: 11, padding: '3px 0', borderBottom: '1px solid #1a1a24', color: '#475569', display: 'flex', gap: 8 }}>
              <span style={{ color: '#374151', flexShrink: 0 }}>{fmtTime(e.created_at)}</span>
              <span style={{ color: '#a78bfa' }}>{e.topic}</span>
              <span>{e.event_type}</span>
              <span style={{ color: '#374151' }}>← {e.producer}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 11, color: '#475569', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>{title}</div>
      <div style={{ background: '#13131a', borderRadius: 8, padding: '10px 14px' }}>{children}</div>
    </div>
  )
}

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch { return iso }
}
