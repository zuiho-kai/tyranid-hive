import { useState, useEffect, useCallback, useRef } from 'react'
import { fetchTasks, fetchSynapses, fetchStats, createTask, transitionTask } from './api'
import type { Task, Synapse, BusEvent, TaskStats } from './api'
import { useHiveWebSocket } from './useWebSocket'
import TaskList from './components/TaskList'
import TaskDetail from './components/TaskDetail'
import EventStream from './components/EventStream'
import GeneLibrary from './components/GeneLibrary'
import SynapsePanel from './components/SynapsePanel'
import CreateTaskModal from './components/CreateTaskModal'

type Tab = 'tasks' | 'genes' | 'synapses'

const STATE_FILTERS = ['', 'Incubating', 'Planning', 'Reviewing', 'Executing', 'Complete', 'Cancelled'] as const
type StateFilter = typeof STATE_FILTERS[number]

const SORT_OPTIONS = [
  { value: 'updated_at:desc', label: '最近更新' },
  { value: 'updated_at:asc',  label: '最早更新' },
  { value: 'created_at:desc', label: '最近创建' },
  { value: 'priority:asc',    label: '优先级 ↑' },
  { value: 'state:asc',       label: '状态 A→Z' },
] as const
type SortOption = typeof SORT_OPTIONS[number]['value']

