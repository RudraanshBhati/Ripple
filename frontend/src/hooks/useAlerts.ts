import { useState, useEffect, useCallback, useRef } from 'react'
import type { Alert } from '../types'

export function useAlerts(pollInterval = 10000) {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchAlerts = useCallback(async () => {
    try {
      const res = await fetch('/api/alerts?limit=50')
      if (!res.ok) return
      const data = await res.json()
      setAlerts(data.alerts ?? [])
    } catch {
      // network error — keep last state
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAlerts()
    timerRef.current = setInterval(fetchAlerts, pollInterval)
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [fetchAlerts, pollInterval])

  return { alerts, loading, refresh: fetchAlerts }
}
