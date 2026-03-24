import { LoaderCircle, Search, Wifi, WifiOff } from 'lucide-react'
import type { Task, TaskStats } from '../api'
import {
  displayTaskDescription,
  displayTaskTitle,
  formatLifecycleState,
} from '../utils/display'

interface Props {
  tasks: Task[]
  selectedTaskId: string | null
  onSelectTask: (id: string) => void
  connected: boolean
  loading: boolean
  search: string
  onSearchChange: (value: string) => void
  stats: TaskStats | null
  synapseCount: number
}

export default function ChannelSidebar({
  tasks,
  selectedTaskId,
  onSelectTask,
  connected,
  loading,
  search,
  onSearchChange,
  stats,
  synapseCount,
}: Props) {
  const activeTasks = tasks.filter(task => !['Complete', 'Cancelled'].includes(task.state))
  const doneTasks = tasks.filter(task => ['Complete', 'Cancelled'].includes(task.state))

  return (
    <aside className="flex h-[38vh] min-h-[300px] w-full shrink-0 flex-col overflow-hidden rounded-[32px] border border-[var(--cl-border)] bg-[var(--cl-panel)] shadow-[0_20px_60px_rgba(119,83,56,0.10)] backdrop-blur-xl lg:h-full lg:w-[312px]">
      <div className="border-b border-[var(--cl-border)] px-5 pb-5 pt-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-[11px] uppercase tracking-[0.28em] text-[var(--cl-warning)]">灰风</div>
            <h1 className="mt-2 text-[30px] font-semibold tracking-[-0.04em] text-[var(--cl-text)]">任务</h1>
            <p className="mt-2 text-sm leading-6 text-[var(--cl-muted)]">
              左边选任务，中间看对话，底部直接发起新任务。
            </p>
          </div>
          <div className="rounded-[22px] border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] px-3 py-2 text-right">
            <div className="text-[10px] uppercase tracking-[0.2em] text-[var(--cl-dim)]">代理</div>
            <div className="mt-1 text-lg font-semibold text-[var(--cl-success)]">{synapseCount}</div>
          </div>
        </div>

        <div className="mt-5 flex items-center justify-between rounded-[22px] border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] px-3 py-2.5">
          <div className="flex items-center gap-2 text-sm text-[var(--cl-text)]">
            {connected ? <Wifi className="h-4 w-4 text-[var(--cl-success)]" /> : <WifiOff className="h-4 w-4 text-[var(--cl-danger)]" />}
            <span>{connected ? '实时连接正常' : '实时连接断开'}</span>
          </div>
          {loading ? <LoaderCircle className="h-4 w-4 animate-spin text-[var(--cl-primary)]" /> : null}
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2">
          <StatCard label="总数" value={stats?.total ?? tasks.length} />
          <StatCard label="进行中" value={stats?.active ?? activeTasks.length} tone="text-[var(--cl-success)]" />
          <StatCard label="已完成" value={(stats?.complete ?? 0) + (stats?.cancelled ?? 0)} tone="text-[var(--cl-dim)]" />
        </div>

        <label className="mt-4 block">
          <span className="mb-1.5 block text-[11px] uppercase tracking-[0.2em] text-[var(--cl-dim)]">搜索任务</span>
          <span className="flex items-center gap-2 rounded-[22px] border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] px-3 py-2.5">
            <Search className="h-4 w-4 text-[var(--cl-dim)]" />
            <input
              className="w-full bg-transparent text-sm text-[var(--cl-text)] outline-none placeholder:text-[var(--cl-dim)]"
              onChange={event => onSearchChange(event.target.value)}
              placeholder="按标题、描述或任务 ID 搜索"
              value={search}
            />
          </span>
        </label>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
        <TaskSection title={`进行中 ${activeTasks.length}`} tasks={activeTasks} selectedTaskId={selectedTaskId} onSelectTask={onSelectTask} />
        <TaskSection title={`已完成 ${doneTasks.length}`} tasks={doneTasks} selectedTaskId={selectedTaskId} onSelectTask={onSelectTask} />
      </div>
    </aside>
  )
}

function StatCard({ label, value, tone = 'text-[var(--cl-primary)]' }: { label: string; value: number; tone?: string }) {
  return (
    <div className="rounded-[22px] border border-[var(--cl-border)] bg-[var(--cl-panel-strong)] px-3 py-2.5">
      <div className="text-[10px] uppercase tracking-[0.2em] text-[var(--cl-dim)]">{label}</div>
      <div className={`mt-1 text-lg font-semibold ${tone}`}>{value}</div>
    </div>
  )
}

function TaskSection({
  title,
  tasks,
  selectedTaskId,
  onSelectTask,
}: {
  title: string
  tasks: Task[]
  selectedTaskId: string | null
  onSelectTask: (id: string) => void
}) {
  return (
    <section className="mb-5">
      <div className="mb-2 px-2 text-[11px] uppercase tracking-[0.2em] text-[var(--cl-dim)]">{title}</div>
      <div className="space-y-2">
        {tasks.length === 0 ? (
          <div className="rounded-[24px] border border-dashed border-[var(--cl-border)] bg-[rgba(255,255,255,0.48)] px-4 py-6 text-center text-sm text-[var(--cl-dim)]">
            暂无任务
          </div>
        ) : (
          tasks.map(task => {
            const description = displayTaskDescription(task)
            const active = task.id === selectedTaskId
            return (
              <button
                key={task.id}
                type="button"
                data-testid={`task-card-${task.id}`}
                onClick={() => onSelectTask(task.id)}
                className={`w-full rounded-[26px] border px-4 py-3 text-left transition ${
                  active
                    ? 'border-[var(--cl-success)] bg-[var(--cl-success-soft)] shadow-[0_16px_36px_rgba(93,124,87,0.10)]'
                    : 'border-[var(--cl-border)] bg-[rgba(255,255,255,0.58)] hover:border-[rgba(93,72,47,0.24)] hover:bg-[var(--cl-panel-strong)]'
                }`}
              >
                <div className="truncate text-sm font-semibold text-[var(--cl-text)]">{displayTaskTitle(task)}</div>
                <div className="mt-1 text-xs text-[var(--cl-dim)]">{task.id}</div>
                {description ? (
                  <div className="mt-2 line-clamp-2 text-xs leading-5 text-[var(--cl-muted)]">
                    {description}
                  </div>
                ) : null}
                <div className="mt-3 flex items-center justify-between gap-3">
                  <span className="rounded-full bg-[var(--cl-primary-soft)] px-2.5 py-1 text-[11px] font-medium text-[var(--cl-primary)]">
                    {formatLifecycleState(task.state)}
                  </span>
                  <span className="text-[11px] text-[var(--cl-dim)]">{formatCompactTime(task.updated_at)}</span>
                </div>
              </button>
            )
          })
        )}
      </div>
    </section>
  )
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
