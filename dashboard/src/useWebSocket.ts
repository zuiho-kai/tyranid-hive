import { useEffect, useRef, useState } from 'react'
import type { BusEvent } from './api'

export function useHiveWebSocket(onEvent?: (e: BusEvent) => void) {
  const [connected, setConnected] = useState(false)
  const [events, setEvents] = useState<BusEvent[]>([])
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    const ws = new WebSocket(`${protocol}://${host}/ws`)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onerror = () => setConnected(false)

    ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data)
        if (data.type === 'ping') return
        const e = data as BusEvent
        setEvents(prev => [e, ...prev].slice(0, 200))
        onEvent?.(e)
      } catch { /* ignore parse errors */ }
    }

    return () => ws.close()
  }, [])

  return { connected, events }
}
