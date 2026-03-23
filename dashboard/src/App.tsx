import { useState, useEffect, useCallback, useRef } from 'react'
import { fetchTasks, fetchSynapses, fetchStats, createTask, transitionTask } from './api'
import type { Task, Synapse, BusEvent, TaskStats } from './api'
import { useHiveWebSocket } from './useWebSocket'
import ChannelSidebar from './components/ChannelSidebar'
import TrunkChat from './components/TrunkChat'
import DetailPanel from './components/DetailPanel'
import CreateTaskModal from './components/CreateTaskModal'

type Tab = 'tasks' | 'genes' | 'synapses' | 'stats'

const STATE_FILTERS = ['', 'Incubating', 'Planning', 'Reviewing', 'Executing', 'Complete', 'Cancelled'] as const
type StateFilter = typeof STATE_FILTERS[number]

const SORT_OPTIONS = [
  { value: 'updated_at:desc', label: 'Most recently updated' },
  { value: 'updated_at:asc', label: 'Oldest updated' },
  { value: 'created_at:desc', label: 'Most recently created' },
  { value: 'priority:asc', label: 'Priority ascending' },
  { value: 'state:asc', label: 'State ascending' },
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
      if (q) params.q = q
      if (state) params.state = state
      const [ts, st] = await Promise.all([fetchTasks(params), fetchStats()])
      setTasks(ts)
      setStats(st)
      if (selectedTask) {
        const updated = ts.find(task => task.id === selectedTask.id)
        if (updated) setSelectedTask(updated)
      }
    } finally {
      setLoading(false)
    }
  }, [selectedTask, sortOpt])

  useEffect(() => { void refreshTasks() }, [refreshTasks])
  useEffect(() => { void fetchSynapses().then(setSynapses) }, [])

  const handleSearchChange = (value: string) => {
    setSearch(value)
    if (searchTimer.current) clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => {
      void refreshTasks(value || undefined, stateFilter || undefined)
    }, 300)
  }

  const handleStateFilter = (state: StateFilter) => {
    setStateFilter(state)
    void refreshTasks(search || undefined, state || undefined)
  }

  const handleSortChange = (value: SortOption) => {
    setSortOpt(value)
    void refreshTasks(search || undefined, stateFilter || undefined, value)
  }

  const handleWsEvent = useCallback((event: BusEvent) => {
    if (event.topic.startsWith('task.')) {
      void refreshTasks(search || undefined, stateFilter || undefined)
    }
  }, [refreshTasks, search, stateFilter])

  const { connected, events } = useHiveWebSocket(handleWsEvent)

  const handleTransition = async (taskId: string, newState: string) => {
    await transitionTask(taskId, newState)
    await refreshTasks(search || undefined, stateFilter || undefined)
  }

  const handleDelete = (taskId: string) => {
    setTasks(taskList => taskList.filter(task => task.id !== taskId))
    if (selectedTask?.id === taskId) setSelectedTask(null)
  }

  const handlePatch = (updated: Task) => {
    setTasks(taskList => taskList.map(task => task.id === updated.id ? updated : task))
    if (selectedTask?.id === updated.id) setSelectedTask(updated)
  }

  const handleCreate = async (title: string, description: string, priority: string) => {
    await createTask({ title, description, priority })
    setShowCreate(false)
    await refreshTasks(search || undefined, stateFilter || undefined)
  }

  void STATE_FILTERS
  void SORT_OPTIONS
  void setTab
  void handleSearchChange
  void handleStateFilter
  void handleSortChange
  void handleTransition
  void handleDelete
  void handlePatch

  return (
    <div
      style={{ display: 'flex', height: '100vh', background: '#0d0d10', color: '#e2e8f0', overflow: 'hidden' }}
      data-tab={tab}
      data-loading={loading}
      data-synapse-count={synapses.length}
      data-task-total={stats?.total ?? 0}
    >
      <ChannelSidebar
        tasks={tasks}
        selectedId={selectedTask?.id ?? null}
        onSelect={id => setSelectedTask(id ? tasks.find(task => task.id === id) ?? null : null)}
        connected={connected}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <TrunkChat selectedTask={selectedTask} events={events} />
      </div>
      <DetailPanel
        selectedTask={selectedTask}
        onCreateTask={({ title, description }) => handleCreate(title, description, 'medium')}
        onRefresh={() => refreshTasks(search || undefined, stateFilter || undefined)}
      />
      {showCreate && <CreateTaskModal onConfirm={handleCreate} onCancel={() => setShowCreate(false)} />}
    </div>
  )
}
