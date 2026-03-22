import { useState, useEffect, useCallback } from 'react'
import {
  fetchOverviewStats, fetchTimeline, fetchEvolutionStatus, triggerEvolveDomain,
} from '../api'
import type { OverviewStats, TimelineData, EvolutionStatus } from '../api'

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
  const [timeline, setTimeline] = useState<TimelineData | null>(null)
  const [evolution, setEvolution] = useState<EvolutionStatus | null>(null)
  const [timelineDays, setTimelineDays] = useState(14)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [evolving, setEvolving] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    Promise.all([
      fetchOverviewStats(),
      fetchTimeline(timelineDays),
      fetchEvolutionStatus(),
    ])
      .then(([s, t, e]) => { setStats(s); setTimeline(t); setEvolution(e) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [timelineDays])

  useEffect(() => { load() }, [load])

  const handleEvolve = async (domain: string) => {
    setEvolving(domain)
    try {
      await triggerEvolveDomain(domain)
      load()
    } finally {
      setEvolving(null)
    }
  }

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

      {/* 生物质净值曲线 */}
      {timeline && (
        <Card title="生物质净值曲线" accent="#a855f7">
          <div style={{ display: 'flex', gap: 8, marginBottom: 10, alignItems: 'center' }}>
            <span style={{ fontSize: 11, color: '#475569' }}>时间窗口：</span>
            {[7, 14, 30].map(d => (
              <button
                key={d}
                onClick={() => { setTimelineDays(d) }}
                style={{
                  ...btnStyle,
                  background: timelineDays === d ? '#a855f733' : '#1e2030',
                  color: timelineDays === d ? '#a855f7' : '#94a3b8',
                  border: timelineDays === d ? '1px solid #a855f744' : '1px solid #2d3148',
                }}
              >
                {d}天
              </button>
            ))}
          </div>
          <SparklineChart points={timeline.points} />
          <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 11, color: '#475569' }}>
            <span style={{ color: '#a855f7' }}>── 生物质净值</span>
            <span style={{ color: '#22c55e' }}>── 今日完成</span>
            <span style={{ color: '#0891b2' }}>── 今日经验</span>
          </div>
        </Card>
      )}

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

      {/* Evolution Master 进化状态 */}
      {evolution && evolution.domains.length > 0 && (
        <Card title={`进化状态（阈值 ${evolution.threshold} 条成功经验）`} accent="#f59e0b">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {evolution.domains.map(d => (
              <div key={d.domain} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: d.ready_to_evolve ? '#f59e0b' : '#475569', fontSize: 12, minWidth: 80 }}>
                  {d.ready_to_evolve ? '⚡' : '·'} {d.domain}
                </span>
                <div style={{ flex: 1, height: 4, background: '#1e2030', borderRadius: 2 }}>
                  <div style={{
                    width: `${Math.min(100, (d.success_count / evolution.threshold) * 100)}%`,
                    height: '100%',
                    background: d.ready_to_evolve ? '#f59e0b' : '#334155',
                    borderRadius: 2,
                    transition: 'width 0.3s',
                  }} />
                </div>
                <span style={{ fontSize: 11, color: '#475569', minWidth: 40, textAlign: 'right' }}>
                  {d.success_count}/{evolution.threshold}
                </span>
                {d.ready_to_evolve && (
                  <button
                    onClick={() => handleEvolve(d.domain)}
                    disabled={evolving === d.domain}
                    style={{ ...btnStyle, color: '#f59e0b', border: '1px solid #f59e0b44', fontSize: 10 }}
                  >
                    {evolving === d.domain ? '进化中…' : '萃取'}
                  </button>
                )}
              </div>
            ))}
          </div>
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

// ── 生物质净值曲线（纯 SVG）────────────────────────────────

function SparklineChart({ points }: { points: { date: string; net_biomass: number; tasks_completed: number; lessons_added: number }[] }) {
  if (!points.length) return null
  const W = 600, H = 80, PAD = 4
  const maxBio = Math.max(...points.map(p => p.net_biomass), 1)
  const maxBar = Math.max(...points.map(p => Math.max(p.tasks_completed, p.lessons_added)), 1)
  const xStep = (W - PAD * 2) / Math.max(points.length - 1, 1)

  // 生物质净值折线
  const bioLine = points.map((p, i) => {
    const x = PAD + i * xStep
    const y = H - PAD - ((p.net_biomass / maxBio) * (H - PAD * 2))
    return `${x},${y}`
  }).join(' ')

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 80 }}>
      {/* 背景网格 */}
      {[0.25, 0.5, 0.75, 1].map(f => (
        <line key={f} x1={PAD} y1={H - PAD - f * (H - PAD * 2)} x2={W - PAD} y2={H - PAD - f * (H - PAD * 2)}
          stroke="#1e2030" strokeWidth="1" />
      ))}

      {/* 每日完成任务（绿色柱） */}
      {points.map((p, i) => {
        const bh = (p.tasks_completed / maxBar) * (H - PAD * 2) * 0.4
        const x = PAD + i * xStep - 3
        return bh > 0 ? (
          <rect key={`c${i}`} x={x} y={H - PAD - bh} width={3} height={bh} fill="#22c55e44" rx={1} />
        ) : null
      })}

      {/* 每日经验新增（蓝色柱） */}
      {points.map((p, i) => {
        const bh = (p.lessons_added / maxBar) * (H - PAD * 2) * 0.4
        const x = PAD + i * xStep + 1
        return bh > 0 ? (
          <rect key={`l${i}`} x={x} y={H - PAD - bh} width={3} height={bh} fill="#0891b244" rx={1} />
        ) : null
      })}

      {/* 净值折线（面积填充） */}
      <defs>
        <linearGradient id="bioGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#a855f7" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#a855f7" stopOpacity="0" />
        </linearGradient>
      </defs>
      {points.length > 1 && (
        <polygon
          points={`${PAD},${H - PAD} ${bioLine} ${PAD + (points.length - 1) * xStep},${H - PAD}`}
          fill="url(#bioGrad)"
        />
      )}
      {points.length > 1 && (
        <polyline points={bioLine} fill="none" stroke="#a855f7" strokeWidth="1.5" strokeLinejoin="round" />
      )}

      {/* 数据点 */}
      {points.map((p, i) => {
        const x = PAD + i * xStep
        const y = H - PAD - ((p.net_biomass / maxBio) * (H - PAD * 2))
        return p.net_biomass > 0 ? (
          <circle key={i} cx={x} cy={y} r={2} fill="#a855f7" />
        ) : null
      })}
    </svg>
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
