import type { Alert } from '../types'

interface Props {
  alerts: Alert[]
}

function sourceLabel(signal: string): string {
  if (signal.toLowerCase().includes('flood') || signal.toLowerCase().includes('weather')) return 'Weather'
  if (signal.toLowerCase().includes('strike') || signal.toLowerCase().includes('union')) return 'Labor'
  if (signal.toLowerCase().includes('port') || signal.toLowerCase().includes('ship')) return 'Maritime'
  if (signal.toLowerCase().includes('fire') || signal.toLowerCase().includes('factory')) return 'Factory'
  return 'NewsAPI'
}

export function SignalsPanel({ alerts }: Props) {
  const signals = alerts.slice(0, 8).map(a => ({
    t: new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    src: sourceLabel(a.signal),
    title: a.signal.slice(0, 60),
    matched: a.severity_score >= 0.35,
    id: a._id,
  }))

  return (
    <div className="panel">
      <div className="panel-head">
        <div className="dot pulse" style={{ background: 'var(--green)' }}/>
        <div className="panel-title">Signals</div>
        <span className="panel-sub">{alerts.length} ingested</span>
      </div>
      {signals.length === 0 ? (
        <div style={{ padding: '14px', fontSize: 12, color: 'var(--muted)' }}>No signals yet — pipeline idle</div>
      ) : (
        <div>
          {signals.map((s, i) => (
            <div key={s.id} style={{
              padding: '10px 14px',
              borderBottom: i < signals.length - 1 ? '1px solid var(--border)' : 'none',
              display: 'flex', gap: 10, alignItems: 'center',
              opacity: s.matched ? 1 : 0.6,
            }}>
              <span className="mono" style={{ fontSize: 10, color: 'var(--muted)', width: 40 }}>{s.t}</span>
              <span className="badge" style={{ width: 66, justifyContent: 'center', fontSize: 9 }}>{s.src}</span>
              <span style={{ flex: 1, fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.title}</span>
              {s.matched && <span className="dot" style={{ background: '#DC2626' }}/>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
