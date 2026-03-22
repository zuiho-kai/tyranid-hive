import { useState, useEffect } from 'react'
import { fetchLessons, fetchPlaybooks } from '../api'
import type { Lesson, Playbook } from '../api'

type Tab = 'lessons' | 'playbooks'

export default function GeneLibrary() {
  const [tab, setTab] = useState<Tab>('lessons')
  const [lessons, setLessons] = useState<Lesson[]>([])
  const [playbooks, setPlaybooks] = useState<Playbook[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    if (tab === 'lessons') {
      fetchLessons().then(setLessons).finally(() => setLoading(false))
    } else {
      fetchPlaybooks().then(setPlaybooks).finally(() => setLoading(false))
    }
  }, [tab])

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Sub-tabs */}
      <div style={{ display: 'flex', gap: 2, padding: '10px 20px 0', borderBottom: '1px solid #1e2030' }}>
        {(['lessons', 'playbooks'] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '5px 14px', border: 'none', borderRadius: '6px 6px 0 0', cursor: 'pointer', fontSize: 12,
            background: tab === t ? '#1e2030' : 'transparent',
            color: tab === t ? '#a78bfa' : '#64748b',
            borderBottom: tab === t ? '2px solid #7c3aed' : '2px solid transparent',
          }}>
            {t === 'lessons' ? '📚 经验教训' : '📖 作战手册'}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
        {loading ? (
          <div style={{ color: '#374151', fontSize: 13 }}>加载中…</div>
        ) : tab === 'lessons' ? (
          <LessonsView lessons={lessons} />
        ) : (
          <PlaybooksView playbooks={playbooks} />
        )}
      </div>
    </div>
  )
}

function LessonsView({ lessons }: { lessons: Lesson[] }) {
  if (lessons.length === 0) {
    return <div style={{ color: '#374151', fontSize: 13, textAlign: 'center', marginTop: 40 }}>暂无经验教训记录</div>
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {lessons.map(l => (
        <div key={l.id} style={{ background: '#13131a', borderRadius: 8, padding: '12px 16px', border: '1px solid #1e2030' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <div style={{ display: 'flex', gap: 6 }}>
              <span style={{ fontSize: 11, padding: '2px 8px', background: '#1e2030', borderRadius: 4, color: '#8b5cf6' }}>{l.domain}</span>
              <span style={{ fontSize: 11, padding: '2px 8px', background: outcomeColor(l.outcome) + '22', borderRadius: 4, color: outcomeColor(l.outcome) }}>{l.outcome}</span>
            </div>
            <span style={{ fontSize: 11, color: '#374151' }}>×{l.frequency}</span>
          </div>
          <div style={{ fontSize: 13, color: '#e2e8f0', lineHeight: 1.6, marginBottom: 6 }}>{l.content}</div>
          {l.tags && <div style={{ fontSize: 11, color: '#475569' }}>{l.tags}</div>}
        </div>
      ))}
    </div>
  )
}

function PlaybooksView({ playbooks }: { playbooks: Playbook[] }) {
  if (playbooks.length === 0) {
    return <div style={{ color: '#374151', fontSize: 13, textAlign: 'center', marginTop: 40 }}>暂无作战手册</div>
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {playbooks.map(p => (
        <div key={p.id} style={{ background: '#13131a', borderRadius: 8, padding: '12px 16px', border: `1px solid ${p.is_active ? '#2d3148' : '#1a1a24'}`, opacity: p.is_active ? 1 : 0.6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
            <div>
              <span style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0' }}>{p.title}</span>
              {p.crystallized && <span style={{ marginLeft: 6, fontSize: 10, color: '#06b6d4', border: '1px solid #06b6d4', borderRadius: 3, padding: '1px 5px' }}>晶化</span>}
            </div>
            <div style={{ display: 'flex', gap: 6, fontSize: 11, color: '#64748b' }}>
              <span>v{p.version}</span>
              <span>·</span>
              <span style={{ color: p.is_active ? '#22c55e' : '#374151' }}>{p.is_active ? '活跃' : '归档'}</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, fontSize: 11, color: '#475569', marginBottom: 6 }}>
            <span>{p.domain}</span>
            <span>·</span>
            <span>使用 {p.use_count} 次</span>
            <span>·</span>
            <span>成功率 {Math.round(p.success_rate * 100)}%</span>
          </div>
          <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.5, whiteSpace: 'pre-wrap', maxHeight: 80, overflow: 'hidden' }}>{p.content}</div>
        </div>
      ))}
    </div>
  )
}

function outcomeColor(outcome: string): string {
  if (outcome === 'success') return '#22c55e'
  if (outcome === 'failure') return '#ef4444'
  if (outcome === 'partial') return '#f59e0b'
  return '#64748b'
}
