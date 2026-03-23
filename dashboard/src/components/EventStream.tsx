import type { BusEvent } from '../api'

interface Props {
  events: BusEvent[]
}

export default function EventStream({ events }: Props) {
  return (
    <div className="w-[260px] border-l border-ww-subtle flex flex-col overflow-hidden shrink-0">
      <div className="px-3.5 pt-2.5 pb-1.5 text-[11px] text-ww-dim border-b border-ww-subtle tracking-wider uppercase">
        事件流 ({events.length})
      </div>
      <div className="flex-1 overflow-y-auto">
        {events.length === 0 ? (
          <div className="p-4 text-ww-dim text-xs text-center">暂无事件</div>
        ) : events.map(e => (
          <div key={e.event_id} className="px-3 py-[7px] border-b border-ww-surface">
            <div className="flex justify-between mb-0.5">
              <span className="text-[11px] text-opus-primary font-semibold">{e.topic}</span>
              <span className="text-[10px] text-ww-dim">{fmtTime(e.created_at)}</span>
            </div>
            <div className="text-[11px] text-ww-dim">{e.event_type}</div>
            <div className="text-[10px] text-ww-dim">← {e.producer}</div>
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
