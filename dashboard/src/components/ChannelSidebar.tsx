import { LoaderCircle, Search, Wifi, WifiOff } from 'lucide-react'
import type { Task, TaskStats } from '../api'

interface SortOption {
  value: string
  label: string
}

interface Props {
  tasks: Task[]
  selectedId: string | null
  onSelect: (id: string) => void
  connected: boolean
  loading: boolean
  search: string
  onSearchChange: (value: string) => void
  stateFilter: string
  onStateFilterChange: (value: string) => void
  stateOptions: readonly string[]
  sortOpt: string
  onSortChange: (value: string) => void
  sortOptions: readonly SortOption[]
  stats: TaskStats | null
  synapseCount: number
}

const COMPLETED_STATES = new Set(['Complete', 'Cancelled'])

const STATE_LABELS: Record<string, string> = {
  Incubating: 'Incubating',
  Planning: 'Planning',
  Reviewing: 'Reviewing',
  Spawning: 'Spawning',
  Executing: 'Executing',
  Consolidating: 'Consolidating',
  Dormant: 'Dormant',
  Complete: 'Complete',
  Cancelled: 'Cancelled',
}

const PRIORITY_LABELS: Record<string, string> = {
  critical: 'Critical',
  high: 'High',
  normal: 'Normal',
  low: 'Low',
}

