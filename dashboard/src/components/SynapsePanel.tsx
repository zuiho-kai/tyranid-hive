import type { Synapse } from '../api'

const TIER_COLOR: Record<number, string> = {
  1: '#ef4444',
  2: '#f97316',
  3: '#f59e0b',
  4: '#22c55e',
  5: '#06b6d4',
}

interface Props {
  synapses: Synapse[]
}

export default function SynapsePanel({ synapses }: Props) {
  if (synapses.length === 0) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#374151', fontSize: 14 }}>
        暂无小主脑
      </div>
    )
  }

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
        {synapses.map(s => (
          <div key={s.id} style={{ background: '#13131a', borderRadius: 10, padding: '14px 16px', border: '1px solid #1e2030' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span style={{ fontSize: 24 }}>{s.emoji}</span>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#e2e8f0' }}>{s.name}</div>
                <div style={{ fontSize: 11, color: TIER_COLOR[s.tier] ?? '#64748b' }}>Tier {s.tier}</div>
              </div>
            </div>
            <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.5 }}>{s.role}</div>
            <div style={{ marginTop: 8, fontSize: 10, color: '#374151' }}>{s.id}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
