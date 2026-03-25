import { LoaderCircle, Search, Wifi, WifiOff } from 'lucide-react'
import type { Task, TaskStats } from '../api'
import type { TaskFilterKey } from '../App'
import {
  displayTaskDescription,
  displayTaskTitle,
  formatLifecycleState,
} from '../utils/display'

interface Props {
  tasks: Task[]
  selectedTaskId: string | null
  selectedFilter: TaskFilterKey
  onSelectTask: (id: string) => void
  onSelectFilter: (filter: TaskFilterKey) => void
  connected: boolean
  loading: boolean
  search: string
  onSearchChange: (value: string) => void
  stats: TaskStats | null
  synapseCount: number
  counts: Record<TaskFilterKey, number>
}

const FILTERS: Array<{ id: TaskFilterKey; label: string }> = [
  { id: 'active', label: '进行中' },
  { id: 'waiting', label: '待补充' },
  { id: 'done', label: '已完成' },
  { id: 'all', label: '全部' },
]

export default function ChannelSidebar({
  tasks,
  selectedTaskId,
  selectedFilter,
  onSelectTask,
  onSelectFilter,
  connected,
  loading,
  search,
  onSearchChange,
  stats,
  synapseCount,
  counts,
}: Props) {
  return (
    <aside className="flex h-[38vh] min-h-[300px] w-full shrink-0 flex-col overflow-hidden rounded-[32px] border border-[var(--cl-border)] bg-[var(--cl-panel)] shadow-[0_20px_60px_rgba(119,83,56,0.10)] backdrop-blur-xl lg:h-full lg:w-[308px]">
      <div className="border-b border-[var(--cl-border)] px-5 pb-5 pt-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-[11px] uppercase tracking-[0.24em] text-[var(--cl-warning)]">灰风</div>
            <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.04em] text-[var(--cl-text)]">任务台</h1>
            <p className="mt-2 text-sm leading-6 text-[var(--cl-muted)]">
              先找到任务，再看对话。
            </p>
          </div>
          <div className="rounded-[22px] border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] px-3 py-2 text-right">
            <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--cl-dim)]">代理</div>
            <div className="mt-1 text-lg font-semibold text-[var(--cl-success)]">{synapseCount}</div>
          </div>
        </div>

        <div className="mt-5 flex items-center justify-between rounded-[22px] border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] px-3 py-2.5">
          <div className="flex items-center gap-2 text-sm text-[var(--cl-text)]">
            {connected ? <Wifi className="h-4 w-4 text-[var(--cl-success)]" /> : <WifiOff className="h-4 w-4 text-[var(--cl-danger)]" />}
            <span>{connected ? '连接正常' : '连接断开'}</span>
          </div>
          {loading ? <LoaderCircle className="h-4 w-4 animate-spin text-[var(--cl-primary)]" /> : null}
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2">
          <StatCard label="总数" value={stats?.total ?? counts.all} />
          <StatCard label="进行中" value={stats?.active ?? counts.active} tone="text-[var(--cl-success)]" />
          <StatCard label="完成" value={(stats?.complete ?? 0) + (stats?.cancelled ?? 0)} tone="text-[var(--cl-dim)]" />
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {FILTERS.map(filter => (
            <button
              key={filter.id}
              type="button"
              onClick={() => onSelectFilter(filter.id)}
              className={`rounded-full border px-3 py-1.5 text-xs transition ${
                selectedFilter === filter.id
                  ? 'border-[var(--cl-primary)] bg-[var(--cl-primary-soft)] text-[var(--cl-text)]'
                  : 'border-[var(--cl-border)] bg-[var(--cl-panel-strong)] text-[var(--cl-muted)]'
              }`}
            >
              {filter.label} {counts[filter.id]}
            </button>
          ))}
        </div>

        <label className="mt-4 block">
          <span className="mb-1.5 block text-[11px] uppercase tracking-[0.16em] text-[var(--cl-dim)]">搜索</span>
          <span className="flex items-center gap-2 rounded-[22px] border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] px-3 py-2.5">
            <Search className="h-4 w-4 text-[var(--cl-dim)]" />
            <input
              className="w-full bg-transparent text-sm text-[var(--cl-text)] outline-none placeholder:text-[var(--cl-dim)]"
              onChange={event => onSearchChange(event.target.value)}
              placeholder="标题、说明或任务 ID"
              value={search}
            />
          </span>
        </label>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
        <div className="mb-2 px-2 text-[11px] uppercase tracking-[0.16em] text-[var(--cl-dim)]">
          {filterTitle(selectedFilter)} {tasks.length}
        </div>
        <div className="space-y-2">
          {tasks.length === 0 ? (
            <div className="rounded-[24px] border border-dashed border-[var(--cl-border)] bg-[rgba(255,255,255,0.48)] px-4 py-6 text-center text-sm text-[var(--cl-dim)]">
              {counts.all === 0 ? '还没有任务，直接在中间输入并创建。' : '当前筛选下没有任务。'}
            </div>
          ) : (
            tasks.map(task => {
              const description = displayTaskDescription(task)
              const active = task.id === selectedTaskId
              const showDescription = description && description !== displayTaskTitle(task)
              return (
                <button
                  key={task.id}
                  type="button"
                  data-testid={`task-card-${task.id}`}
                  onClick={() => onSelectTask(task.id)}
                  className={`w-full rounded-[24px] border px-4 py-3 text-left transition ${
                    active
                      ? 'border-[var(--cl-success)] bg-[var(--cl-success-soft)] shadow-[0_16px_36px_rgba(93,124,87,0.10)]'
                      : 'border-[var(--cl-border)] bg-[rgba(255,255,255,0.58)] hover:border-[rgba(93,72,47,0.24)] hover:bg-[var(--cl-panel-strong)]'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-semibold text-[var(--cl-text)]">{displayTaskTitle(task)}</div>
                      <div className="mt-1 text-[11px] text-[var(--cl-dim)]">{task.id}</div>
                    </div>
                    <span className="shrink-0 rounded-full bg-[var(--cl-primary-soft)] px-2.5 py-1 text-[11px] font-medium text-[var(--cl-primary)]">
                      {formatLifecycleState(task.state)}
                    </span>
                  </div>
                  {showDescription ? (
                    <div className="mt-2 line-clamp-2 text-xs leading-5 text-[var(--cl-muted)]">
                      {description}
                    </div>
                  ) : null}
                  <div className="mt-3 text-right text-[11px] text-[var(--cl-dim)]">{formatCompactTime(task.updated_at)}</div>
                </button>
              )
            })
          )}
        </div>
      </div>
    </aside>
  )
}

function StatCard({ label, value, tone = 'text-[var(--cl-primary)]' }: { label: string; value: number; tone?: string }) {
  return (
    <div className="rounded-[22px] border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] px-3 py-2.5">
      <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--cl-dim)]">{label}</div>
      <div className={`mt-1 text-lg font-semibold ${tone}`}>{value}</div>
    </div>
  )
}

function filterTitle(filter: TaskFilterKey) {
  if (filter === 'active') return '进行中'
  if (filter === 'waiting') return '待补充'
  if (filter === 'done') return '已完成'
  return '全部任务'
}

function formatCompactTime(value: string) {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
