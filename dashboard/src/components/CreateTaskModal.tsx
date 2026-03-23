import { useState } from 'react'

interface Props {
  onConfirm: (title: string, description: string, priority: string) => Promise<void>
  onCancel: () => void
}

export default function CreateTaskModal({ onConfirm, onCancel }: Props) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState('normal')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    if (!title.trim()) return
    setSubmitting(true)
    try {
      await onConfirm(title.trim(), description.trim(), priority)
    } finally {
      setSubmitting(false)
    }
  }

  const canSubmit = title.trim().length > 0 && !submitting

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60">
      <div className="w-[420px] max-w-[90vw] rounded-xl border border-ww-subtle bg-ww-surface p-6">
        <h3 className="mb-5 text-base font-bold text-ww-main">Create task</h3>

        <label className="mb-3.5 block">
          <div className="mb-1.5 text-[11px] uppercase tracking-wider text-ww-dim">Title *</div>
          <input
            autoFocus
            className="w-full rounded-md border border-ww-subtle bg-ww-base px-3 py-2 text-[13px] text-ww-main outline-none placeholder:text-ww-dim"
            onChange={event => setTitle(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter' && !event.shiftKey) {
                void handleSubmit()
              }
            }}
            placeholder="Task summary"
            value={title}
          />
        </label>

        <label className="mb-3.5 block">
          <div className="mb-1.5 text-[11px] uppercase tracking-wider text-ww-dim">Description</div>
          <textarea
            className="w-full resize-y rounded-md border border-ww-subtle bg-ww-base px-3 py-2 text-[13px] text-ww-main outline-none placeholder:text-ww-dim"
            onChange={event => setDescription(event.target.value)}
            placeholder="Describe the task in more detail"
            rows={3}
            value={description}
          />
        </label>

        <label className="mb-5 block">
          <div className="mb-1.5 text-[11px] uppercase tracking-wider text-ww-dim">Priority</div>
          <select
            className="cursor-pointer rounded-md border border-ww-subtle bg-ww-base px-3 py-2 text-[13px] text-ww-main outline-none"
            onChange={event => setPriority(event.target.value)}
            value={priority}
          >
            <option value="low">Low</option>
            <option value="normal">Normal</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </label>

        <div className="flex justify-end gap-2">
          <button
            className="rounded-md border border-ww-subtle bg-transparent px-4 py-[7px] text-[13px] text-ww-dim transition-colors hover:bg-ww-card"
            onClick={onCancel}
            type="button"
          >
            Cancel
          </button>
          <button
            className="rounded-md border-none bg-opus-primary px-4 py-[7px] text-[13px] font-semibold text-white transition-colors hover:bg-opus-dark disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!canSubmit}
            onClick={() => void handleSubmit()}
            type="button"
          >
            {submitting ? 'Creating…' : 'Create task'}
          </button>
        </div>
      </div>
    </div>
  )
}
