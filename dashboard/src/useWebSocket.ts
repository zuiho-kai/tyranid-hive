import { useEffect, useRef, useState, useCallback } from 'react'
import type { BusEvent } from './api'

const MAX_RETRIES = 8
const BASE_DELAY_MS = 1000   // 初始重连延迟 1s
const MAX_DELAY_MS = 30_000  // 最大延迟 30s

export function useHiveWebSocket(onEvent?: (e: BusEvent) => void) {
  const [connected, setConnected] = useState(false)
  const [events, setEvents] = useState<BusEvent[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef(0)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  const connect = useCallback(() => {
    if (!mountedRef.current) return

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    const ws = new WebSocket(`${protocol}://${host}/ws`)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) { ws.close(); return }
      setConnected(true)
      retryRef.current = 0   // 重置重连计数
    }

    ws.onclose = () => {
      if (!mountedRef.current) return
      setConnected(false)
      scheduleReconnect()
    }

    ws.onerror = () => {
      if (!mountedRef.current) return
      setConnected(false)
    }

    ws.onmessage = (msg) => {
      if (!mountedRef.current) return
      try {
        const data = JSON.parse(msg.data)
        if (data.type === 'ping') return
        const e = data as BusEvent
        setEvents(prev => [e, ...prev].slice(0, 200))
        onEventRef.current?.(e)
      } catch { /* ignore parse errors */ }
    }
  }, [])

  const scheduleReconnect = useCallback(() => {
    if (retryRef.current >= MAX_RETRIES) return
    const delay = Math.min(BASE_DELAY_MS * 2 ** retryRef.current, MAX_DELAY_MS)
    retryRef.current += 1
    timerRef.current = setTimeout(() => {
      if (mountedRef.current) connect()
    }, delay)
  }, [connect])

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      if (timerRef.current) clearTimeout(timerRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { connected, events }
}
