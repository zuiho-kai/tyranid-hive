import { useEffect, useState } from 'react'
import type { Synapse, SynapseScore } from '../api'
import { fetchFitnessLeaderboard } from '../api'

const TIER_COLOR: Record<number, string> = {
  1: '#ef4444', 2: '#f97316', 3: '#f59e0b', 4: '#22c55e', 5: '#06b6d4',
}

interface Props {
  synapses: Synapse[]
}

export default function SynapsePanel({ synapses }: Props) {
  const [scores, setScores] = useState<Record<string, SynapseScore>>({})

  useEffect(() => {
    fetchFitnessLeaderboard(50)
      .then(lb => {
        const map: Record<string, SynapseScore> = {}
        lb.scores.forEach(s => { map[s.synapse_id] = s })
        setScores(map)
      })
      .catch(() => {/* 静默失败 */})
  }, [])

  if (synapses.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-ww-dim text-sm">
        暂无小主脑
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-5">
      <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3">
        {synapses.map(s => {
          const sc = scores[s.id]
          return (
            <div key={s.id} className="bg-ww-surface rounded-[10px] px-4 py-3.5 border border-ww-subtle">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-2xl">{s.emoji}</span>
                <div>
                  <div className="text-sm font-bold text-ww-main">{s.name}</div>
                  <div className="text-[11px]" style={{ color: TIER_COLOR[s.tier] ?? '#64748b' }}>Tier {s.tier}</div>
                </div>
              </div>
              <div className="text-xs text-ww-dim leading-normal">{s.role}</div>

              {sc ? (
                <div className="mt-2.5 px-2.5 py-2 bg-ww-base rounded-md border border-ww-subtle">
                  <div className="flex justify-between mb-1">
                    <span className="text-[11px] text-ww-muted">适存度</span>
                    <span className="text-[13px] font-bold text-opus-primary">{sc.fitness.toFixed(2)}</span>
                  </div>
                  <div className="flex gap-2 text-[10px] text-ww-dim">
                    <span>战功 {sc.mark_count}</span>
                    <span>✅{sc.success_count}</span>
                    <span>❌{sc.fail_count}</span>
                    <span>{(sc.success_rate * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ) : (
                <div className="mt-2.5 text-[11px] text-ww-dim">暂无战功</div>
              )}

              <div className="mt-1.5 text-[10px] text-ww-dim">{s.id}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
