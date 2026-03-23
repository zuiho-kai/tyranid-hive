import { useState } from 'react'
import type { CSSProperties } from 'react'
import type { Task } from '../api'

interface Props {
  tasks: Task[]
  selectedId: string | null
  onSelect: (id: string | null) => void
  connected: boolean
}

const COMPLETED_STATES = new Set(['Complete', 'Cancelled'])

const STATE_EMOJI: Record<string, string> = {
  Incubating: '\u{1F95A}',
  Planning: '\u{1F9E0}',
  Reviewing: '\u{1F440}',
  Spawning: '\u{1FABA}',
  Executing: '\u2699\uFE0F',
  Consolidating: '\u{1F9EC}',
  Complete: '\u2705',
  Cancelled: '\u274C',
  Stalled: '\u23F8\uFE0F',
}

const containerStyle: CSSProperties = {
  width: 220,
  flexShrink: 0,
  display: 'flex',
  flexDirection: 'column',
  background: '#0d0d10',
  borderRight: '1px solid #1a1a22',
  color: '#f3f4f6',
  overflow: 'hidden',
}

const headerStyle: CSSProperties = {
  padding: '18px 14px 14px',
  borderBottom: '1px solid #1a1a22',
}

const listStyle: CSSProperties = {
  flex: 1,
  overflowY: 'auto',
  padding: '10px 8px 14px',
}

const sectionTitleStyle: CSSProperties = {
  margin: '14px 6px 6px',
  fontSize: 11,
  fontWeight: 700,
  color: '#6b7280',
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
}

function getTaskEmoji(task: Task): string {
  return STATE_EMOJI[task.state] ?? '\u{1F4CC}'
}

function isCompleted(task: Task): boolean {
  return COMPLETED_STATES.has(task.state)
}

export default function ChannelSidebar({ tasks, selectedId, onSelect, connected }: Props) {
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  const activeTasks = tasks.filter(task => !isCompleted(task))
  const completedTasks = tasks.filter(task => isCompleted(task))

  return (
    <aside style={containerStyle}>
      <div style={headerStyle}>
        <div style={{ fontSize: 18, fontWeight: 800, color: '#c4b5fd', lineHeight: 1.1 }}>
          Tyranid Hive
        </div>
        <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: connected ? '#22c55e' : '#ef4444',
              boxShadow: connected ? '0 0 10px rgba(34, 197, 94, 0.7)' : '0 0 10px rgba(239, 68, 68, 0.6)',
              flexShrink: 0,
            }}
          />
          <span style={{ fontSize: 12, color: connected ? '#86efac' : '#fca5a5', fontWeight: 600 }}>
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      <div style={listStyle}>
        <div style={{ ...sectionTitleStyle, marginTop: 0 }}>Active</div>
        {activeTasks.length > 0 ? (
          activeTasks.map(task => (
            <TaskItem
              key={task.id}
              task={task}
              selected={selectedId === task.id}
              hovered={hoveredId === task.id}
              onClick={() => onSelect(task.id)}
              onHoverChange={setHoveredId}
            />
          ))
        ) : (
          <EmptyState label="No active tasks" />
        )}

        <div style={sectionTitleStyle}>Completed</div>
        {completedTasks.length > 0 ? (
          completedTasks.map(task => (
            <TaskItem
              key={task.id}
              task={task}
              selected={selectedId === task.id}
              hovered={hoveredId === task.id}
              onClick={() => onSelect(task.id)}
              onHoverChange={setHoveredId}
            />
          ))
        ) : (
          <EmptyState label="No completed tasks" />
        )}
      </div>
    </aside>
  )
}

interface TaskItemProps {
  task: Task
  selected: boolean
  hovered: boolean
  onClick: () => void
  onHoverChange: (id: string | null) => void
}

function TaskItem({ task, selected, hovered, onClick, onHoverChange }: TaskItemProps) {
  const completed = isCompleted(task)

  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => onHoverChange(task.id)}
      onMouseLeave={() => onHoverChange(null)}
      style={{
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '10px 12px',
        margin: '0 0 4px',
        border: 'none',
        borderRadius: 10,
        background: selected ? '#6d28d9' : hovered ? '#17171f' : 'transparent',
        color: selected ? '#ffffff' : completed ? '#9ca3af' : '#e5e7eb',
        cursor: 'pointer',
        textAlign: 'left',
        transition: 'background 120ms ease, color 120ms ease',
      }}
    >
      <span style={{ fontSize: 16, lineHeight: 1, flexShrink: 0 }}>{getTaskEmoji(task)}</span>
      <span
        style={{
          flex: 1,
          minWidth: 0,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          fontSize: 13,
          fontWeight: selected ? 700 : 500,
        }}
      >
        {task.title}
      </span>
    </button>
  )
}

function EmptyState({ label }: { label: string }) {
  return (
    <div
      style={{
        margin: '0 0 8px',
        padding: '10px 12px',
        borderRadius: 10,
        background: '#121219',
        color: '#6b7280',
        fontSize: 12,
      }}
    >
      {label}
    </div>
  )
}
