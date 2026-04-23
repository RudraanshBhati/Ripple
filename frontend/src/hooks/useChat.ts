import { useState, useCallback, useEffect } from 'react'
import type { ChatMessage } from '../types'

export function useChat(sessionId: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [sending, setSending] = useState(false)

  useEffect(() => {
    if (!sessionId) { setMessages([]); return }
    fetch(`/api/sessions/${sessionId}/messages?limit=50`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setMessages(data.messages ?? []) })
      .catch(() => {})
  }, [sessionId])

  const sendMessage = useCallback(async (text: string) => {
    if (!sessionId || !text.trim() || sending) return

    const userMsg: ChatMessage = {
      session_id: sessionId,
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMsg])
    setSending(true)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: text }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const assistantMsg: ChatMessage = {
        session_id: sessionId,
        role: 'assistant',
        content: data.response || '(no response)',
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      const errMsg: ChatMessage = {
        session_id: sessionId,
        role: 'assistant',
        content: `Error: ${err instanceof Error ? err.message : 'Unknown error'}`,
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, errMsg])
    } finally {
      setSending(false)
    }
  }, [sessionId, sending])

  const appendMessages = useCallback((msgs: ChatMessage[]) => {
    setMessages(msgs)
  }, [])

  const clearMessages = useCallback(async () => {
    if (!sessionId) { setMessages([]); return }
    try {
      await fetch(`/api/sessions/${sessionId}/messages`, { method: 'DELETE' })
    } catch {
      // non-fatal: local clear still proceeds
    }
    setMessages([])
  }, [sessionId])

  return { messages, sending, sendMessage, appendMessages, clearMessages }
}
