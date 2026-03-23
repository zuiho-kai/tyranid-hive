import { useState, useEffect } from 'react'
import type { Task, BusEvent, AnalysisResult, TrialResult, ChainResult, SwarmResult, BlockedStatus } from '../api'
import { fetchEvents, patchTask, deleteTask, appendTodo, toggleTodo, analyzeTask, trialTask, chainTask, swarmTask, fetchTaskChildren, fetchTaskBlocked } from '../api'

const NEXT_STATES: Record<string, string[]> = {
  Incubating: ['Planning', 'Cancelled'],
  Planning: ['Reviewing', 'Dormant', 'Cancelled'],
  Reviewing: ['Spawning', 'Planning', 'Cancelled'],
  Spawning: ['Executing', 'Dormant', 'Cancelled'],
  Executing: ['Consolidating', 'Complete', 'Dormant', 'Cancelled'],
  Consolidating: ['Complete', 'Executing', 'Cancelled'],
  Dormant: ['Planning', 'Executing'],
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
  const [chaining, setChaining] = useState(false)
  const [chainResult, setChainResult] = useState<ChainResult | null>(null)
  const [chainError, setChainError] = useState<string | null>(null)
  const [showChainInput, setShowChainInput] = useState(false)
  const [chainSynapses, setChainSynapses] = useState('overmind,code-expert')
  const [swarming, setSwarming] = useState(false)
  const [swarmResult, setSwarmResult] = useState<SwarmResult | null>(null)
  const [swarmError, setSwarmError] = useState<string | null>(null)
  const [showSwarmInput, setShowSwarmInput] = useState(false)
  const [swarmUnits, setSwarmUnits] = useState('code-expert:实现功能A\nresearch-analyst:调研方案B')
  const [children, setChildren] = useState<Task[]>([])
  const [blocked, setBlocked] = useState<BlockedStatus | null>(null)

  useEffect(() => {
    if (!task) return
    fetchTaskChildren(task.id).then(setChildren)
    fetchTaskBlocked(task.id).then(setBlocked)
  }, [task?.id])

  if (!task) {
    return <div className="flex-1 flex items-center justify-center text-ww-dim text-sm">选择左侧战团查看详情</div>
  }

  const nextStates = NEXT_STATES[task.state] ?? []
  const dot = STATE_COLOR[task.state] ?? '#64748b'

  const doTransition = async (s: string) => {
    setTransitioning(true)
    try { await onTransition(task.id, s) } finally { setTransitioning(false) }
  }
  const loadEvents = async () => {
    if (!showEvents) { const ev = await fetchEvents(task.id); setEvents(ev) }
    setShowEvents(v => !v)
  }
  const startEdit = () => { setEditTitle(task.title); setEditDesc(task.description ?? ''); setEditPriority(task.priority ?? 'normal'); setEditing(true) }
  const cancelEdit = () => setEditing(false)
  const saveEdit = async () => {
    setSaving(true)
    try { const updated = await patchTask(task.id, { title: editTitle, description: editDesc, priority: editPriority }); onPatch(updated); setEditing(false) } finally { setSaving(false) }
  }
  const doDelete = async () => {
    if (!confirm(`确认删除战团「${task.title}」？此操作不可撤销。`)) return
    setDeleting(true)
    try { await deleteTask(task.id); onDelete(task.id) } finally { setDeleting(false) }
  }
  const doToggleTodo = async (index: number) => { const updated = await toggleTodo(task.id, index); onPatch(updated) }
  const doAddTodo = async () => {
    if (!newTodo.trim()) return
    setAddingTodo(true)
    try { const updated = await appendTodo(task.id, newTodo.trim()); onPatch(updated); setNewTodo('') } finally { setAddingTodo(false) }
  }
  const doAnalyze = async () => {
    setAnalyzing(true); setAnalyzeResult(null); setAnalyzeError(null)
    try { const { task: updated, analysis } = await analyzeTask(task.id); onPatch(updated); setAnalyzeResult(analysis) }
    catch (e: unknown) { setAnalyzeError(e instanceof Error ? e.message : '分析失败') }
    finally { setAnalyzing(false) }
  }
  const doTrial = async () => {
    setTrialing(true); setTrialResult(null); setTrialError(null)
    try { setTrialResult(await trialTask(task.id, ['code-expert', 'research-analyst'], task.description || task.title)) }
    catch (e: unknown) { setTrialError(e instanceof Error ? e.message : '赛马失败') }
    finally { setTrialing(false) }
  }
  const doChain = async () => {
    const synapses = chainSynapses.split(',').map(s => s.trim()).filter(Boolean)
    if (synapses.length < 2) { setChainError('链式调用至少需要 2 个小主脑'); return }
    setChaining(true); setChainResult(null); setChainError(null); setShowChainInput(false)
    try { setChainResult(await chainTask(task.id, synapses, task.description || task.title)) }
    catch (e: unknown) { setChainError(e instanceof Error ? e.message : '链式调用失败') }
    finally { setChaining(false) }
  }
  const doSwarm = async () => {
    const units = swarmUnits.split('\n').map(l => l.trim()).filter(Boolean).map(line => {
      const idx = line.indexOf(':')
      return idx < 0 ? null : { synapse: line.slice(0, idx).trim(), message: line.slice(idx + 1).trim() }
    }).filter((u): u is { synapse: string; message: string } => !!u)
    if (units.length === 0) { setSwarmError('至少需要一个有效 unit（格式：synapse:message）'); return }
    setSwarming(true); setSwarmResult(null); setSwarmError(null); setShowSwarmInput(false)
    try { setSwarmResult(await swarmTask(task.id, units)) }
    catch (e: unknown) { setSwarmError(e instanceof Error ? e.message : 'Swarm 执行失败') }
    finally { setSwarming(false) }
  }

  return (
    <div className="flex-1 overflow-y-auto p-5">
      {/* 头部 */}
      <div className="mb-4">
        {editing ? (
          <div className="flex flex-col gap-2">
            <input value={editTitle} onChange={e => setEditTitle(e.target.value)}
              className="text-base font-bold bg-ww-card border border-ww-subtle rounded-md px-2.5 py-1.5 text-ww-main outline-none" />
            <textarea value={editDesc} onChange={e => setEditDesc(e.target.value)} rows={3} placeholder="任务描述（可选）"
              className="text-[13px] bg-ww-card border border-ww-subtle rounded-md px-2.5 py-1.5 text-ww-muted outline-none resize-y" />
            <div className="flex gap-1.5 items-center">
              <span className="text-xs text-ww-dim">优先级：</span>
              {PRIORITIES.map(p => (
                <button key={p} onClick={() => setEditPriority(p)}
                  className="px-2.5 py-0.5 text-[11px] border-none rounded cursor-pointer transition-colors"
                  style={{ background: editPriority === p ? PRIORITY_COLOR[p] : undefined, color: editPriority === p ? '#fff' : '#64748b', fontWeight: editPriority === p ? 600 : 400 }}
                >{p}</button>
              ))}
            </div>
            <div className="flex gap-2">
              <button onClick={saveEdit} disabled={saving || !editTitle.trim()} className="px-4 py-1.5 bg-opus-primary border-none rounded-md text-white cursor-pointer text-xs disabled:opacity-50">{saving ? '保存中…' : '保存'}</button>
              <button onClick={cancelEdit} className="px-3 py-1.5 bg-ww-card border border-ww-subtle rounded-md text-ww-dim cursor-pointer text-xs">取消</button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: dot }} />
              <h2 className="m-0 text-lg font-bold flex-1">{task.title}</h2>
              <button onClick={startEdit} className="px-2 py-1 bg-ww-card border border-ww-subtle rounded-md text-ww-dim cursor-pointer text-[11px]">编辑</button>
              <button onClick={doDelete} disabled={deleting} className="px-2 py-1 bg-ww-card border border-ww-danger/30 rounded-md text-ww-danger cursor-pointer text-[11px]">{deleting ? '…' : '删除'}</button>
            </div>
            <div className="flex gap-3 text-xs text-ww-dim flex-wrap">
              <span>{task.id}</span><span>·</span>
              <span style={{ color: dot }}>{task.state}</span><span>·</span>
              <span style={{ color: PRIORITY_COLOR[task.priority] ?? '#94a3b8' }}>{task.priority}</span>
              {task.assignee_synapse && <><span>·</span><span>→ {task.assignee_synapse}</span></>}
              {task.exec_mode && <><span>·</span><span>模式: {task.exec_mode}</span></>}
            </div>
          </>
        )}
      </div>

      {!editing && task.description && (
        <div className="px-3.5 py-2.5 bg-ww-surface rounded-lg text-[13px] text-ww-muted mb-4 leading-relaxed">{task.description}</div>
      )}

      {/* 状态流转 */}
      {!editing && nextStates.length > 0 && (
        <div className="mb-4">
          <div className="text-[11px] text-ww-dim mb-1.5 uppercase tracking-wider">流转到</div>
          <div className="flex flex-wrap gap-1.5">
            {nextStates.map(s => (
              <button key={s} onClick={() => doTransition(s)} disabled={transitioning}
                className="px-3 py-1.5 bg-transparent rounded-md cursor-pointer text-xs transition-colors hover:bg-ww-surface"
                style={{ border: `1px solid ${STATE_COLOR[s] ?? '#2d3148'}`, color: STATE_COLOR[s] ?? '#94a3b8' }}
              >{s}</button>
            ))}
          </div>
        </div>
      )}

      {/* 智能操作 */}
      {!editing && (
        <div className="mb-4 flex gap-2 flex-wrap">
          <SmartBtn onClick={doAnalyze} loading={analyzing} label="🧠 主脑分析" loadingLabel="🧠 分析中…" color="opus" />
          <SmartBtn onClick={doTrial} loading={trialing} label="⚔️ 赛马" loadingLabel="⚔️ 赛马中…" color="success" />
          <SmartBtn onClick={() => setShowChainInput(v => !v)} loading={chaining} label="🔗 链式调用" loadingLabel="🔗 链式中…" color="info" />
          <SmartBtn onClick={() => setShowSwarmInput(v => !v)} loading={swarming} label="🐛 Swarm" loadingLabel="🐛 Swarm中…" color="success" />
        </div>
      )}

      {/* 链式输入 */}
      {!editing && showChainInput && (
        <div className="mb-4 px-3.5 py-2.5 bg-ww-surface rounded-lg flex gap-2 items-center">
          <input value={chainSynapses} onChange={e => setChainSynapses(e.target.value)} placeholder="小主脑链（逗号分隔，≥2）"
            className="flex-1 px-2 py-1 bg-ww-base border border-ww-subtle rounded text-ww-main text-xs outline-none" />
          <button onClick={doChain} disabled={chaining} className="px-3 py-1 bg-opus-dark border-none rounded-md text-white cursor-pointer text-xs">执行</button>
        </div>
      )}

      {/* Swarm 输入 */}
      {!editing && showSwarmInput && (
        <div className="mb-4 px-3.5 py-2.5 bg-ww-surface rounded-lg">
          <div className="text-[11px] text-ww-dim mb-1.5">每行一个 unit，格式：synapse:message</div>
          <textarea value={swarmUnits} onChange={e => setSwarmUnits(e.target.value)} rows={4}
            className="w-full px-2 py-1.5 bg-ww-base border border-ww-subtle rounded text-ww-main text-xs outline-none resize-y font-mono" />
          <button onClick={doSwarm} disabled={swarming} className="mt-1.5 px-3.5 py-1 bg-codex-dark border-none rounded-md text-white cursor-pointer text-xs">并发执行</button>
        </div>
      )}

      <ErrorBox msg={analyzeError} />
      {analyzeResult && (
        <Section title="主脑分析结果">
          <div className="text-xs flex flex-col gap-1.5">
            <div><span className="text-ww-dim">概要：</span>{analyzeResult.summary}</div>
            <div><span className="text-ww-dim">领域：</span>{analyzeResult.domain} · <span className="text-ww-dim">建议状态：</span><span className="text-opus-primary">{analyzeResult.recommended_state}</span></div>
            {analyzeResult.risks.length > 0 && <div><span className="text-ww-dim">风险：</span><span className="text-ww-info">{analyzeResult.risks.join('；')}</span></div>}
          </div>
        </Section>
      )}

      <ErrorBox msg={trialError} />
      {trialResult && (
        <Section title="赛马结果">
          <div className="text-xs">
            <div className="mb-2">胜者：<span className="font-bold text-ww-success">{trialResult.winner ?? '（均失败）'}</span>
              {trialResult.tie && <span className="text-ww-info ml-1.5">[平局]</span>}
            </div>
            {Object.entries(trialResult.results).map(([synapse, res]) => (
              <div key={synapse} className="flex gap-2 py-0.5 text-ww-dim">
                <span>{res.success ? '✅' : '❌'}</span>
                <span className={synapse === trialResult.winner ? 'text-ww-success font-semibold' : 'text-ww-dim'}>{synapse}</span>
                <span>rc={res.returncode}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      <ErrorBox msg={chainError} />
      <ErrorBox msg={swarmError} />

      {chainResult && (
        <Section title={`链式调用结果 (${chainResult.success ? '✅ 成功' : '❌ 失败'})`}>
          <div className="text-xs flex flex-col gap-1">
            {chainResult.results.map((stage, i) => (
              <div key={i} className="flex gap-2 py-1 border-b border-ww-subtle text-ww-dim">
                <span className="text-ww-dim shrink-0">#{i + 1}</span>
                <span className={`font-semibold min-w-[120px] ${stage.success ? 'text-ww-success' : 'text-ww-danger'}`}>{stage.synapse}</span>
                <span>rc={stage.returncode}</span>
                <span className="text-ww-dim">{stage.elapsed_sec.toFixed(1)}s</span>
                {stage.stdout && <span className="text-ww-muted overflow-hidden text-ellipsis whitespace-nowrap flex-1">{stage.stdout.slice(0, 80)}</span>}
              </div>
            ))}
            {chainResult.final_output && (
              <div className="mt-1.5 px-2 py-1.5 bg-ww-base rounded text-ww-muted text-[11px] max-h-[120px] overflow-y-auto whitespace-pre-wrap">{chainResult.final_output.slice(0, 500)}</div>
            )}
          </div>
        </Section>
      )}

      {swarmResult && (
        <Section title={`Swarm 结果 (${swarmResult.success_count}/${swarmResult.total} 成功  ${(swarmResult.success_rate * 100).toFixed(0)}%)`}>
          <div className="text-xs flex flex-col gap-1">
            {swarmResult.results.map((unit, i) => (
              <div key={i} className="py-1 border-b border-ww-subtle">
                <div className="flex gap-2 text-ww-dim">
                  <span>{unit.success ? '✅' : '❌'}</span>
                  <span className={`font-semibold min-w-[120px] ${unit.success ? 'text-ww-success' : 'text-ww-danger'}`}>{unit.synapse}</span>
                  <span>rc={unit.returncode}</span>
                  <span className="text-ww-dim">{unit.elapsed_sec.toFixed(1)}s</span>
                </div>
                {unit.stdout && <div className="text-ww-muted text-[11px] mt-0.5 pl-5 overflow-hidden text-ellipsis whitespace-nowrap">{unit.stdout.slice(0, 100)}</div>}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Todos */}
      <Section title={`子任务 (${task.todos?.length ?? 0})`}>
        {(task.todos?.length ?? 0) > 0 && task.todos.map((todo, i) => (
          <div key={i} onClick={() => doToggleTodo(i)} className="flex gap-2 items-start py-1 text-[13px] cursor-pointer">
            <span className={`mt-0.5 select-none ${todo.done ? 'text-ww-success' : 'text-ww-dim'}`}>{todo.done ? '✓' : '○'}</span>
            <span className={todo.done ? 'text-ww-dim line-through' : 'text-ww-main'}>{todo.title}</span>
          </div>
        ))}
        {!editing && (
          <div className="flex gap-1.5 mt-2">
            <input value={newTodo} onChange={e => setNewTodo(e.target.value)} onKeyDown={e => e.key === 'Enter' && doAddTodo()}
              placeholder="新增子任务…" className="flex-1 px-2 py-1 bg-ww-base border border-ww-subtle rounded text-ww-main text-xs outline-none" />
            <button onClick={doAddTodo} disabled={addingTodo || !newTodo.trim()}
              className="px-2.5 py-1 bg-ww-card border border-ww-subtle rounded text-ww-muted cursor-pointer text-[11px] disabled:opacity-50">+</button>
          </div>
        )}
      </Section>

      {/* 依赖阻塞 */}
      {task.depends_on && task.depends_on.length > 0 && (
        <Section title="依赖状态">
          {blocked === null ? (
            <div className="text-xs text-ww-dim">加载中…</div>
          ) : blocked.is_blocked ? (
            <div>
              <div className="text-xs text-dare-primary mb-1.5">⚠ 被以下依赖阻塞</div>
              {blocked.pending_deps.map(dep => (
                <div key={dep.id} className="flex gap-2 text-xs py-0.5 text-ww-muted">
                  <span style={{ color: STATE_COLOR[dep.state] ?? '#64748b' }}>●</span>
                  <span className="text-ww-dim">{dep.id.slice(0, 8)}</span>
                  <span>{dep.title}</span>
                  <span className="text-ww-dim">[{dep.state}]</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-ww-success">✓ 所有依赖已完成，可自由执行</div>
          )}
        </Section>
      )}

      {/* 子战团 */}
      {children.length > 0 && (
        <Section title={`子战团 (${children.length})`}>
          {children.map(child => (
            <div key={child.id} className="flex gap-2 items-center py-1 text-xs">
              <span className="w-2 h-2 rounded-full shrink-0 inline-block" style={{ background: STATE_COLOR[child.state] ?? '#64748b' }} />
              <span className="text-ww-dim font-mono shrink-0">{child.id.slice(0, 8)}</span>
              <span className="text-ww-muted flex-1 overflow-hidden text-ellipsis whitespace-nowrap">{child.title}</span>
              <span className="shrink-0" style={{ color: STATE_COLOR[child.state] ?? '#64748b' }}>{child.state}</span>
            </div>
          ))}
        </Section>
      )}

      {/* 标签 */}
      {task.labels && task.labels.length > 0 && (
        <Section title="标签">
          <div className="flex gap-1.5 flex-wrap">
            {task.labels.map((label, i) => (
              <span key={i} className="px-2 py-0.5 bg-ww-card border border-ww-subtle rounded-[10px] text-[11px] text-opus-primary">{label}</span>
            ))}
          </div>
        </Section>
      )}

      {/* 流转记录 */}
      {(task.flow_log?.length ?? 0) > 0 && (
        <Section title="流转记录">
          {[...task.flow_log].reverse().map((entry, i) => (
            <div key={i} className="flex gap-2 text-xs py-0.5 text-ww-dim">
              <span className="text-ww-dim shrink-0">{fmtTime(entry.ts)}</span>
              <span>{entry.from ?? '—'} → <span style={{ color: STATE_COLOR[entry.to] ?? '#94a3b8' }}>{entry.to}</span></span>
              <span className="text-ww-dim">by {entry.agent}</span>
              {entry.reason && <span className="text-ww-dim">({entry.reason})</span>}
            </div>
          ))}
        </Section>
      )}

      {/* 执行进度 */}
      {(task.progress_log?.length ?? 0) > 0 && (
        <Section title="执行进度">
          {[...task.progress_log].reverse().map((p, i) => (
            <div key={i} className="py-1 text-xs">
              <div className="text-ww-dim mb-0.5">{fmtTime(p.ts)} · {p.agent}</div>
              <div className="text-ww-muted leading-normal">{p.content}</div>
            </div>
          ))}
        </Section>
      )}

      {/* 事件链路 */}
      <button onClick={loadEvents} className="text-xs text-ww-dim bg-transparent border-none cursor-pointer py-1 mt-2 hover:text-ww-muted transition-colors">
        {showEvents ? '▾ 隐藏事件链路' : '▸ 查看事件链路'}
      </button>
      {showEvents && events && (
        <div className="mt-2">
          {events.length === 0 ? <span className="text-xs text-ww-dim">暂无事件记录</span> : events.map(e => (
            <div key={e.event_id} className="text-[11px] py-0.5 border-b border-ww-surface text-ww-dim flex gap-2">
              <span className="text-ww-dim shrink-0">{fmtTime(e.created_at)}</span>
              <span className="text-opus-primary">{e.topic}</span>
              <span>{e.event_type}</span>
              <span className="text-ww-dim">← {e.producer}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <div className="text-[11px] text-ww-dim mb-1.5 uppercase tracking-wider">{title}</div>
      <div className="bg-ww-surface rounded-lg px-3.5 py-2.5">{children}</div>
    </div>
  )
}

function SmartBtn({ onClick, loading, label, loadingLabel, color }: {
  onClick: () => void; loading: boolean; label: string; loadingLabel: string; color: 'opus' | 'success' | 'info'
}) {
  const colorMap = {
    opus: 'bg-opus-dark/40 text-opus-light hover:bg-opus-dark/60 disabled:bg-opus-dark/20 disabled:text-opus-primary',
    success: 'bg-codex-dark/40 text-codex-light hover:bg-codex-dark/60 disabled:bg-codex-dark/20 disabled:text-codex-primary',
    info: 'bg-gemini-dark/40 text-gemini-light hover:bg-gemini-dark/60 disabled:bg-gemini-dark/20 disabled:text-gemini-primary',
  }
  return (
    <button onClick={onClick} disabled={loading}
      className={`px-3.5 py-1.5 border-none rounded-md cursor-pointer text-xs font-semibold transition-colors ${colorMap[color]}`}
    >{loading ? loadingLabel : label}</button>
  )
}

function ErrorBox({ msg }: { msg: string | null }) {
  if (!msg) return null
  return (
    <div className="mb-3 px-3 py-2 bg-ww-danger/10 border border-ww-danger/30 rounded-md text-xs text-ww-danger">
      ⚠ {msg}
    </div>
  )
}

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch { return iso }
}
