import { useState, useEffect, useCallback } from "react"
import type { NewsArticle } from "../types"

interface NewsState {
  weather: NewsArticle[]
  geopolitical: NewsArticle[]
  other: NewsArticle[]
  loading: boolean
  lastFetched: Date | null
}

export function useNews(pollInterval = 60000) {
  const [state, setState] = useState<NewsState>({
    weather: [], geopolitical: [], other: [], loading: false, lastFetched: null,
  })
  const [scanning, setScanning] = useState(false)

  const fetchAll = useCallback(async () => {
    setState(s => ({ ...s, loading: true }))
    try {
      const [w, g, o] = await Promise.all([
        fetch("/api/news?category=weather&limit=50").then(r => r.json()),
        fetch("/api/news?category=geopolitical&limit=50").then(r => r.json()),
        fetch("/api/news?category=other&limit=50").then(r => r.json()),
      ])
      setState({
        weather: w.articles ?? [],
        geopolitical: g.articles ?? [],
        other: o.articles ?? [],
        loading: false,
        lastFetched: new Date(),
      })
    } catch {
      setState(s => ({ ...s, loading: false }))
    }
  }, [])

  // Trigger a backend scrape then reload articles once done
  const triggerScan = useCallback(async () => {
    setScanning(true)
    try {
      await fetch("/api/trigger-scrape", { method: "POST" })
      // Wait a few seconds for the scrape to run, then reload
      await new Promise(r => setTimeout(r, 5000))
      await fetchAll()
    } finally {
      setScanning(false)
    }
  }, [fetchAll])

  // Clear DB + rescan (for removing stale/irrelevant articles)
  const clearAndRescan = useCallback(async () => {
    setScanning(true)
    try {
      await fetch("/api/clear-cache", { method: "POST" })
      await new Promise(r => setTimeout(r, 6000))
      await fetchAll()
    } finally {
      setScanning(false)
    }
  }, [fetchAll])

  useEffect(() => {
    fetchAll()
    const id = setInterval(fetchAll, pollInterval)
    return () => clearInterval(id)
  }, [fetchAll, pollInterval])

  return { ...state, refresh: fetchAll, triggerScan, clearAndRescan, scanning }
}
