import type { ReactNode } from 'react'
import type { ChannelKey, MissionDraft } from '../App'
import type { BusEvent, Synapse, Task } from '../api'

interface Props {
  selectedTask: Task | null
  selectedChannel: ChannelKey
  events: BusEvent[]
  draft: MissionDraft
  synapses: Synapse[]
}

export default function DetailPanel({
  selectedTask,
  selectedChannel,
  events,
  draft,
  synapses,
}: Props) {
  const taskEvents = selectedTask
    ? events.filter(event => event.trace_id === selectedTask.trace_id || event.payload?.task_id === selectedTask.id)
    : []
  const lastEvent = taskEvents[0] ?? null
  const currentStage = typeof lastEvent?.payload?.stage === 'string' ? lastEvent.payload.stage : 'idle'

  return (
    <aside className="flex h-[34vh] min-h-[280px] w-full shrink-0 flex-col overflow-hidden rounded-[30px] border border-white/10 bg-[rgba(8,7,12,0.78)] shadow-[0_24px_70px_rgba(0,0,0,0.35)] backdrop-blur-xl lg:h-full lg:w-[340px]">
      <div className="border-b border-white/10 px-5 pb-4 pt-5">
        <div className="text-[11px] uppercase tracking-[0.32em] text-[#8d7fa6]">Inspector</div>
        <h2 className="mt-2 text-[26px] font-semibold tracking-[-0.03em] text-[#f8f3ed]">
          {selectedTask ? 'Task telemetry' : 'Composer state'}
        </h2>
        <p className="mt-2 text-sm leading-6 text-[#a79bb8]">
          {selectedTask
            ? 'Current mode, stage, and event audit for the selected mission.'
            : 'Draft summary and available synapses before launch.'}
        </p>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
        <Panel title="Session Snapshot">
          <MetricRow label="Channel" value={selectedChannel} />
          <MetricRow label="Draft mode" value={draft.mode} />
          <MetricRow label="Priority" value={draft.priority} />
          <MetricRow label="Synapses" value={String(synapses.length)} />
        </Panel>

        {selectedTask ? (
          <>
            <Panel title="Task State">
              <MetricRow label="Task" value={selectedTask.title} />
              <MetricRow label="Task ID" value={selectedTask.id} mono />
              <MetricRow label="State" value={selectedTask.state} />
              <MetricRow label="Mode" value={selectedTask.exec_mode ?? 'auto'} />
              <MetricRow label="Stage" value={currentStage} mono testId="current-stage" />
              <MetricRow label="Progress" value={String(selectedTask.progress_log.length)} testId="progress-count" />
              <MetricRow label="Todos" value={`${selectedTask.todos.filter(todo => todo.done).length}/${selectedTask.todos.length}`} />
            </Panel>

            <Panel title="Task Notes">
              <div className="rounded-[22px] border border-white/10 bg-white/[0.04] px-4 py-3 text-sm leading-7 text-[#ded7e9]">
                {selectedTask.description?.trim() || 'No description provided.'}
              </div>
            </Panel>

            <Panel title="Mode Config">
              <pre data-testid="mode-config" className="overflow-x-auto rounded-[22px] border border-white/10 bg-black/20 p-3 text-[11px] leading-6 text-[#b6acc8]">
                {JSON.stringify(selectedTask.meta ?? {}, null, 2)}
              </pre>
            </Panel>

            <Panel title="Latest Event">
              {lastEvent ? (
                <>
                  <MetricRow label="Type" value={lastEvent.event_type} />
                  <MetricRow label="Producer" value={lastEvent.producer} />
                  <MetricRow label="When" value={formatTs(lastEvent.created_at)} />
                  <pre className="mt-3 overflow-x-auto rounded-[22px] border border-white/10 bg-black/20 p-3 text-[11px] leading-6 text-[#b6acc8]">
                    {JSON.stringify(lastEvent.payload, null, 2)}
                  </pre>
                </>
              ) : (
                <Empty text="No realtime event for this task yet." />
              )}
            </Panel>
          </>
        ) : (
          <>
            <Panel title="Draft Preview">
              <div className="rounded-[22px] border border-white/10 bg-white/[0.04] px-4 py-3 text-sm leading-7 text-[#ded7e9]">
                {draft.message.trim() || 'Start writing the mission in the console to see a live preview here.'}
              </div>
            </Panel>

            <Panel title="Available Synapses">
              <div className="space-y-2">
                {synapses.map(synapse => (
                  <div key={synapse.id} className="rounded-[22px] border border-white/10 bg-white/[0.04] px-3 py-3">
                    <div className="flex items-center gap-2 text-sm font-semibold text-[#f8f3ed]">
                      <span>{synapse.emoji}</span>
                      <span>{synapse.name}</span>
                    </div>
                    <div className="mt-1 text-xs text-[#988cae]">{synapse.role}</div>
                  </div>
                ))}
              </div>
            </Panel>
          </>
        )}
      </div>
    </aside>
  )
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-[26px] border border-white/10 bg-[rgba(255,255,255,0.04)] p-4">
      <div className="mb-3 text-[11px] uppercase tracking-[0.24em] text-[#8d7fa6]">{title}</div>
      {children}
    </section>
  )
}

function MetricRow({ label, value, mono = false, testId }: { label: string; value: string; mono?: boolean; testId?: string }) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5" data-testid={testId}>
      <span className="text-xs uppercase tracking-[0.16em] text-[#8d7fa6]">{label}</span>
      <span className={`text-right text-sm text-[#f8f3ed] ${mono ? 'font-mono text-[12px]' : ''}`}>{value}</span>
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return (
    <div className="rounded-[22px] border border-dashed border-white/10 bg-black/10 px-4 py-4 text-sm text-[#9185a6]">
      {text}
    </div>
  )
}

function formatTs(value: string) {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
