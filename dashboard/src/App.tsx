import { useState, useEffect, useCallback } from 'react'
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

export default function App() {
  const [tab, setTab] = useState<Tab>('tasks')
  const [tasks, setTasks] = useState<Task[]>([])
  const [synapses, setSynapses] = useState<Synapse[]>([])
  const [stats, setStats] = useState<TaskStats | null>(null)
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [loading, setLoading] = useState(false)

  const refreshTasks = useCallback(async () => {
    setLoading(true)
    try {
      const [ts, st] = await Promise.all([fetchTasks(), fetchStats()])
      setTasks(ts)
      setStats(st)
      if (selectedTask) {
        const updated = ts.find(t => t.id === selectedTask.id)
        if (updated) setSelectedTask(updated)
      }
    } finally {
      setLoading(false)
    }
  }, [selectedTask])

  useEffect(() => { refreshTasks() }, [])
  useEffect(() => { fetchSynapses().then(setSynapses) }, [])

  const handleWsEvent = useCallback((e: BusEvent) => {
    if (e.topic.startsWith('task.')) refreshTasks()
  }, [refreshTasks])

  const { connected, events } = useHiveWebSocket(handleWsEvent)

  const handleTransition = async (taskId: string, newState: string) => {
    await transitionTask(taskId, newState)
    await refreshTasks()
  }

  const handleCreate = async (title: string, description: string, priority: string) => {
    await createTask({ title, description, priority })
    setShowCreate(false)
    await refreshTasks()
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
          {/* 使用 /api/tasks/stats 的精确计数 */}
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
          <button onClick={refreshTasks} disabled={loading} style={{ padding: '5px 12px', background: '#1e2030', border: '1px solid #2d3148', borderRadius: 6, color: '#94a3b8', cursor: 'pointer', fontSize: 12 }}>
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

      {/* 主体 */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {tab === 'tasks' && (
          <>
            <TaskList tasks={tasks} selected={selectedTask} onSelect={setSelectedTask} />
            <TaskDetail task={selectedTask} onTransition={handleTransition} onRefresh={refreshTasks} />
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
