import { useState } from 'react'
import type { Task, BusEvent, AnalysisResult, TrialResult } from '../api'
import { fetchEvents, patchTask, deleteTask, appendTodo, toggleTodo, analyzeTask, trialTask } from '../api'

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

const PRIORITIES = ['critical', 'high', 'normal', 'low'] as const
const PRIORITY_COLOR: Record<string, string> = {
  critical: '#ef4444', high: '#f97316', normal: '#94a3b8', low: '#475569',
}

interface Props {
  task: Task | null
  onTransition: (id: string, state: string) => Promise<void>
  onRefresh: (q?: string, state?: string) => void
  onDelete: (id: string) => void
  onPatch: (task: Task) => void
}

export default function TaskDetail({ task, onTransition, onDelete, onPatch }: Props) {
  const [transitioning, setTransitioning] = useState(false)
  const [events, setEvents] = useState<BusEvent[] | null>(null)
  const [showEvents, setShowEvents] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editTitle, setEditTitle] = useState('')
  const [editDesc, setEditDesc] = useState('')
  const [editPriority, setEditPriority] = useState('normal')
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [newTodo, setNewTodo] = useState('')
  const [addingTodo, setAddingTodo] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeResult, setAnalyzeResult] = useState<AnalysisResult | null>(null)
  const [analyzeError, setAnalyzeError] = useState<string | null>(null)
  const [trialing, setTrialing] = useState(false)
  const [trialResult, setTrialResult] = useState<TrialResult | null>(null)
  const [trialError, setTrialError] = useState<string | null>(null)

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

  const startEdit = () => {
    setEditTitle(task.title)
    setEditDesc(task.description ?? '')
    setEditPriority(task.priority ?? 'normal')
    setEditing(true)
  }

  const cancelEdit = () => setEditing(false)

  const saveEdit = async () => {
    setSaving(true)
    try {
      const updated = await patchTask(task.id, {
        title: editTitle,
        description: editDesc,
        priority: editPriority,
      })
      onPatch(updated)
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  const doDelete = async () => {
    if (!confirm(`确认删除战团「${task.title}」？此操作不可撤销。`)) return
    setDeleting(true)
    try {
      await deleteTask(task.id)
      onDelete(task.id)
    } finally {
      setDeleting(false)
    }
  }

  const doToggleTodo = async (index: number) => {
    const updated = await toggleTodo(task.id, index)
    onPatch(updated)
  }

  const doAddTodo = async () => {
    if (!newTodo.trim()) return
    setAddingTodo(true)
    try {
      const updated = await appendTodo(task.id, newTodo.trim())
      onPatch(updated)
      setNewTodo('')
    } finally {
      setAddingTodo(false)
    }
  }

  const doAnalyze = async () => {
    setAnalyzing(true)
    setAnalyzeResult(null)
    setAnalyzeError(null)
    try {
      const { task: updated, analysis } = await analyzeTask(task.id)
      onPatch(updated)
      setAnalyzeResult(analysis)
    } catch (e: unknown) {
      setAnalyzeError(e instanceof Error ? e.message : '分析失败')
    } finally {
      setAnalyzing(false)
    }
  }

  const doTrial = async () => {
    setTrialing(true)
    setTrialResult(null)
    setTrialError(null)
    try {
      const result = await trialTask(task.id, ['code-expert', 'research-analyst'], task.description || task.title)
      setTrialResult(result)
    } catch (e: unknown) {
      setTrialError(e instanceof Error ? e.message : '赛马失败')
    } finally {
      setTrialing(false)
    }
  }

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
      {/* 头部 */}
      <div style={{ marginBottom: 16 }}>
        {editing ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <input
              value={editTitle}
              onChange={e => setEditTitle(e.target.value)}
              style={{ fontSize: 16, fontWeight: 700, background: '#1e2030', border: '1px solid #2d3148', borderRadius: 6, padding: '6px 10px', color: '#e2e8f0', outline: 'none' }}
            />
            <textarea
              value={editDesc}
              onChange={e => setEditDesc(e.target.value)}
              rows={3}
              placeholder="任务描述（可选）"
              style={{ fontSize: 13, background: '#1e2030', border: '1px solid #2d3148', borderRadius: 6, padding: '6px 10px', color: '#94a3b8', outline: 'none', resize: 'vertical' }}
            />
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <span style={{ fontSize: 12, color: '#475569' }}>优先级：</span>
              {PRIORITIES.map(p => (
                <button key={p} onClick={() => setEditPriority(p)} style={{
                  padding: '3px 10px', fontSize: 11, border: 'none', borderRadius: 4, cursor: 'pointer',
                  background: editPriority === p ? PRIORITY_COLOR[p] : '#1e2030',
                  color: editPriority === p ? '#fff' : '#64748b',
                  fontWeight: editPriority === p ? 600 : 400,
                }}>{p}</button>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={saveEdit} disabled={saving || !editTitle.trim()} style={{ padding: '5px 16px', background: '#7c3aed', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer', fontSize: 12 }}>
                {saving ? '保存中…' : '保存'}
              </button>
              <button onClick={cancelEdit} style={{ padding: '5px 12px', background: '#1e2030', border: '1px solid #2d3148', borderRadius: 6, color: '#64748b', cursor: 'pointer', fontSize: 12 }}>
                取消
              </button>
            </div>
          </div>
        ) : (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: dot, display: 'inline-block' }} />
              <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, flex: 1 }}>{task.title}</h2>
              <button onClick={startEdit} title="编辑" style={{ padding: '4px 8px', background: '#1e2030', border: '1px solid #2d3148', borderRadius: 6, color: '#64748b', cursor: 'pointer', fontSize: 11 }}>编辑</button>
              <button onClick={doDelete} disabled={deleting} title="删除" style={{ padding: '4px 8px', background: '#1e2030', border: '1px solid #3d1a1a', borderRadius: 6, color: '#ef4444', cursor: 'pointer', fontSize: 11 }}>
                {deleting ? '…' : '删除'}
              </button>
            </div>
            <div style={{ display: 'flex', gap: 12, fontSize: 12, color: '#64748b', flexWrap: 'wrap' }}>
              <span>{task.id}</span>
              <span>·</span>
              <span style={{ color: dot }}>{task.state}</span>
              <span>·</span>
              <span style={{ color: PRIORITY_COLOR[task.priority] ?? '#94a3b8' }}>{task.priority}</span>
              {task.assignee_synapse && <><span>·</span><span>→ {task.assignee_synapse}</span></>}
              {task.exec_mode && <><span>·</span><span>模式: {task.exec_mode}</span></>}
            </div>
          </>
        )}
      </div>

      {!editing && task.description && (
        <div style={{ padding: '10px 14px', background: '#13131a', borderRadius: 8, fontSize: 13, color: '#94a3b8', marginBottom: 16, lineHeight: 1.6 }}>
          {task.description}
        </div>
      )}

      {/* 操作按钮 */}
      {!editing && nextStates.length > 0 && (
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

      {/* 智能操作 */}
      {!editing && (
        <div style={{ marginBottom: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            onClick={doAnalyze}
            disabled={analyzing}
            style={{ padding: '5px 14px', background: analyzing ? '#2d1f5e' : '#4c1d95', border: 'none', borderRadius: 6, color: analyzing ? '#a78bfa' : '#e9d5ff', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}
          >
            {analyzing ? '🧠 分析中…' : '🧠 主脑分析'}
          </button>
          <button
            onClick={doTrial}
            disabled={trialing}
            style={{ padding: '5px 14px', background: trialing ? '#1a2e1a' : '#14532d', border: 'none', borderRadius: 6, color: trialing ? '#4ade80' : '#bbf7d0', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}
          >
            {trialing ? '⚔️ 赛马中…' : '⚔️ 赛马'}
          </button>
        </div>
      )}

      {/* 分析结果 */}
      {analyzeError && (
        <div style={{ marginBottom: 12, padding: '8px 12px', background: '#1a0a0a', border: '1px solid #7f1d1d', borderRadius: 6, fontSize: 12, color: '#f87171' }}>
          ⚠ {analyzeError}
        </div>
      )}
      {analyzeResult && (
        <Section title="主脑分析结果">
          <div style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div><span style={{ color: '#475569' }}>概要：</span>{analyzeResult.summary}</div>
            <div><span style={{ color: '#475569' }}>领域：</span>{analyzeResult.domain} · <span style={{ color: '#475569' }}>建议状态：</span><span style={{ color: '#a78bfa' }}>{analyzeResult.recommended_state}</span></div>
            {analyzeResult.risks.length > 0 && (
              <div><span style={{ color: '#475569' }}>风险：</span><span style={{ color: '#fbbf24' }}>{analyzeResult.risks.join('；')}</span></div>
            )}
          </div>
        </Section>
      )}

      {/* 赛马结果 */}
      {trialError && (
        <div style={{ marginBottom: 12, padding: '8px 12px', background: '#1a0a0a', border: '1px solid #7f1d1d', borderRadius: 6, fontSize: 12, color: '#f87171' }}>
          ⚠ {trialError}
        </div>
      )}
      {trialResult && (
        <Section title="赛马结果">
          <div style={{ fontSize: 12 }}>
            <div style={{ marginBottom: 8 }}>
              胜者：<span style={{ fontWeight: 700, color: '#22c55e' }}>{trialResult.winner ?? '（均失败）'}</span>
              {trialResult.tie && <span style={{ color: '#fbbf24', marginLeft: 6 }}>[平局]</span>}
            </div>
            {Object.entries(trialResult.results).map(([synapse, res]) => (
              <div key={synapse} style={{ display: 'flex', gap: 8, padding: '3px 0', color: '#64748b' }}>
                <span>{res.success ? '✅' : '❌'}</span>
                <span style={{ color: synapse === trialResult.winner ? '#22c55e' : '#64748b', fontWeight: synapse === trialResult.winner ? 600 : 400 }}>{synapse}</span>
                <span>rc={res.returncode}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Todos */}
      <Section title={`子任务 (${task.todos?.length ?? 0})`}>
        {(task.todos?.length ?? 0) > 0 && task.todos.map((todo, i) => (
          <div key={i}
            onClick={() => doToggleTodo(i)}
            style={{ display: 'flex', gap: 8, alignItems: 'flex-start', padding: '4px 0', fontSize: 13, cursor: 'pointer' }}
          >
            <span style={{ color: todo.done ? '#22c55e' : '#475569', marginTop: 2, userSelect: 'none' }}>{todo.done ? '✓' : '○'}</span>
            <span style={{ color: todo.done ? '#475569' : '#e2e8f0', textDecoration: todo.done ? 'line-through' : 'none' }}>{todo.title}</span>
          </div>
        ))}
        {/* 新增 Todo 输入框 */}
        {!editing && (
          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
            <input
              value={newTodo}
              onChange={e => setNewTodo(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && doAddTodo()}
              placeholder="新增子任务…"
              style={{ flex: 1, padding: '4px 8px', background: '#0d0d10', border: '1px solid #2d3148', borderRadius: 4, color: '#e2e8f0', fontSize: 12, outline: 'none' }}
            />
            <button
              onClick={doAddTodo}
              disabled={addingTodo || !newTodo.trim()}
              style={{ padding: '4px 10px', background: '#1e2030', border: '1px solid #2d3148', borderRadius: 4, color: '#94a3b8', cursor: 'pointer', fontSize: 11 }}
            >
              +
            </button>
          </div>
        )}
      </Section>

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
