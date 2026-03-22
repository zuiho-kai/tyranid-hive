import type { Task } from '../api'

const STATE_COLOR: Record<string, string> = {
  Incubating:    '#6366f1',
  Planning:      '#8b5cf6',
  Reviewing:     '#a78bfa',
  Spawning:      '#06b6d4',
  Executing:     '#22c55e',
  Consolidating: '#f59e0b',
  Complete:      '#475569',
  Dormant:       '#ef4444',
  Cancelled:     '#374151',
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
  const active   = tasks.filter(t => !['Complete', 'Cancelled'].includes(t.state))
  const finished = tasks.filter(t => ['Complete', 'Cancelled'].includes(t.state))

  return (
    <div style={{ width: 280, borderRight: '1px solid #1e2030', display: 'flex', flexDirection: 'column', overflow: 'hidden', flexShrink: 0 }}>
      <div style={{ padding: '10px 14px 6px', fontSize: 11, color: '#475569', borderBottom: '1px solid #1e2030', letterSpacing: 1, textTransform: 'uppercase' }}>
        活跃 ({active.length})
      </div>
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {active.map(t => <TaskRow key={t.id} task={t} selected={selected?.id === t.id} onSelect={onSelect} />)}
        {finished.length > 0 && (
          <>
            <div style={{ padding: '8px 14px 4px', fontSize: 11, color: '#374151', letterSpacing: 1, textTransform: 'uppercase' }}>
              已完成 ({finished.length})
            </div>
            {finished.map(t => <TaskRow key={t.id} task={t} selected={selected?.id === t.id} onSelect={onSelect} />)}
          </>
        )}
        {tasks.length === 0 && (
          <div style={{ padding: 20, color: '#374151', fontSize: 13, textAlign: 'center' }}>
            暂无战团<br /><span style={{ fontSize: 11 }}>点击「新战团」开始</span>
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
      style={{
        padding: '9px 14px', cursor: 'pointer', borderBottom: '1px solid #1a1a24',
        background: selected ? '#1e2030' : 'transparent',
        borderLeft: selected ? '2px solid #7c3aed' : '2px solid transparent',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: dot, flexShrink: 0, display: 'inline-block' }} />
        <span style={{ fontSize: 13, fontWeight: 500, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {task.title}
        </span>
        <span style={{ fontSize: 10, color: pri, flexShrink: 0 }}>
          {task.priority !== 'normal' ? task.priority : ''}
        </span>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#475569' }}>
        <span>{task.state}</span>
        <span>{task.id.split('-').pop()}</span>
      </div>
    </div>
  )
}
