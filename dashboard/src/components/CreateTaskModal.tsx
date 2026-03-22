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

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
      <div style={{ background: '#13131a', border: '1px solid #2d3148', borderRadius: 12, padding: 24, width: 420, maxWidth: '90vw' }}>
        <h3 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 700, color: '#e2e8f0' }}>新战团</h3>

        <label style={{ display: 'block', marginBottom: 14 }}>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>任务名称 *</div>
          <input
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="战团任务简述…"
            autoFocus
            style={{
              width: '100%', padding: '8px 12px', background: '#0f0f12', border: '1px solid #2d3148',
              borderRadius: 6, color: '#e2e8f0', fontSize: 13, outline: 'none', boxSizing: 'border-box',
            }}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSubmit()}
          />
        </label>

        <label style={{ display: 'block', marginBottom: 14 }}>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>描述</div>
          <textarea
            value={description}
            onChange={e => setDescription(e.target.value)}
            rows={3}
            placeholder="详细描述（可选）…"
            style={{
              width: '100%', padding: '8px 12px', background: '#0f0f12', border: '1px solid #2d3148',
              borderRadius: 6, color: '#e2e8f0', fontSize: 13, outline: 'none', resize: 'vertical', boxSizing: 'border-box',
            }}
          />
        </label>

        <label style={{ display: 'block', marginBottom: 20 }}>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>优先级</div>
          <select
            value={priority}
            onChange={e => setPriority(e.target.value)}
            style={{
              padding: '8px 12px', background: '#0f0f12', border: '1px solid #2d3148',
              borderRadius: 6, color: '#e2e8f0', fontSize: 13, outline: 'none', cursor: 'pointer',
            }}
          >
            <option value="low">低</option>
            <option value="normal">普通</option>
            <option value="high">高</option>
            <option value="critical">紧急</option>
          </select>
        </label>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button
            onClick={onCancel}
            style={{ padding: '7px 16px', background: 'transparent', border: '1px solid #2d3148', borderRadius: 6, color: '#64748b', cursor: 'pointer', fontSize: 13 }}
          >
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={!title.trim() || submitting}
            style={{
              padding: '7px 16px', background: '#7c3aed', border: 'none', borderRadius: 6,
              color: '#fff', cursor: title.trim() && !submitting ? 'pointer' : 'not-allowed',
              fontSize: 13, fontWeight: 600, opacity: title.trim() && !submitting ? 1 : 0.5,
            }}
          >
            {submitting ? '创建中…' : '创建战团'}
          </button>
        </div>
      </div>
    </div>
  )
}
