import { useState, type ReactNode } from 'react'
import { RefreshCw, Sparkles } from 'lucide-react'
import type { Synapse, Task } from '../api'

interface CreateTaskInput {
  title: string
  description: string
  priority: string
}

interface Props {
  selectedTask: Task | null
  onCreateTask: (input: CreateTaskInput) => void | Promise<void>
  onRefresh: () => void | Promise<void>
  synapses: Synapse[]
}

const PRIORITY_OPTIONS = ['low', 'normal', 'high', 'critical'] as const

const PRIORITY_STYLES: Record<string, string> = {
  low: 'bg-codex-bg text-codex-dark',
  normal: 'bg-gemini-bg text-gemini-dark',
  high: 'bg-dare-bg text-dare-dark',
  critical: 'bg-cocreator-bg text-cocreator-dark',
}

export default function DetailPanel({
  selectedTask,
  onCreateTask,
  onRefresh,
  synapses,
}: Props) {
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<(typeof PRIORITY_OPTIONS)[number]>('normal')
  const [isCreating, setIsCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const flowLog = selectedTask?.flow_log ?? []
  const progressLog = selectedTask?.progress_log ?? []
  const todos = selectedTask?.todos ?? []

  const handleCreate = async () => {
    const nextTitle = title.trim()
    if (!nextTitle) {
      setCreateError('Title is required.')
      return
    }

    setIsCreating(true)
    setCreateError(null)

    try {
      await onCreateTask({
        title: nextTitle,
        description: description.trim(),
        priority,
      })
      setTitle('')
      setDescription('')
      setPriority('normal')
      setIsFormOpen(false)
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : 'Failed to create task.')
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <aside className="flex h-[32vh] min-h-[260px] w-full shrink-0 flex-col overflow-hidden rounded-[24px] border border-black/10 bg-[#faf3eb]/95 text-[#201c18] shadow-[0_18px_40px_rgba(42,35,64,0.08)] backdrop-blur lg:h-full lg:w-[320px] lg:rounded-none lg:border-0 lg:border-l lg:shadow-none">
      <div className="border-b border-black/10 px-5 pb-4 pt-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-[11px] uppercase tracking-[0.28em] text-[#8d7661]">
              Control Details
            </div>
            <h2 className="mt-2 text-xl font-semibold tracking-[-0.02em] text-[#241d17]">
              Mission Console
            </h2>
            <p className="mt-2 text-sm leading-6 text-[#7b6552]">
              Create tasks, inspect transitions, and keep the active synapse roster in view.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void onRefresh()}
              className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-black/10 bg-white/70 text-[#7b6552] transition hover:border-[#c7ad92] hover:text-[#241d17]"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => {
                setIsFormOpen(current => !current)
                setCreateError(null)
              }}
              className="rounded-2xl bg-[#241d17] px-4 py-2.5 text-sm font-medium text-[#fff8f2] transition hover:bg-[#3a2b20]"
            >
              {isFormOpen ? 'Close' : 'New Task'}
            </button>
          </div>
        </div>
      </div>

      {isFormOpen ? (
        <div className="border-b border-black/10 bg-white/50 px-5 py-4">
          <div className="space-y-3">
            <label className="block">
              <span className="mb-1.5 block text-[11px] uppercase tracking-[0.24em] text-[#8d7661]">
                Title
              </span>
              <input
                type="text"
                value={title}
                onChange={event => setTitle(event.target.value)}
                onKeyDown={event => {
                  if (event.key === 'Enter') {
                    void handleCreate()
                  }
                }}
                placeholder="Describe the mission objective"
                className="w-full rounded-2xl border border-black/10 bg-[#fffdfb] px-3 py-2.5 text-sm text-[#241d17] outline-none placeholder:text-[#b49a84]"
              />
            </label>

            <label className="block">
              <span className="mb-1.5 block text-[11px] uppercase tracking-[0.24em] text-[#8d7661]">
                Description
              </span>
              <textarea
                value={description}
                onChange={event => setDescription(event.target.value)}
                rows={4}
                placeholder="Add context, acceptance criteria, or execution notes"
                className="w-full resize-none rounded-2xl border border-black/10 bg-[#fffdfb] px-3 py-2.5 text-sm text-[#241d17] outline-none placeholder:text-[#b49a84]"
              />
            </label>

            <label className="block">
              <span className="mb-1.5 block text-[11px] uppercase tracking-[0.24em] text-[#8d7661]">
                Priority
              </span>
              <select
                value={priority}
                onChange={event =>
                  setPriority(event.target.value as (typeof PRIORITY_OPTIONS)[number])
                }
                className="w-full rounded-2xl border border-black/10 bg-[#fffdfb] px-3 py-2.5 text-sm text-[#241d17] outline-none"
              >
                {PRIORITY_OPTIONS.map(option => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>

            {createError ? <p className="text-sm text-[#b45252]">{createError}</p> : null}

            <button
              type="button"
              onClick={() => void handleCreate()}
              disabled={isCreating}
              className="inline-flex w-full items-center justify-center rounded-2xl bg-[#5b8c5a] px-4 py-3 text-sm font-medium text-white transition hover:bg-[#466e45] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isCreating ? 'Creating...' : 'Create task'}
            </button>
          </div>
        </div>
      ) : null}

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
        <Panel title="Task Snapshot">
          {selectedTask ? (
            <div className="space-y-4">
              <div>
                <div className="text-lg font-semibold leading-snug text-[#241d17]">
                  {selectedTask.title}
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Badge>{selectedTask.state}</Badge>
                  <Badge tone={selectedTask.priority}>
                    {selectedTask.priority}
                  </Badge>
                  {selectedTask.exec_mode ? <Badge>{selectedTask.exec_mode}</Badge> : null}
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <Metric label="Flow" value={String(flowLog.length)} />
                <Metric label="Progress" value={String(progressLog.length)} />
                <Metric
                  label="Todos"
                  value={`${todos.filter(todo => todo.done).length}/${todos.length}`}
                />
              </div>

              <div className="space-y-2 text-sm text-[#6e5d50]">
                <Row label="Creator" value={selectedTask.creator} />
                <Row
                  label="Assignee"
                  value={selectedTask.assignee_synapse ?? 'Unassigned'}
                />
                <Row label="Task ID" value={selectedTask.id} mono />
                <Row label="Updated" value={formatDate(selectedTask.updated_at)} />
              </div>

              <div className="rounded-2xl bg-[#fffaf5] p-3 text-sm leading-6 text-[#6e5d50]">
                {selectedTask.description?.trim() || 'No description provided.'}
              </div>

              {selectedTask.labels.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {selectedTask.labels.map(label => (
                    <span
                      key={label}
                      className="rounded-full bg-[#efe1d1] px-2.5 py-1 text-xs font-medium text-[#765f4d]"
                    >
                      {label}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ) : (
            <EmptyState
              title="No task selected"
              description="Pick a task from the left rail to inspect its current state and history."
            />
          )}
        </Panel>

        <Panel title="Synapse Roster">
          {synapses.length > 0 ? (
            <div className="space-y-2">
              {synapses.map(synapse => (
                <div
                  key={synapse.id}
                  className="flex items-center justify-between rounded-2xl bg-[#fffaf5] px-3 py-2.5"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm">{synapse.emoji || '::'}</span>
                      <span className="truncate text-sm font-medium text-[#241d17]">
                        {synapse.name}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-[#8d7661]">{synapse.role}</div>
                  </div>
                  <div className="rounded-full bg-[#eaf6ea] px-2 py-1 text-[11px] font-medium text-[#466e45]">
                    T{synapse.tier}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No synapses loaded"
              description="The API did not return any available agents."
            />
          )}
        </Panel>

        <Panel title="Recent Flow">
          {flowLog.length > 0 ? (
            <div className="space-y-3">
              {[...flowLog].reverse().slice(0, 6).map((entry, index) => (
                <div key={`${entry.ts}-${entry.to}-${index}`} className="flex gap-3">
                  <div className="flex w-4 shrink-0 flex-col items-center">
                    <span className="mt-1 h-2 w-2 rounded-full bg-[#9b7ebd]" />
                    {index < Math.min(flowLog.length, 6) - 1 ? (
                      <span className="mt-1 w-px flex-1 bg-[#e4d7ca]" />
                    ) : null}
                  </div>
                  <div className="min-w-0 pb-3">
                    <div className="text-sm font-medium text-[#241d17]">
                      {entry.from ?? 'Start'} to {entry.to}
                    </div>
                    <div className="mt-1 text-xs text-[#8d7661]">
                      {formatDate(entry.ts)} by {entry.agent}
                    </div>
                    {entry.reason ? (
                      <div className="mt-1 text-sm leading-6 text-[#6e5d50]">
                        {entry.reason}
                      </div>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No transitions yet"
              description="State changes will appear here once the task starts moving."
            />
          )}
        </Panel>

        <Panel title="Progress Feed">
          {progressLog.length > 0 ? (
            <div className="space-y-3">
              {[...progressLog].reverse().slice(0, 5).map((entry, index) => (
                <div key={`${entry.ts}-${entry.agent}-${index}`} className="rounded-2xl bg-[#fffaf5] p-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium text-[#241d17]">
                      {entry.agent}
                    </span>
                    <span className="text-xs text-[#8d7661]">{formatDate(entry.ts)}</span>
                  </div>
                  <div className="mt-2 text-sm leading-6 text-[#6e5d50]">
                    {entry.content}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No progress yet"
              description="Agent updates and system writebacks will show up here."
            />
          )}
        </Panel>

        <Panel title="Operator Notes">
          <div className="rounded-2xl bg-[linear-gradient(135deg,#f3eaf8,#fff9f3)] p-4">
            <div className="flex items-start gap-3">
              <div className="rounded-2xl bg-white/80 p-2 text-[#6d5a8c]">
                <Sparkles className="h-4 w-4" />
              </div>
              <div>
                <div className="text-sm font-medium text-[#241d17]">
                  Clowder-inspired operating posture
                </div>
                <p className="mt-1 text-sm leading-6 text-[#6e5d50]">
                  Keep the left rail dense, the center pane conversational, and this panel focused
                  on orchestration facts rather than duplicate content.
                </p>
              </div>
            </div>
          </div>
        </Panel>
      </div>
    </aside>
  )
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-[24px] border border-black/10 bg-white/65 p-4 shadow-[0_16px_48px_rgba(70,45,22,0.06)]">
      <div className="mb-3 text-[11px] uppercase tracking-[0.26em] text-[#8d7661]">
        {title}
      </div>
      {children}
    </section>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-[#fffaf5] px-3 py-2 text-center">
      <div className="text-base font-semibold text-[#241d17]">{value}</div>
      <div className="mt-1 text-[10px] uppercase tracking-[0.2em] text-[#8d7661]">
        {label}
      </div>
    </div>
  )
}

function Badge({
  children,
  tone,
}: {
  children: ReactNode
  tone?: string
}) {
  return (
    <span
      className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
        tone ? PRIORITY_STYLES[tone] ?? 'bg-[#efe7dc] text-[#765f4d]' : 'bg-[#efe7dc] text-[#765f4d]'
      }`}
    >
      {children}
    </span>
  )
}

function Row({
  label,
  value,
  mono,
}: {
  label: string
  value: string
  mono?: boolean
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <span className="text-[#8d7661]">{label}</span>
      <span className={`${mono ? 'font-mono text-[12px]' : ''} text-right text-[#241d17]`}>
        {value}
      </span>
    </div>
  )
}

function EmptyState({
  title,
  description,
}: {
  title: string
  description: string
}) {
  return (
    <div className="rounded-2xl bg-[#fffaf5] px-4 py-5 text-center">
      <div className="text-sm font-medium text-[#241d17]">{title}</div>
      <p className="mt-1 text-sm leading-6 text-[#8d7661]">{description}</p>
    </div>
  )
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}
