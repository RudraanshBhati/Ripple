import { useState, useEffect, useCallback } from "react"
import type { PortWeather } from "../types"

interface PortWeatherState {
  ports: PortWeather[]
  loading: boolean
  fetchedAt: string | null
}

export function usePortWeather(pollInterval = 600000) {
  const [state, setState] = useState<PortWeatherState>({
    ports: [], loading: false, fetchedAt: null,
  })

  const fetch_ = useCallback(async () => {
    setState(s => ({ ...s, loading: true }))
    try {
      const r = await fetch("/api/port-weather")
      const json = await r.json()
      setState({ ports: json.ports ?? [], loading: false, fetchedAt: json.fetched_at ?? null })
    } catch {
      setState(s => ({ ...s, loading: false }))
    }
  }, [])

  useEffect(() => {
    fetch_()
    const id = setInterval(fetch_, pollInterval)
    return () => clearInterval(id)
  }, [fetch_, pollInterval])

  return { ...state, refresh: fetch_ }
}
