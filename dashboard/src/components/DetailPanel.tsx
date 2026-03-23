import { useState, type CSSProperties } from 'react'
import type { Task } from '../api'

interface CreateTaskInput {
  title: string
  description: string
}

interface Props {
  selectedTask: Task | null
  onCreateTask: (input: CreateTaskInput) => void | Promise<void>
  onRefresh: () => void | Promise<void>
}

export default function DetailPanel({ selectedTask, onCreateTask, onRefresh }: Props) {
  const [isFormOpen, setIsFormOpen] = useState<boolean>(false)
  const [title, setTitle] = useState<string>('')
  const [description, setDescription] = useState<string>('')
  const [isCreating, setIsCreating] = useState<boolean>(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const stateHistory = selectedTask?.flow_log ?? []

  const handleCreate = async (): Promise<void> => {
    const nextTitle = title.trim()
    const nextDescription = description.trim()

    if (!nextTitle) {
      setCreateError('Title is required.')
      return
    }

    setIsCreating(true)
    setCreateError(null)

    try {
      await onCreateTask({
        title: nextTitle,
        description: nextDescription,
      })
      setTitle('')
      setDescription('')
      setIsFormOpen(false)
    } catch (error: unknown) {
      setCreateError(error instanceof Error ? error.message : 'Failed to create task.')
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <aside style={panelStyle}>
      <div style={headerStyle}>
        <button
          type="button"
          onClick={() => {
            setIsFormOpen(prev => !prev)
            setCreateError(null)
          }}
          style={{
            ...primaryButtonStyle,
            width: '100%',
          }}
        >
          {isFormOpen ? 'Close Create Task' : 'Create Task'}
        </button>

        {isFormOpen && (
          <div style={cardStyle}>
            <div style={sectionLabelStyle}>New Task</div>
            <input
              type="text"
              value={title}
              onChange={event => setTitle(event.target.value)}
              placeholder="Task title"
              style={inputStyle}
            />
            <textarea
              value={description}
              onChange={event => setDescription(event.target.value)}
              placeholder="Task description"
              rows={4}
              style={textareaStyle}
            />
            {createError && <div style={errorTextStyle}>{createError}</div>}
            <div style={formActionsStyle}>
              <button
                type="button"
                onClick={handleCreate}
                disabled={isCreating}
                style={primaryButtonStyle}
              >
                {isCreating ? 'Creating...' : 'Submit'}
              </button>
              <button
                type="button"
                onClick={() => void onRefresh()}
                style={secondaryButtonStyle}
              >
                Refresh
              </button>
            </div>
          </div>
        )}
      </div>

      <div style={contentStyle}>
        {selectedTask ? (
          <>
            <div style={taskTitleStyle}>{selectedTask.title}</div>

            <div style={cardStyle}>
              <div style={sectionLabelStyle}>Status</div>
              <div style={statusBadgeStyle}>{selectedTask.state}</div>
            </div>

            <div style={cardStyle}>
              <div style={sectionLabelStyle}>Description</div>
              <div style={bodyTextStyle}>
                {selectedTask.description?.trim() || 'No description provided.'}
              </div>
            </div>

            <div style={cardStyle}>
              <div style={sectionLabelStyle}>State History</div>
              {stateHistory.length > 0 ? (
                <div style={timelineStyle}>
                  {stateHistory
                    .slice()
                    .reverse()
                    .map((entry, index) => (
                      <div key={`${entry.ts}-${entry.to}-${index}`} style={timelineItemStyle}>
                        <div style={timelineRailStyle}>
                          <span style={timelineDotStyle} />
                          {index < stateHistory.length - 1 && <span style={timelineLineStyle} />}
                        </div>
                        <div style={timelineContentStyle}>
                          <div style={timelineStateStyle}>
                            <span style={timelineStateFromStyle}>{entry.from ?? 'Start'}</span>
                            <span style={timelineArrowStyle}>→</span>
                            <span>{entry.to}</span>
                          </div>
                          <div style={timelineMetaStyle}>
                            {formatDateTime(entry.ts)} | {entry.agent}
                          </div>
                          {entry.reason && <div style={timelineReasonStyle}>{entry.reason}</div>}
                        </div>
                      </div>
                    ))}
                </div>
              ) : (
                <div style={emptyTextStyle}>No state transitions recorded.</div>
              )}
            </div>
          </>
        ) : (
          <div style={emptyStateStyle}>
            <div style={sectionLabelStyle}>Task Details</div>
            <div style={emptyTextStyle}>Select a task to inspect its status, description, and history.</div>
          </div>
        )}
      </div>
    </aside>
  )
}

function formatDateTime(value: string): string {
  const parsed = new Date(value)

  if (Number.isNaN(parsed.getTime())) {
    return value
  }

  return parsed.toLocaleString('zh-CN', {
    hour12: false,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const panelStyle: CSSProperties = {
  width: 300,
  minWidth: 300,
  height: '100%',
  display: 'flex',
  flexDirection: 'column',
  background: '#0d0d10',
  borderLeft: '1px solid #1e2030',
  color: '#e8ebf5',
  boxSizing: 'border-box',
}

const headerStyle: CSSProperties = {
  padding: 16,
  borderBottom: '1px solid #1e2030',
}

const contentStyle: CSSProperties = {
  flex: 1,
  overflowY: 'auto',
  padding: 16,
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
}

const cardStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 10,
  padding: 12,
  border: '1px solid #1a1d2c',
  borderRadius: 10,
  background: '#111319',
}

const taskTitleStyle: CSSProperties = {
  fontSize: 18,
  fontWeight: 700,
  lineHeight: 1.4,
  color: '#f5f7ff',
}

const sectionLabelStyle: CSSProperties = {
  fontSize: 11,
  letterSpacing: 1.2,
  textTransform: 'uppercase',
  color: '#7f8aa3',
}

const bodyTextStyle: CSSProperties = {
  fontSize: 13,
  lineHeight: 1.6,
  color: '#c4cbe0',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
}

const statusBadgeStyle: CSSProperties = {
  display: 'inline-flex',
  alignSelf: 'flex-start',
  padding: '5px 10px',
  borderRadius: 999,
  background: '#1a2338',
  border: '1px solid #2a3654',
  color: '#8fb7ff',
  fontSize: 12,
  fontWeight: 600,
}

const inputStyle: CSSProperties = {
  width: '100%',
  padding: '10px 12px',
  borderRadius: 8,
  border: '1px solid #2a2d3f',
  background: '#090a0f',
  color: '#f3f5fb',
  outline: 'none',
  boxSizing: 'border-box',
  fontSize: 13,
}

const textareaStyle: CSSProperties = {
  ...inputStyle,
  resize: 'vertical',
  minHeight: 96,
  fontFamily: 'inherit',
}

const formActionsStyle: CSSProperties = {
  display: 'flex',
  gap: 8,
}

const primaryButtonStyle: CSSProperties = {
  padding: '10px 12px',
  border: '1px solid #35508f',
  borderRadius: 8,
  background: '#1f3b73',
  color: '#f8fbff',
  cursor: 'pointer',
  fontSize: 13,
  fontWeight: 600,
}

const secondaryButtonStyle: CSSProperties = {
  padding: '10px 12px',
  border: '1px solid #2a2d3f',
  borderRadius: 8,
  background: '#131620',
  color: '#c4cbe0',
  cursor: 'pointer',
  fontSize: 13,
}

const errorTextStyle: CSSProperties = {
  fontSize: 12,
  color: '#ff8e8e',
}

const emptyStateStyle: CSSProperties = {
  ...cardStyle,
  marginTop: 'auto',
  marginBottom: 'auto',
}

const emptyTextStyle: CSSProperties = {
  fontSize: 13,
  lineHeight: 1.6,
  color: '#95a0b8',
}

const timelineStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 10,
}

const timelineItemStyle: CSSProperties = {
  display: 'flex',
  gap: 10,
}

const timelineRailStyle: CSSProperties = {
  width: 14,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  flexShrink: 0,
}

const timelineDotStyle: CSSProperties = {
  width: 8,
  height: 8,
  borderRadius: '50%',
  background: '#6ea8ff',
  marginTop: 5,
}

const timelineLineStyle: CSSProperties = {
  width: 1,
  flex: 1,
  marginTop: 4,
  background: '#2a2d3f',
}

const timelineContentStyle: CSSProperties = {
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
  paddingBottom: 10,
}

const timelineStateStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  fontSize: 13,
  fontWeight: 600,
  color: '#e8ebf5',
}

const timelineStateFromStyle: CSSProperties = {
  color: '#9aa5bf',
}

const timelineArrowStyle: CSSProperties = {
  color: '#5d6882',
}

const timelineMetaStyle: CSSProperties = {
  fontSize: 11,
  color: '#75809a',
}

const timelineReasonStyle: CSSProperties = {
  fontSize: 12,
  lineHeight: 1.5,
  color: '#bcc5da',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
}
