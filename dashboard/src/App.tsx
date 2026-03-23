import { useEffect, useRef, useState, useCallback } from 'react'
import { createTask, fetchStats, fetchSynapses, fetchTasks } from './api'
import type { BusEvent, Synapse, Task, TaskStats } from './api'
import { useHiveWebSocket } from './useWebSocket'
import ChannelSidebar from './components/ChannelSidebar'
import DetailPanel from './components/DetailPanel'
import TrunkChat from './components/TrunkChat'

export interface UserMessage {
  id: string
  taskId: string
  content: string
  ts: string
}

const STATE_FILTERS = [
  '',
  'Incubating',
  'Planning',
  'Reviewing',
  'Spawning',
  'Executing',
  'Consolidating',
  'Dormant',
  'Complete',
  'Cancelled',
] as const

const SORT_OPTIONS = [
  { value: 'updated_at:desc', label: 'Recently updated' },
  { value: 'created_at:desc', label: 'Recently created' },
  { value: 'priority:asc', label: 'Priority' },
  { value: 'state:asc', label: 'State' },
] as const

type StateFilter = typeof STATE_FILTERS[number]
type SortOption = typeof SORT_OPTIONS[number]['value']

const DONE_STATES = new Set(['Complete', 'Cancelled'])

export default function App() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [synapses, setSynapses] = useState<Synapse[]>([])
  const [stats, setStats] = useState<TaskStats | null>(null)
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [stateFilter, setStateFilter] = useState<StateFilter>('')
  const [sortOpt, setSortOpt] = useState<SortOption>('updated_at:desc')
  const [userMessages, setUserMessages] = useState<Record<string, UserMessage[]>>({})
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const refreshTasks = useCallback(
    async (q?: string, state?: string, sort: SortOption = sortOpt) => {
      setLoading(true)
      try {
        const [sortBy, order] = sort.split(':')
        const params: { q?: string; state?: string; sort_by?: string; order?: string } = {
          sort_by: sortBy,
          order,
        }
        if (q) params.q = q
        if (state) params.state = state

        const [nextTasks, nextStats] = await Promise.all([fetchTasks(params), fetchStats()])
        setTasks(nextTasks)
        setStats(nextStats)
        setSelectedTask(current => {
          if (!current) return current
          return nextTasks.find(task => task.id === current.id) ?? null
        })
      } finally {
        setLoading(false)
      }
    },
    [sortOpt],
  )

  useEffect(() => {
    void fetchSynapses().then(setSynapses)
  }, [])

  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => {
      void refreshTasks(search || undefined, stateFilter || undefined, sortOpt)
    }, 220)
    return () => {
      if (searchTimer.current) clearTimeout(searchTimer.current)
    }
  }, [refreshTasks, search, sortOpt, stateFilter])

  useEffect(() => {
    if (tasks.length === 0) {
      setSelectedTask(null)
      return
    }

    setSelectedTask(current => {
      if (current) {
        const matched = tasks.find(task => task.id === current.id)
        if (matched) return matched
      }
      return tasks.find(task => !DONE_STATES.has(task.state)) ?? tasks[0]
    })
  }, [tasks])

  const handleWsEvent = useCallback(
    (event: BusEvent) => {
      if (event.topic.startsWith('task.')) {
        void refreshTasks(search || undefined, stateFilter || undefined, sortOpt)
      }
    },
    [refreshTasks, search, sortOpt, stateFilter],
  )

  const { connected, events } = useHiveWebSocket(handleWsEvent)

  const handleCreateTask = async (input: {
    title: string
    description: string
    priority: string
  }) => {
    await createTask(input)
    await refreshTasks(search || undefined, stateFilter || undefined, sortOpt)
  }

  const handleSendMessage = (taskId: string, content: string) => {
    const message: UserMessage = {
      id: `user-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      taskId,
      content,
      ts: new Date().toISOString(),
    }

    setUserMessages(current => ({
      ...current,
      [taskId]: [...(current[taskId] ?? []), message],
    }))
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-ww-base text-ww-main">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(155,126,189,0.18),transparent_30%),radial-gradient(circle_at_bottom_right,rgba(226,149,120,0.16),transparent_26%),linear-gradient(180deg,rgba(255,255,255,0.45),transparent_40%)]" />
      <div className="relative flex h-screen min-h-0 p-3 md:p-4">
        <div className="flex min-h-0 w-full flex-col gap-3 lg:flex-row lg:gap-0 lg:overflow-hidden lg:rounded-[30px] lg:border lg:border-ww-subtle lg:bg-[rgba(255,250,245,0.78)] lg:shadow-[0_28px_70px_rgba(42,35,64,0.14)] lg:backdrop-blur-xl">
        <ChannelSidebar
          connected={connected}
          loading={loading}
          onSearchChange={setSearch}
          onSelect={taskId => setSelectedTask(tasks.find(task => task.id === taskId) ?? null)}
          onSortChange={value => setSortOpt(value as SortOption)}
          onStateFilterChange={value => setStateFilter(value as StateFilter)}
          search={search}
          selectedId={selectedTask?.id ?? null}
          sortOpt={sortOpt}
          sortOptions={SORT_OPTIONS}
          stateFilter={stateFilter}
          stateOptions={STATE_FILTERS}
          stats={stats}
          synapseCount={synapses.length}
          tasks={tasks}
        />
        <div className="min-h-0 min-w-0 flex-1 overflow-hidden lg:border-x lg:border-ww-subtle">
          <TrunkChat
            events={events}
            onSendMessage={handleSendMessage}
            selectedTask={selectedTask}
            userMessages={selectedTask ? userMessages[selectedTask.id] ?? [] : []}
          />
        </div>
        <DetailPanel
          onCreateTask={handleCreateTask}
          onRefresh={() => refreshTasks(search || undefined, stateFilter || undefined, sortOpt)}
          selectedTask={selectedTask}
          synapses={synapses}
        />
        </div>
      </div>
    </div>
  )
}
