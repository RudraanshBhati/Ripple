import { useState } from 'react'
import type { Alert } from '../types'
import { Icons, severityLabel, severityDotColor, fmtTime, alertId } from './shared'

interface Props {
  alerts: Alert[]
  loading: boolean
  selectedId: string | null
  onSelect: (id: string) => void
}

type Filter = 'all' | 'critical' | 'unread' | 'tier2'

export function AlertsFeed({ alerts, loading, selectedId, onSelect }: Props) {
  const [filter, setFilter] = useState<Filter>('all')

  const filtered = alerts.filter(a => {
    if (filter === 'critical') return a.severity_score >= 0.7
    if (filter === 'tier2') return a.tier2_exposure || a.invisible_risk
    return true
  })

  const liveCount = alerts.filter(a => a.severity_score >= 0.35).length

  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <div className="panel-head">
        <div className="dot pulse" style={{ background: '#DC2626' }}/>
        <div className="panel-title">Active alerts</div>
        <span className="badge badge-red">{liveCount} live</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          <button className="icon-btn" style={{ width: 28, height: 28 }}>{Icons.filter}</button>
        </div>
      </div>

      <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        {(['all', 'critical', 'tier2'] as Filter[]).map(f => (
          <button key={f} className="btn btn-xs"
            style={filter === f ? { background: 'var(--fg)', color: 'white', borderColor: 'var(--fg)' } : {}}
            onClick={() => setFilter(f)}>
            {f}
          </button>
        ))}
      </div>

      <div style={{ overflowY: 'auto', flex: 1 }}>
        {loading && (
          <div style={{ padding: '24px 14px', textAlign: 'center', color: 'var(--muted)', fontSize: 12 }}>
            Loading alerts…
          </div>
        )}
        {!loading && filtered.length === 0 && (
          <div style={{ padding: '24px 14px', textAlign: 'center', color: 'var(--muted)', fontSize: 12 }}>
            No alerts yet — run an analysis to get started.
          </div>
        )}
        {filtered.map(a => {
          const { label, cls } = severityLabel(a.severity_score)
          const isActive = a._id === selectedId
          return (
            <div key={a._id}
              className={`alert-row ${isActive ? 'active' : ''}`}
              onClick={() => onSelect(a._id)}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span className="dot" style={{ background: severityDotColor(a.severity_score) }}/>
                <span className="mono" style={{ fontSize: 10, color: 'var(--muted)', fontWeight: 500 }}>{alertId(a)}</span>
                <span className="mono" style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--muted-2)' }}>
                  {fmtTime(a.created_at)}
                </span>
              </div>
              <div className="alert-title" style={{ marginBottom: 4 }}>
                {a.signal_type?.replace(/_/g, ' ') || 'Supply chain alert'}
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--muted)', marginBottom: 8, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {a.signal.slice(0, 80)}
              </div>
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                <span className={`badge ${cls}`}>{label}</span>
                {a.affected_entities?.length > 0 && (
                  <span className="badge">{a.affected_entities[0]}</span>
                )}
                {a.sku_risks?.length > 0 && (
                  <span className="badge">{a.sku_risks.length} SKU{a.sku_risks.length !== 1 ? 's' : ''}</span>
                )}
                {(a.invisible_risk || a.tier2_exposure) && (
                  <span className="badge badge-red">tier-2</span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
