import { LoaderCircle, Search, Wifi, WifiOff } from 'lucide-react'
import type { ChannelKey } from '../App'
import type { Task, TaskStats } from '../api'

interface Props {
  tasks: Task[]
  selectedTaskId: string | null
  selectedChannel: ChannelKey
  onSelectTask: (id: string) => void
  onSelectChannel: (channel: ChannelKey) => void
  connected: boolean
  loading: boolean
  search: string
  onSearchChange: (value: string) => void
  stats: TaskStats | null
  synapseCount: number
}

const CHANNELS: Array<{ id: ChannelKey; label: string; blurb: string }> = [
  { id: 'trunk', label: 'Trunk', blurb: 'Primary mission thread' },
  { id: 'trial', label: 'Trial', blurb: 'A/B race and verdicts' },
  { id: 'chain', label: 'Chain', blurb: 'Sequential handoffs' },
  { id: 'swarm', label: 'Swarm', blurb: 'Parallel units and counts' },
  { id: 'ledger', label: 'Ledger', blurb: 'Raw state and event audit' },
]

export default function ChannelSidebar({
  tasks,
  selectedTaskId,
  selectedChannel,
  onSelectTask,
  onSelectChannel,
  connected,
  loading,
  search,
  onSearchChange,
  stats,
  synapseCount,
}: Props) {
  const active = tasks.filter(task => !['Complete', 'Cancelled'].includes(task.state))
  const closed = tasks.filter(task => ['Complete', 'Cancelled'].includes(task.state))

  return (
    <aside className="flex h-[36vh] min-h-[280px] w-full shrink-0 flex-col overflow-hidden rounded-[30px] border border-white/10 bg-[rgba(11,9,16,0.78)] shadow-[0_24px_70px_rgba(0,0,0,0.35)] backdrop-blur-xl lg:h-full lg:w-[300px]">
      <div className="border-b border-white/10 px-5 pb-5 pt-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-[11px] uppercase tracking-[0.36em] text-[#9e90b8]">Clowder Rail</div>
            <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.04em] text-[#f8f3ed]">GreyWind Hive</h1>
            <p className="mt-2 text-sm leading-6 text-[#aa9ebc]">
              Direct tasking, observable execution, and Codex-backed mission control.
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-right">
            <div className="text-[10px] uppercase tracking-[0.24em] text-[#8d7fa6]">Nodes</div>
            <div className="mt-1 text-lg font-semibold text-[#7ee2a8]">{synapseCount}</div>
          </div>
        </div>

        <div className="mt-5 flex items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-3 py-2.5">
          <div className="flex items-center gap-2 text-sm text-[#f8f3ed]">
            {connected ? <Wifi className="h-4 w-4 text-[#7ee2a8]" /> : <WifiOff className="h-4 w-4 text-[#f09c9c]" />}
            <span>{connected ? 'Realtime stream online' : 'Realtime stream offline'}</span>
          </div>
          {loading ? <LoaderCircle className="h-4 w-4 animate-spin text-[#c9b6e7]" /> : null}
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2">
          <StatCard label="Total" value={stats?.total ?? tasks.length} />
          <StatCard label="Active" value={stats?.active ?? active.length} tone="text-[#7ee2a8]" />
          <StatCard label="Closed" value={(stats?.complete ?? 0) + (stats?.cancelled ?? 0)} tone="text-[#c7bfd4]" />
        </div>

        <label className="mt-4 block">
          <span className="mb-1.5 block text-[11px] uppercase tracking-[0.24em] text-[#8d7fa6]">Search missions</span>
          <span className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-3 py-2.5">
            <Search className="h-4 w-4 text-[#8d7fa6]" />
            <input
              className="w-full bg-transparent text-sm text-[#f8f3ed] outline-none placeholder:text-[#71667f]"
              onChange={event => onSearchChange(event.target.value)}
              placeholder="Title, mode, or id"
              value={search}
            />
          </span>
        </label>
      </div>

      <div className="border-b border-white/10 px-3 py-4">
        <div className="mb-2 px-2 text-[11px] uppercase tracking-[0.24em] text-[#8d7fa6]">Channels</div>
        <div className="space-y-2">
          {CHANNELS.map(channel => {
            const activeTone = selectedChannel === channel.id
            return (
              <button
                key={channel.id}
                type="button"
                data-testid={`channel-${channel.id}`}
                onClick={() => onSelectChannel(channel.id)}
                className={`w-full rounded-2xl border px-3 py-3 text-left transition ${
                  activeTone
                    ? 'border-[#a88fe0] bg-[rgba(168,143,224,0.18)]'
                    : 'border-white/8 bg-white/[0.04] hover:border-white/20 hover:bg-white/[0.07]'
                }`}
              >
                <div className="text-sm font-semibold text-[#f8f3ed]">{channel.label}</div>
                <div className="mt-1 text-xs text-[#9d90b1]">{channel.blurb}</div>
              </button>
            )
          })}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
        <TaskSection title={`Active • ${active.length}`} tasks={active} selectedTaskId={selectedTaskId} onSelectTask={onSelectTask} />
        <TaskSection title={`Closed • ${closed.length}`} tasks={closed} selectedTaskId={selectedTaskId} onSelectTask={onSelectTask} />
      </div>
    </aside>
  )
}

function StatCard({ label, value, tone = 'text-[#c9b6e7]' }: { label: string; value: number; tone?: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2.5">
      <div className="text-[10px] uppercase tracking-[0.24em] text-[#8d7fa6]">{label}</div>
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
      <div className="mb-2 px-2 text-[11px] uppercase tracking-[0.24em] text-[#8d7fa6]">{title}</div>
      <div className="space-y-2">
        {tasks.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.04] px-4 py-6 text-center text-sm text-[#7d708d]">
            No missions here yet.
          </div>
        ) : (
          tasks.map(task => (
            <button
              key={task.id}
              type="button"
              data-testid={`task-card-${task.id}`}
              onClick={() => onSelectTask(task.id)}
              className={`w-full rounded-3xl border px-4 py-3 text-left transition ${
                task.id === selectedTaskId
                  ? 'border-[#68cf95] bg-[rgba(104,207,149,0.12)]'
                  : 'border-white/8 bg-white/[0.04] hover:border-white/20 hover:bg-white/[0.08]'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-[#f8f3ed]">{task.title}</div>
                  <div className="mt-1 text-xs text-[#827694]">{task.id}</div>
                </div>
                <span className="rounded-full border border-white/10 px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-[#9d90b1]">
                  {task.exec_mode ?? 'auto'}
                </span>
              </div>
              <div className="mt-3 flex items-center justify-between gap-3">
                <span className="rounded-full bg-white/8 px-2.5 py-1 text-[11px] font-medium text-[#d8cfeb]">{task.state}</span>
                <span className="text-[11px] text-[#7d708d]">{formatCompactTime(task.updated_at)}</span>
              </div>
            </button>
          ))
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