export default function App() {
  const [tab, setTab] = useState<Tab>('tasks')
  const [tasks, setTasks] = useState<Task[]>([])
  const [synapses, setSynapses] = useState<Synapse[]>([])
  const [stats, setStats] = useState<TaskStats | null>(null)
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [loading, setLoading] = useState(false)
  // 搜索 + 状态筛选 + 排序
  const [search, setSearch] = useState('')
  const [stateFilter, setStateFilter] = useState<StateFilter>('')
  const [sortOpt, setSortOpt] = useState<SortOption>('updated_at:desc')
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const refreshTasks = useCallback(async (q?: string, state?: string, sort?: string) => {
    setLoading(true)
    try {
      const [sortBy, sortOrder] = (sort ?? sortOpt).split(':')
      const params: { q?: string; state?: string; sort_by?: string; order?: string } = {
        sort_by: sortBy,
        order: sortOrder,
      }
      if (q)     params.q     = q
      if (state) params.state = state
      const [ts, st] = await Promise.all([fetchTasks(params), fetchStats()])
      setTasks(ts)
      setStats(st)
      if (selectedTask) {
        const updated = ts.find(t => t.id === selectedTask.id)
        if (updated) setSelectedTask(updated)
      }
    } finally {
      setLoading(false)
    }
  }, [selectedTask, sortOpt])

  useEffect(() => { refreshTasks() }, [])
  useEffect(() => { fetchSynapses().then(setSynapses) }, [])

  // 搜索防抖 300ms
  const handleSearchChange = (val: string) => {
    setSearch(val)
    if (searchTimer.current) clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => {
      refreshTasks(val || undefined, stateFilter || undefined)
    }, 300)
  }

  const handleStateFilter = (s: StateFilter) => {
    setStateFilter(s)
    refreshTasks(search || undefined, s || undefined)
  }

  const handleSortChange = (s: SortOption) => {
    setSortOpt(s)
    refreshTasks(search || undefined, stateFilter || undefined, s)
  }

  const handleWsEvent = useCallback((e: BusEvent) => {
    if (e.topic.startsWith('task.')) refreshTasks(search || undefined, stateFilter || undefined)
  }, [refreshTasks, search, stateFilter])

  const { connected, events } = useHiveWebSocket(handleWsEvent)

  const handleTransition = async (taskId: string, newState: string) => {
    await transitionTask(taskId, newState)
    await refreshTasks(search || undefined, stateFilter || undefined)
  }

  const handleDelete = (taskId: string) => {
    setTasks(ts => ts.filter(t => t.id !== taskId))
    if (selectedTask?.id === taskId) setSelectedTask(null)
  }

  const handlePatch = (updated: Task) => {
    setTasks(ts => ts.map(t => t.id === updated.id ? updated : t))
    if (selectedTask?.id === updated.id) setSelectedTask(updated)
  }

  const handleCreate = async (title: string, description: string, priority: string) => {
    await createTask({ title, description, priority })
    setShowCreate(false)
    await refreshTasks(search || undefined, stateFilter || undefined)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#0f0f12', color: '#e2e8f0', fontFamily: 'system-ui, sans-serif' }}>
      {/* 顶栏 */}
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 20px', height: 52, borderBottom: '1px solid #1e2030', background: '#13131a', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 20 }}>🧬</span>
          <span style={{ fontWeight: 700, fontSize: 16, color: '#a78bfa' }}>Tyranid Hive</span>
          <span style={{ fontSize: 11, color: '#475569', marginLeft: 4 }}>军情司</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ fontSize: 11, color: connected ? '#22c55e' : '#ef4444' }}>
            {connected ? '● 已连接' : '○ 断线'}
          </span>
          {stats ? (
            <span style={{ fontSize: 11, color: '#475569' }}>
              <span style={{ color: '#22c55e' }}>{stats.active}</span> 活跃
              {' / '}
              <span>{stats.total}</span> 总计
              {stats.complete > 0 && <> · <span style={{ color: '#475569' }}>{stats.complete} 完成</span></>}
            </span>
          ) : (
            <span style={{ fontSize: 11, color: '#475569' }}>加载中…</span>
          )}
          <button onClick={() => setShowCreate(true)} style={{ padding: '5px 14px', background: '#7c3aed', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>
            + 新战团
          </button>
          <button onClick={() => refreshTasks(search || undefined, stateFilter || undefined)} disabled={loading} style={{ padding: '5px 12px', background: '#1e2030', border: '1px solid #2d3148', borderRadius: 6, color: '#94a3b8', cursor: 'pointer', fontSize: 12 }}>
            {loading ? '…' : '↺'}
          </button>
        </div>
      </header>

      {/* Tab */}
      <nav style={{ display: 'flex', gap: 2, padding: '8px 20px 0', borderBottom: '1px solid #1e2030', background: '#13131a', flexShrink: 0 }}>
        {(['tasks', 'genes', 'synapses'] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '6px 16px', border: 'none', borderRadius: '6px 6px 0 0', cursor: 'pointer', fontSize: 13,
            background: tab === t ? '#1e2030' : 'transparent',
            color: tab === t ? '#a78bfa' : '#64748b',
            borderBottom: tab === t ? '2px solid #7c3aed' : '2px solid transparent',
          }}>
            {t === 'tasks' ? '🐛 战团' : t === 'genes' ? '🧬 基因库' : '🧠 小主脑'}
          </button>
        ))}
      </nav>

      {/* 搜索 + 状态筛选 + 排序栏（仅在战团 tab 显示） */}
      {tab === 'tasks' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px', background: '#0d0d10', borderBottom: '1px solid #1e2030', flexShrink: 0, flexWrap: 'wrap' }}>
          {/* 搜索框 */}
          <div style={{ position: 'relative', flex: '0 0 220px' }}>
            <span style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', fontSize: 12, color: '#475569', pointerEvents: 'none' }}>🔍</span>
            <input
              value={search}
              onChange={e => handleSearchChange(e.target.value)}
              placeholder="搜索战团…"
              style={{
                width: '100%', boxSizing: 'border-box',
                padding: '5px 8px 5px 26px',
                background: '#1e2030', border: '1px solid #2d3148', borderRadius: 6,
                color: '#e2e8f0', fontSize: 12, outline: 'none',
              }}
            />
          </div>
          {/* 状态筛选按钮组 */}
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {STATE_FILTERS.map(s => (
              <button
                key={s || 'all'}
                onClick={() => handleStateFilter(s)}
                style={{
                  padding: '3px 10px', fontSize: 11, border: 'none', borderRadius: 4, cursor: 'pointer',
                  background: stateFilter === s ? '#7c3aed' : '#1e2030',
                  color: stateFilter === s ? '#fff' : '#64748b',
                  fontWeight: stateFilter === s ? 600 : 400,
                }}
              >
                {s || '全部'}
              </button>
            ))}
          </div>
          {/* 排序下拉 */}
          <select
            value={sortOpt}
            onChange={e => handleSortChange(e.target.value as SortOption)}
            style={{
              padding: '4px 8px', fontSize: 11, background: '#1e2030', border: '1px solid #2d3148',
              borderRadius: 4, color: '#94a3b8', cursor: 'pointer', outline: 'none',
            }}
          >
            {SORT_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          {/* 搜索结果计数 */}
          {(search || stateFilter) && (
            <span style={{ fontSize: 11, color: '#475569', marginLeft: 4 }}>
              {tasks.length} 条结果
              <button
                onClick={() => { setSearch(''); setStateFilter(''); refreshTasks() }}
                style={{ marginLeft: 6, fontSize: 10, color: '#475569', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}
              >
                清除
              </button>
            </span>
          )}
        </div>
      )}

      {/* 主体 */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {tab === 'tasks' && (
          <>
            <TaskList tasks={tasks} selected={selectedTask} onSelect={setSelectedTask} />
            <TaskDetail task={selectedTask} onTransition={handleTransition} onRefresh={refreshTasks} onDelete={handleDelete} onPatch={handlePatch} />
            <EventStream events={events} />
          </>
        )}
        {tab === 'genes' && <GeneLibrary />}
        {tab === 'synapses' && <SynapsePanel synapses={synapses} />}
      </div>

      {showCreate && <CreateTaskModal onConfirm={handleCreate} onCancel={() => setShowCreate(false)} />}
    </div>
  )
}
