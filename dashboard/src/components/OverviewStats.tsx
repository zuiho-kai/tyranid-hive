import { useState, useEffect, useCallback } from 'react'
import {
  fetchOverviewStats, fetchTimeline, fetchEvolutionStatus, triggerEvolveDomain,
} from '../api'
import type { OverviewStats, TimelineData, EvolutionStatus } from '../api'

const STATE_COLOR: Record<string, string> = {
  Incubating: '#7c3aed', Planning: '#2563eb', Executing: '#0891b2',
  Reviewing: '#d97706', Consolidating: '#059669', WaitingInput: '#dc2626', Complete: '#16a34a',
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
    Promise.all([fetchOverviewStats(), fetchTimeline(timelineDays), fetchEvolutionStatus()])
      .then(([s, t, e]) => { setStats(s); setTimeline(t); setEvolution(e) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [timelineDays])

  useEffect(() => { load() }, [load])

  const handleEvolve = async (domain: string) => {
    setEvolving(domain)
    try { await triggerEvolveDomain(domain); load() } finally { setEvolving(null) }
  }

  if (loading) return <div className="text-ww-dim text-[13px] p-5">加载中…</div>
  if (error || !stats) return (
    <div className="text-ww-danger text-[13px] p-5">
      加载失败：{error ?? '未知错误'} &nbsp;
      <button onClick={load} className="px-2.5 py-1 bg-ww-card border border-ww-subtle rounded text-ww-muted cursor-pointer text-[11px]">重试</button>
    </div>
  )

  const { tasks, lessons, playbooks } = stats

  return (
    <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-4">
      <div className="flex justify-end">
        <button onClick={load} className="px-2.5 py-1 bg-ww-card border border-ww-subtle rounded text-ww-muted cursor-pointer text-[11px] hover:bg-ww-surface transition-colors">↺ 刷新</button>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card title="战斗任务" accent="#7c3aed"><BigNum value={tasks.total} label="总计" /></Card>
        <Card title="经验教训" accent="#0891b2"><BigNum value={lessons.total} label="条记录" /></Card>
        <Card title="作战手册" accent="#059669">
          <div className="flex gap-4">
            <BigNum value={playbooks.active} label="活跃" />
            <BigNum value={playbooks.crystallized} label="已结晶" accent="#06b6d4" />
          </div>
        </Card>
      </div>

      {timeline && (
        <Card title="生物质净值曲线" accent="#a855f7">
          <div className="flex gap-2 mb-2.5 items-center">
            <span className="text-[11px] text-ww-dim">时间窗口：</span>
            {[7, 14, 30].map(d => (
              <button
                key={d}
                onClick={() => setTimelineDays(d)}
                className={`px-2.5 py-1 rounded text-[11px] cursor-pointer border transition-colors ${
                  timelineDays === d
                    ? 'bg-opus-primary/20 text-opus-primary border-opus-primary/25'
                    : 'bg-ww-card text-ww-muted border-ww-subtle hover:bg-ww-surface'
                }`}
              >{d}天</button>
            ))}
          </div>
          <SparklineChart points={timeline.points} />
          <div className="flex gap-4 mt-2 text-[11px] text-ww-dim">
            <span className="text-opus-primary">── 生物质净值</span>
            <span className="text-ww-success">── 今日完成</span>
            <span className="text-gemini-primary">── 今日经验</span>
          </div>
        </Card>
      )}

      {Object.keys(tasks.by_state).length > 0 && (
        <Card title="任务状态分布" accent="#7c3aed">
          <div className="flex flex-wrap gap-2">
            {Object.entries(tasks.by_state).map(([state, count]) => (
              <StatBadge key={state} label={state} value={count} color={STATE_COLOR[state] ?? '#64748b'} />
            ))}
          </div>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-3">
        {Object.keys(lessons.by_domain).length > 0 && (
          <Card title="经验库 · 领域分布" accent="#0891b2">
            <BarChart data={lessons.by_domain} total={lessons.total} colorFn={() => '#0891b2'} />
          </Card>
        )}
        {Object.keys(lessons.by_outcome).length > 0 && (
          <Card title="经验库 · 结果分布" accent="#0891b2">
            <BarChart data={lessons.by_outcome} total={lessons.total} colorFn={k => OUTCOME_COLOR[k] ?? '#64748b'} />
          </Card>
        )}
      </div>

      {lessons.top_active.length > 0 && (
        <Card title="最活跃经验（命中频次 Top 5）" accent="#0891b2">
          <div className="flex flex-col gap-1.5">
            {lessons.top_active.map((l, i) => (
              <div key={l.id} className="flex gap-2 items-start text-xs">
                <span className="text-ww-dim min-w-4">{i + 1}.</span>
                <span className="text-opus-primary min-w-[60px]">{l.domain}</span>
                <span className="text-ww-main flex-1 leading-normal">{l.content}</span>
                <span className="text-ww-success min-w-[30px] text-right">×{l.frequency}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {Object.keys(playbooks.by_domain).length > 0 && (
        <Card title="作战手册 · 领域分布" accent="#059669">
          <BarChart data={playbooks.by_domain} total={playbooks.active} colorFn={() => '#059669'} />
        </Card>
      )}

      {evolution && evolution.domains.length > 0 && (
        <Card title={`进化状态（阈值 ${evolution.threshold} 条成功经验）`} accent="#f59e0b">
          <div className="flex flex-col gap-1.5">
            {evolution.domains.map(d => (
              <div key={d.domain} className="flex items-center gap-2">
                <span className="text-xs min-w-[80px]" style={{ color: d.ready_to_evolve ? '#f59e0b' : undefined }}>
                  {d.ready_to_evolve ? '⚡' : '·'} {d.domain}
                </span>
                <div className="flex-1 h-1 bg-ww-card rounded-sm">
                  <div
                    className="h-full rounded-sm transition-all duration-300"
                    style={{
                      width: `${Math.min(100, (d.success_count / evolution.threshold) * 100)}%`,
                      background: d.ready_to_evolve ? '#f59e0b' : '#334155',
                    }}
                  />
                </div>
                <span className="text-[11px] text-ww-dim min-w-[40px] text-right">{d.success_count}/{evolution.threshold}</span>
                {d.ready_to_evolve && (
                  <button
                    onClick={() => handleEvolve(d.domain)}
                    disabled={evolving === d.domain}
                    className="px-2.5 py-1 bg-ww-card border border-[#f59e0b44] rounded text-[#f59e0b] cursor-pointer text-[10px] hover:bg-ww-surface transition-colors"
                  >{evolving === d.domain ? '进化中…' : '萃取'}</button>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {tasks.total === 0 && lessons.total === 0 && playbooks.total === 0 && (
        <div className="text-ww-dim text-[13px] text-center mt-10">虫巢尚未孵化任何数据 —— 创建第一个任务开始吧</div>
      )}
    </div>
  )
}

function SparklineChart({ points }: { points: { date: string; net_biomass: number; tasks_completed: number; lessons_added: number }[] }) {
  if (!points.length) return null
  const W = 600, H = 80, PAD = 4
  const maxBio = Math.max(...points.map(p => p.net_biomass), 1)
  const maxBar = Math.max(...points.map(p => Math.max(p.tasks_completed, p.lessons_added)), 1)
  const xStep = (W - PAD * 2) / Math.max(points.length - 1, 1)

  const bioLine = points.map((p, i) => {
    const x = PAD + i * xStep
    const y = H - PAD - ((p.net_biomass / maxBio) * (H - PAD * 2))
    return `${x},${y}`
  }).join(' ')

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-20">
      {[0.25, 0.5, 0.75, 1].map(f => (
        <line key={f} x1={PAD} y1={H - PAD - f * (H - PAD * 2)} x2={W - PAD} y2={H - PAD - f * (H - PAD * 2)} stroke="#1e2030" strokeWidth="1" />
      ))}
      {points.map((p, i) => {
        const bh = (p.tasks_completed / maxBar) * (H - PAD * 2) * 0.4
        return bh > 0 ? <rect key={`c${i}`} x={PAD + i * xStep - 3} y={H - PAD - bh} width={3} height={bh} fill="#22c55e44" rx={1} /> : null
      })}
      {points.map((p, i) => {
        const bh = (p.lessons_added / maxBar) * (H - PAD * 2) * 0.4
        return bh > 0 ? <rect key={`l${i}`} x={PAD + i * xStep + 1} y={H - PAD - bh} width={3} height={bh} fill="#0891b244" rx={1} /> : null
      })}
      <defs>
        <linearGradient id="bioGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#a855f7" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#a855f7" stopOpacity="0" />
        </linearGradient>
      </defs>
      {points.length > 1 && <polygon points={`${PAD},${H - PAD} ${bioLine} ${PAD + (points.length - 1) * xStep},${H - PAD}`} fill="url(#bioGrad)" />}
      {points.length > 1 && <polyline points={bioLine} fill="none" stroke="#a855f7" strokeWidth="1.5" strokeLinejoin="round" />}
      {points.map((p, i) => {
        const x = PAD + i * xStep
        const y = H - PAD - ((p.net_biomass / maxBio) * (H - PAD * 2))
        return p.net_biomass > 0 ? <circle key={i} cx={x} cy={y} r={2} fill="#a855f7" /> : null
      })}
    </svg>
  )
}

function Card({ title, accent, children }: { title: string; accent: string; children: React.ReactNode }) {
  return (
    <div className="bg-ww-surface rounded-lg px-4 py-3" style={{ border: `1px solid ${accent}33` }}>
      <div className="text-[11px] font-semibold mb-2.5 uppercase tracking-wide" style={{ color: accent }}>{title}</div>
      {children}
    </div>
  )
}

function BigNum({ value, label, accent = '#e2e8f0' }: { value: number; label: string; accent?: string }) {
  return (
    <div>
      <div className="text-[28px] font-bold leading-none" style={{ color: accent }}>{value}</div>
      <div className="text-[11px] text-ww-dim mt-0.5">{label}</div>
    </div>
  )
}

function StatBadge({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center gap-1.5 rounded-[5px] px-2.5 py-1" style={{ background: color + '18', border: `1px solid ${color}44` }}>
      <span className="text-[11px]" style={{ color }}>{label}</span>
      <span className="text-[13px] font-bold" style={{ color }}>{value}</span>
    </div>
  )
}

function BarChart({ data, total, colorFn }: { data: Record<string, number>; total: number; colorFn: (key: string) => string }) {
  const sorted = Object.entries(data).sort((a, b) => b[1] - a[1])
  return (
    <div className="flex flex-col gap-1.5">
      {sorted.map(([key, count]) => {
        const pct = total > 0 ? Math.round((count / total) * 100) : 0
        const color = colorFn(key)
        return (
          <div key={key}>
            <div className="flex justify-between mb-0.5 text-[11px]">
              <span className="text-ww-muted">{key}</span>
              <span style={{ color }}>{count} ({pct}%)</span>
            </div>
            <div className="h-1 bg-ww-card rounded-sm">
              <div className="h-full rounded-sm transition-all duration-300" style={{ width: `${pct}%`, background: color }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}
