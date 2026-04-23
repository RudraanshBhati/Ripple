import { useState, useRef, useEffect } from 'react'
import type { ChatMessage } from '../types'
import { Icons } from './shared'

interface Props {
  messages: ChatMessage[]
  sending: boolean
  sessionId: string | null
  onSend: (text: string) => void
  onNew: () => void
  onClear: () => void | Promise<void>
}

const SUGGESTED = [
  'What SKUs are most at risk?',
  'Show alternative suppliers',
  'What is the tier-2 exposure?',
]

export function ChatPanel({ messages, sending, sessionId, onSend, onNew, onClear }: Props) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = () => {
    if (!input.trim() || sending) return
    onSend(input.trim())
    setInput('')
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <div className="panel-head">
        <span style={{ color: 'var(--indigo)' }}>{Icons.sparkles}</span>
        <div className="panel-title">Ask Ripple</div>
        <span className="panel-sub">agent 4</span>
        <button
          className="btn btn-xs"
          style={{ marginLeft: 'auto' }}
          onClick={onClear}
          disabled={!sessionId || messages.length === 0 || sending}
          title="Clear visible chat (semantic memory preserved)"
        >
          ↻ clear
        </button>
        <button className="btn btn-xs" onClick={onNew}>
          {Icons.plus} new
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '14px 14px 4px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {!sessionId && messages.length === 0 && (
          <div style={{ color: 'var(--muted)', fontSize: 12, textAlign: 'center', paddingTop: 24, lineHeight: 1.6 }}>
            Select an alert and click <b>Ask Ripple</b>,<br/>or run a new analysis to start a session.
          </div>
        )}

        {sessionId && messages.length === 0 && !sending && (
          <div className="bubble-agent">
            <div className="meta">
              <span className="dot" style={{ background: 'var(--green)' }}/>
              Ripple
            </div>
            Session loaded. Ask me anything about this alert — SKU status, supplier risks, or alternatives.
          </div>
        )}

        {messages.map((m, i) => (
          m.role === 'user' ? (
            <div key={i} className="bubble-user">{m.content}</div>
          ) : (
            <div key={i} className="bubble-agent">
              <div className="meta">
                <span className="dot" style={{ background: 'var(--green)' }}/>
                Ripple
                {m.timestamp && (
                  <span style={{ marginLeft: 4 }}>
                    · {new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                )}
              </div>
              <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.55 }}>{m.content}</div>
            </div>
          )
        ))}

        {sending && (
          <div className="bubble-agent">
            <div className="meta">
              <span className="dot pulse" style={{ background: 'var(--amber)' }}/>
              Ripple · thinking…
            </div>
            <div style={{ display: 'flex', gap: 4, alignItems: 'center', padding: '2px 0' }}>
              {[0, 1, 2].map(i => (
                <div key={i} style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: 'var(--muted-2)',
                  animation: `pulse ${0.6 + i * 0.2}s infinite ease-in-out`,
                }}/>
              ))}
            </div>
          </div>
        )}

        {sessionId && messages.length > 0 && !sending && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
            {SUGGESTED.map(q => (
              <button key={q} className="btn btn-xs" style={{ justifyContent: 'flex-start', textAlign: 'left' }} onClick={() => onSend(q)}>
                {q}
              </button>
            ))}
          </div>
        )}

        <div ref={bottomRef}/>
      </div>

      <div style={{ padding: 10, borderTop: '1px solid var(--border)', background: 'var(--surface-2)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, padding: '6px 8px 6px 12px' }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder={sessionId ? 'Ask about an SKU, supplier, region…' : 'Select an alert first…'}
            disabled={!sessionId || sending}
            style={{ flex: 1, border: 'none', background: 'transparent', outline: 'none', fontSize: 12.5, fontFamily: 'inherit', color: 'var(--fg)' }}
          />
          <button className="btn btn-primary btn-sm" onClick={handleSend} disabled={!sessionId || sending || !input.trim()}>
            {Icons.send}
          </button>
        </div>
        <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="badge badge-ghost" style={{ cursor: 'pointer' }} onClick={() => setInput('@SKU ')}>@SKU</span>
          <span className="badge badge-ghost" style={{ cursor: 'pointer' }} onClick={() => setInput('@supplier ')}>@supplier</span>
          <span className="badge badge-ghost" style={{ cursor: 'pointer' }} onClick={() => setInput('@region ')}>@region</span>
        </div>
      </div>
    </div>
  )
}
