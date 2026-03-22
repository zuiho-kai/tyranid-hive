import type { BusEvent } from '../api'

interface Props {
  events: BusEvent[]
}

export default function EventStream({ events }: Props) {
  return (
    <div style={{ width: 260, borderLeft: '1px solid #1e2030', display: 'flex', flexDirection: 'column', overflow: 'hidden', flexShrink: 0 }}>
      <div style={{ padding: '10px 14px 6px', fontSize: 11, color: '#475569', borderBottom: '1px solid #1e2030', letterSpacing: 1, textTransform: 'uppercase' }}>
        事件流 ({events.length})
      </div>
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {events.length === 0 ? (
          <div style={{ padding: 16, color: '#374151', fontSize: 12, textAlign: 'center' }}>暂无事件</div>
        ) : events.map(e => (
          <div key={e.event_id} style={{ padding: '7px 12px', borderBottom: '1px solid #13131a' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
              <span style={{ fontSize: 11, color: '#a78bfa', fontWeight: 600 }}>{e.topic}</span>
              <span style={{ fontSize: 10, color: '#374151' }}>{fmtTime(e.created_at)}</span>
            </div>
            <div style={{ fontSize: 11, color: '#64748b' }}>{e.event_type}</div>
            <div style={{ fontSize: 10, color: '#374151' }}>← {e.producer}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch { return iso }
}
