import { useState, useCallback, useRef } from 'react'
import type { AgentUpdate, CompleteResult, AppState } from '../types'

export function useRipple() {
  const [appState, setAppState] = useState<AppState>('idle')
  const [agentUpdates, setAgentUpdates] = useState<AgentUpdate[]>([])
  const [result, setResult] = useState<CompleteResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const analyze = useCallback(async (signal: string, userId = 'default') => {
    if (abortRef.current) abortRef.current.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl

    setAppState('running')
    setAgentUpdates([])
    setResult(null)
    setError(null)

    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ signal, user_id: userId }),
        signal: ctrl.signal,
      })

      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))

            if (event.type === 'start') {
              setSessionId(event.session_id)
            } else if (event.type === 'agent_update') {
              setAgentUpdates(prev => [
                ...prev,
                { agent: event.agent, data: event.data, trace: event.trace ?? [], completedAt: Date.now() },
              ])
            } else if (event.type === 'complete') {
              setResult(event as CompleteResult)
              setSessionId(event.session_id)
              setAppState('done')
            } else if (event.type === 'error') {
              setError(event.message)
              setAppState('error')
            }
          } catch {
            // malformed JSON — skip
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return
      setError(err instanceof Error ? err.message : 'Unknown error')
      setAppState('error')
    }
  }, [])

  const reset = useCallback(() => {
    if (abortRef.current) abortRef.current.abort()
    setAppState('idle')
    setAgentUpdates([])
    setResult(null)
    setError(null)
    setSessionId(null)
  }, [])

  return { appState, agentUpdates, result, error, sessionId, analyze, reset }
}
