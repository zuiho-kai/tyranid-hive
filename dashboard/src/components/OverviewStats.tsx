import { useState, useEffect } from 'react'
import { fetchOverviewStats } from '../api'
import type { OverviewStats } from '../api'

const STATE_COLOR: Record<string, string> = {
  Incubating: '#7c3aed', Planning: '#2563eb', Executing: '#0891b2',
  Reviewing: '#d97706', Consolidating: '#059669', Complete: '#16a34a',
  Dormant: '#475569', Cancelled: '#dc2626',
}

const OUTCOME_COLOR: Record<string, string> = {
  success: '#22c55e', failure: '#ef4444', partial: '#f59e0b', unknown: '#64748b',
}

export default function OverviewStats() {
  const [stats, setStats] = useState<OverviewStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    setError(null)
    fetchOverviewStats()
      .then(setStats)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  if (loading) return <div style={{ color: '#374151', fontSize: 13, padding: 20 }}>加载中…</div>
  if (error || !stats) return (
    <div style={{ color: '#ef4444', fontSize: 13, padding: 20 }}>
      加载失败：{error ?? '未知错误'} &nbsp;
      <button onClick={load} style={btnStyle}>重试</button>
    </div>
  )

  const { tasks, lessons, playbooks } = stats

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 刷新 */}
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button onClick={load} style={btnStyle}>↺ 刷新</button>
      </div>

      {/* 顶部三卡片 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
        <Card title="战斗任务" accent="#7c3aed">
          <BigNum value={tasks.total} label="总计" />
        </Card>
        <Card title="经验教训" accent="#0891b2">
          <BigNum value={lessons.total} label="条记录" />
        </Card>
        <Card title="作战手册" accent="#059669">
          <div style={{ display: 'flex', gap: 16 }}>
            <BigNum value={playbooks.active} label="活跃" />
            <BigNum value={playbooks.crystallized} label="已结晶" accent="#06b6d4" />
          </div>
        </Card>
      </div>

      {/* 任务状态分布 */}
      {Object.keys(tasks.by_state).length > 0 && (
        <Card title="任务状态分布" accent="#7c3aed">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {Object.entries(tasks.by_state).map(([state, count]) => (
              <StatBadge
                key={state}
                label={state}
                value={count}
                color={STATE_COLOR[state] ?? '#64748b'}
              />
            ))}
          </div>
        </Card>
      )}

      {/* 经验库：领域分布 + 结果分布 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {Object.keys(lessons.by_domain).length > 0 && (
          <Card title="经验库 · 领域分布" accent="#0891b2">
            <BarChart
              data={lessons.by_domain}
              total={lessons.total}
              colorFn={() => '#0891b2'}
            />
          </Card>
        )}
        {Object.keys(lessons.by_outcome).length > 0 && (
          <Card title="经验库 · 结果分布" accent="#0891b2">
            <BarChart
              data={lessons.by_outcome}
              total={lessons.total}
              colorFn={k => OUTCOME_COLOR[k] ?? '#64748b'}
            />
          </Card>
        )}
      </div>

      {/* 最活跃经验 */}
      {lessons.top_active.length > 0 && (
        <Card title="最活跃经验（命中频次 Top 5）" accent="#0891b2">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {lessons.top_active.map((l, i) => (
              <div key={l.id} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 12 }}>
                <span style={{ color: '#475569', minWidth: 16 }}>{i + 1}.</span>
                <span style={{ color: '#8b5cf6', minWidth: 60 }}>{l.domain}</span>
                <span style={{ color: '#e2e8f0', flex: 1, lineHeight: 1.5 }}>{l.content}</span>
                <span style={{ color: '#22c55e', minWidth: 30, textAlign: 'right' }}>×{l.frequency}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* 手册领域分布 */}
      {Object.keys(playbooks.by_domain).length > 0 && (
        <Card title="作战手册 · 领域分布" accent="#059669">
          <BarChart
            data={playbooks.by_domain}
            total={playbooks.active}
            colorFn={() => '#059669'}
          />
        </Card>
      )}

      {/* 空状态 */}
      {tasks.total === 0 && lessons.total === 0 && playbooks.total === 0 && (
        <div style={{ color: '#374151', fontSize: 13, textAlign: 'center', marginTop: 40 }}>
          虫巢尚未孵化任何数据 —— 创建第一个任务开始吧
        </div>
      )}
    </div>
  )
}

// ── 子组件 ────────────────────────────────────────────────

function Card({ title, accent, children }: { title: string; accent: string; children: React.ReactNode }) {
  return (
    <div style={{ background: '#13131a', borderRadius: 8, padding: '12px 16px', border: `1px solid ${accent}33` }}>
      <div style={{ fontSize: 11, color: accent, fontWeight: 600, marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {title}
      </div>
      {children}
    </div>
  )
}

function BigNum({ value, label, accent = '#e2e8f0' }: { value: number; label: string; accent?: string }) {
  return (
    <div>
      <div style={{ fontSize: 28, fontWeight: 700, color: accent, lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>{label}</div>
    </div>
  )
}

function StatBadge({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5, background: color + '18', borderRadius: 5, padding: '4px 10px', border: `1px solid ${color}44` }}>
      <span style={{ fontSize: 11, color }}>{label}</span>
      <span style={{ fontSize: 13, fontWeight: 700, color }}>{value}</span>
    </div>
  )
}

function BarChart({
  data,
  total,
  colorFn,
}: {
  data: Record<string, number>
  total: number
  colorFn: (key: string) => string
}) {
  const sorted = Object.entries(data).sort((a, b) => b[1] - a[1])
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      {sorted.map(([key, count]) => {
        const pct = total > 0 ? Math.round((count / total) * 100) : 0
        const color = colorFn(key)
        return (
          <div key={key}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2, fontSize: 11 }}>
              <span style={{ color: '#94a3b8' }}>{key}</span>
              <span style={{ color }}>{count} ({pct}%)</span>
            </div>
            <div style={{ height: 4, background: '#1e2030', borderRadius: 2 }}>
              <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.3s' }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

const btnStyle: React.CSSProperties = {
  padding: '4px 10px', background: '#1e2030', border: '1px solid #2d3148',
  borderRadius: 5, color: '#94a3b8', cursor: 'pointer', fontSize: 11,
}