export default function ChannelSidebar({
  tasks,
  selectedId,
  onSelect,
  connected,
  loading,
  search,
  onSearchChange,
  stateFilter,
  onStateFilterChange,
  stateOptions,
  sortOpt,
  onSortChange,
  sortOptions,
  stats,
  synapseCount,
}: Props) {
  const activeTasks = tasks.filter(task => !COMPLETED_STATES.has(task.state))
  const completedTasks = tasks.filter(task => COMPLETED_STATES.has(task.state))

  return (
    <aside className="flex h-[36vh] min-h-[280px] w-full shrink-0 flex-col overflow-hidden rounded-[24px] border border-ww-subtle bg-ww-topbar/95 shadow-[0_18px_40px_rgba(42,35,64,0.08)] backdrop-blur lg:h-full lg:w-[320px] lg:rounded-none lg:border-0 lg:border-r lg:shadow-none">
      <div className="border-b border-ww-subtle px-5 pb-5 pt-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="text-[11px] uppercase tracking-[0.3em] text-ww-dim">Mission Hub</div>
            <h1 className="mt-2 text-2xl font-semibold leading-none text-ww-main">Tyranid Hive</h1>
            <p className="mt-2 text-sm leading-6 text-ww-muted">
              A clowder-style control room for task orchestration, live task flow, and dispatch
              telemetry.
            </p>
          </div>
          <div className="rounded-2xl border border-ww-subtle bg-ww-surface px-3 py-2 text-right">
            <div className="text-[10px] uppercase tracking-[0.25em] text-ww-dim">Nodes</div>
            <div className="mt-1 text-lg font-semibold text-opus-light">{synapseCount}</div>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between rounded-2xl border border-ww-subtle bg-ww-surface px-3 py-2.5">
          <div className="flex items-center gap-2">
            {connected ? (
              <Wifi className="h-4 w-4 text-ww-success" />
            ) : (
              <WifiOff className="h-4 w-4 text-ww-danger" />
            )}
            <span className="text-sm font-medium text-ww-main">
              {connected ? 'Realtime stream online' : 'Realtime stream offline'}
            </span>
          </div>
          {loading ? <LoaderCircle className="h-4 w-4 animate-spin text-opus-light" /> : null}
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2 text-center">
          <SummaryCard label="Total" value={stats?.total ?? tasks.length} />
          <SummaryCard label="Active" value={stats?.active ?? activeTasks.length} accent="text-ww-info" />
          <SummaryCard
            label="Closed"
            value={(stats?.complete ?? 0) + (stats?.cancelled ?? 0)}
            accent="text-ww-muted"
          />
        </div>

        <div className="mt-5 space-y-3">
          <label className="block">
            <span className="mb-1.5 block text-[11px] uppercase tracking-[0.24em] text-ww-dim">
              Search
            </span>
            <span className="flex items-center gap-2 rounded-2xl border border-ww-subtle bg-ww-surface px-3 py-2.5">
              <Search className="h-4 w-4 text-ww-dim" />
              <input
                className="w-full bg-transparent text-sm text-ww-main outline-none placeholder:text-ww-dim"
                onChange={event => onSearchChange(event.target.value)}
                placeholder="Find title, label, or trace"
                value={search}
              />
            </span>
          </label>

          <div className="grid grid-cols-2 gap-2">
            <label className="block">
              <span className="mb-1.5 block text-[11px] uppercase tracking-[0.24em] text-ww-dim">
                State
              </span>
              <select
                className="w-full rounded-2xl border border-ww-subtle bg-ww-surface px-3 py-2.5 text-sm text-ww-main outline-none"
                onChange={event => onStateFilterChange(event.target.value)}
                value={stateFilter}
              >
                {stateOptions.map(option => (
                  <option key={option || 'all'} value={option}>
                    {option || 'All states'}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="mb-1.5 block text-[11px] uppercase tracking-[0.24em] text-ww-dim">
                Sort
              </span>
              <select
                className="w-full rounded-2xl border border-ww-subtle bg-ww-surface px-3 py-2.5 text-sm text-ww-main outline-none"
                onChange={event => onSortChange(event.target.value)}
                value={sortOpt}
              >
                {sortOptions.map(option => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
        <TaskSection
          emptyLabel="No active tasks"
          items={activeTasks}
          onSelect={onSelect}
          selectedId={selectedId}
          title={`Active · ${activeTasks.length}`}
        />
        <TaskSection
          emptyLabel="No completed tasks"
          items={completedTasks}
          onSelect={onSelect}
          selectedId={selectedId}
          title={`Closed · ${completedTasks.length}`}
        />
      </div>
    </aside>
  )
}

function SummaryCard({
  label,
  value,
  accent = 'text-opus-light',
}: {
  label: string
  value: number
  accent?: string
}) {
  return (
    <div className="rounded-2xl border border-ww-subtle bg-ww-surface px-3 py-2.5">
      <div className="text-[10px] uppercase tracking-[0.24em] text-ww-dim">{label}</div>
      <div className={`mt-1 text-lg font-semibold ${accent}`}>{value}</div>
    </div>
  )
}

function TaskSection({
  title,
  items,
  selectedId,
  onSelect,
  emptyLabel,
}: {
  title: string
  items: Task[]
  selectedId: string | null
  onSelect: (id: string) => void
  emptyLabel: string
}) {
  return (
    <section className="mb-5">
      <div className="mb-2 px-2 text-[11px] uppercase tracking-[0.24em] text-ww-dim">{title}</div>
      <div className="space-y-2">
        {items.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-ww-subtle bg-ww-surface px-4 py-6 text-center text-sm text-ww-dim">
            {emptyLabel}
          </div>
        ) : (
          items.map(task => (
            <TaskCard
              key={task.id}
              onClick={() => onSelect(task.id)}
              selected={task.id === selectedId}
              task={task}
            />
          ))
        )}
      </div>
    </section>
  )
}

function TaskCard({
  task,
  selected,
  onClick,
}: {
  task: Task
  selected: boolean
  onClick: () => void
}) {
  const priority = PRIORITY_LABELS[task.priority] ?? task.priority
  const stateLabel = STATE_LABELS[task.state] ?? task.state

  return (
    <button
      className={`w-full rounded-3xl border px-4 py-3 text-left transition ${
        selected
          ? 'border-ww-active bg-[rgba(155,126,189,0.18)] shadow-[0_16px_42px_rgba(8,12,24,0.34)]'
          : 'border-ww-subtle bg-ww-surface hover:border-ww-active hover:bg-[rgba(255,255,255,0.03)]'
      }`}
      onClick={onClick}
      type="button"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-ww-main">{task.title}</div>
          <div className="mt-1 truncate text-xs text-ww-dim">{task.id}</div>
        </div>
        <span className="rounded-full border border-ww-subtle px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-ww-muted">
          {priority}
        </span>
      </div>

      <div className="mt-3 flex items-center justify-between gap-3">
        <span className="inline-flex items-center rounded-full bg-ww-info-soft px-2.5 py-1 text-[11px] font-medium text-ww-info">
          {stateLabel}
        </span>
        <span className="text-[11px] text-ww-dim">{formatCompactTime(task.updated_at)}</span>
      </div>
    </button>
  )
}

function formatCompactTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
