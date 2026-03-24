import type { Task } from '../api'

const STATE_COLOR: Record<string, string> = {
  Incubating: '#6366f1', Planning: '#8b5cf6', Reviewing: '#a78bfa',
  Spawning: '#06b6d4', Executing: '#22c55e', Consolidating: '#f59e0b', WaitingInput: '#ef4444',
  Complete: '#475569', Dormant: '#ef4444', Cancelled: '#374151',
}

const PRIORITY_COLOR: Record<string, string> = {
  critical: '#ef4444', high: '#f97316', normal: '#64748b', low: '#374151',
}

interface Props {
  tasks: Task[]
  selected: Task | null
  onSelect: (t: Task) => void
}

export default function TaskList({ tasks, selected, onSelect }: Props) {
  const active = tasks.filter(t => !['Complete', 'Cancelled'].includes(t.state))
  const finished = tasks.filter(t => ['Complete', 'Cancelled'].includes(t.state))

  return (
    <div className="w-[280px] border-r border-ww-subtle flex flex-col overflow-hidden shrink-0">
      <div className="px-3.5 pt-2.5 pb-1.5 text-[11px] text-ww-dim border-b border-ww-subtle tracking-wider uppercase">
        活跃 ({active.length})
      </div>
      <div className="flex-1 overflow-y-auto">
        {active.map(t => <TaskRow key={t.id} task={t} selected={selected?.id === t.id} onSelect={onSelect} />)}
        {finished.length > 0 && (
          <>
            <div className="px-3.5 pt-2 pb-1 text-[11px] text-ww-dim tracking-wider uppercase">
              已完成 ({finished.length})
            </div>
            {finished.map(t => <TaskRow key={t.id} task={t} selected={selected?.id === t.id} onSelect={onSelect} />)}
          </>
        )}
        {tasks.length === 0 && (
          <div className="p-5 text-ww-dim text-[13px] text-center">
            暂无战团<br /><span className="text-[11px]">点击「新战团」开始</span>
          </div>
        )}
      </div>
    </div>
  )
}

function TaskRow({ task, selected, onSelect }: { task: Task; selected: boolean; onSelect: (t: Task) => void }) {
  const dot = STATE_COLOR[task.state] ?? '#64748b'
  const pri = PRIORITY_COLOR[task.priority] ?? '#64748b'

  return (
    <div
      onClick={() => onSelect(task)}
      className={`px-3.5 py-[9px] cursor-pointer border-b border-ww-surface transition-colors ${
        selected ? 'bg-ww-card border-l-2 border-l-opus-primary' : 'border-l-2 border-l-transparent hover:bg-ww-surface'
      }`}
    >
      <div className="flex items-center gap-1.5 mb-0.5">
        <span className="w-2 h-2 rounded-full shrink-0 inline-block" style={{ background: dot }} />
        <span className="text-[13px] font-medium flex-1 overflow-hidden text-ellipsis whitespace-nowrap">
          {task.title}
        </span>
        <span className="text-[10px] shrink-0" style={{ color: pri }}>
          {task.priority !== 'normal' ? task.priority : ''}
        </span>
      </div>
      <div className="flex justify-between text-[11px] text-ww-dim">
        <span style={{ color: dot }}>{task.state}</span>
        <span>{task.id.split('-').pop()}</span>
      </div>
    </div>
  )
}
