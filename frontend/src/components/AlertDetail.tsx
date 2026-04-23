import { useState } from 'react'
import type { Alert } from '../types'
import { Icons, SeverityBar, TierPill, severityLabel, alertId } from './shared'

interface Props {
  alert: Alert | null
  onStartChat: (sessionId: string) => void
}

export function AlertDetail({ alert, onStartChat }: Props) {
  const [showReasoning, setShowReasoning] = useState(false)

  if (!alert) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--muted)', flexDirection: 'column', gap: 12 }}>
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" opacity={0.3}><circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/></svg>
        <span style={{ fontSize: 13 }}>Select an alert to view details</span>
      </div>
    )
  }

  const { label, cls } = severityLabel(alert.severity_score)
  const sevColor = alert.severity_score >= 0.7 ? '#DC2626' : alert.severity_score >= 0.4 ? '#D97706' : '#16A34A'

  return (
    <div style={{ padding: '0 4px' }}>
      {/* Header */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start', padding: '20px 20px 16px' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
            <span className="mono" style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 500 }}>{alertId(alert)}</span>
            {(alert.affected_entities ?? []).map((e: string, i: number) => (
              <span key={i} className="badge">{e}</span>
            ))}
            <span className={`badge ${cls}`}>{label}</span>
          </div>
          <h1 className="section-title">{alert.signal_type?.replace(/_/g, ' ') ?? 'Supply Chain Alert'}</h1>
          <p style={{ fontSize: 13, color: 'var(--fg-2)', marginTop: 8, lineHeight: 1.5 }}>{alert.signal}</p>
        </div>
        <div style={{ textAlign: 'right', paddingLeft: 20, borderLeft: '1px solid var(--border)', minWidth: 140, flexShrink: 0 }}>
          <div className="mono" style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Severity</div>
          <div style={{ fontSize: 32, fontWeight: 700, lineHeight: 1.1, color: sevColor, letterSpacing: '-0.03em', marginTop: 2 }}>
            {alert.severity_score.toFixed(2)}
          </div>
          <div style={{ marginTop: 8 }}><SeverityBar value={alert.severity_score}/></div>
        </div>
      </div>

      {/* Tier-2 callout */}
      {(alert.invisible_risk || alert.tier2_exposure) && (
        <div style={{ margin: '0 20px 16px', padding: '10px 14px', background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 10, display: 'flex', gap: 10, alignItems: 'center' }}>
          <div style={{ color: '#DC2626', flexShrink: 0 }}>{Icons.warning}</div>
          <div style={{ fontSize: 12.5, color: '#450A0A' }}>
            <b>Tier-2 exposure detected</b> — hidden dependency in supply chain, {alert.affected_suppliers.length} supplier(s) at risk
          </div>
        </div>
      )}

      {/* Suppliers + SKUs grid */}
      <div style={{ padding: '0 20px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
        <div className="panel">
          <div className="panel-head">
            <div className="panel-title">Affected suppliers</div>
            <span className="panel-sub" style={{ marginLeft: 'auto' }}>{alert.affected_suppliers.length} exposed</span>
          </div>
          {alert.affected_suppliers.length === 0 ? (
            <div style={{ padding: 14, fontSize: 12, color: 'var(--muted)' }}>No suppliers flagged</div>
          ) : (
            <div>
              <div className="sup-row sup-head" style={{ gridTemplateColumns: '36px 1fr 40px 60px 80px' }}>
                <span>T</span><span>NAME</span><span>CC</span><span>STATUS</span><span>SCORE</span>
              </div>
              {alert.affected_suppliers.slice(0, 4).map(s => (
                <div key={s.supplier_id} className="sup-row" style={{ gridTemplateColumns: '36px 1fr 40px 60px 80px' }}>
                  <TierPill tier={s.tier}/>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 12 }}>{s.name || s.supplier_id}</div>
                    <div className="mono" style={{ fontSize: 10, color: 'var(--muted)' }}>{s.supplier_id}</div>
                  </div>
                  <span className="mono" style={{ fontSize: 11 }}>{(s.country || '??').slice(0, 2).toUpperCase()}</span>
                  <span className={`badge ${s.exposure_type === 'direct' ? 'badge-red' : 'badge-amber'}`} style={{ height: 18, fontSize: 9 }}>
                    {s.exposure_type || 'direct'}
                  </span>
                  <SeverityBar value={0.8}/>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="panel">
          <div className="panel-head">
            <div className="panel-title">SKUs at risk</div>
            <span className="panel-sub" style={{ marginLeft: 'auto' }}>{alert.sku_risks.length} impacted</span>
          </div>
          {alert.sku_risks.length === 0 ? (
            <div style={{ padding: 14, fontSize: 12, color: 'var(--muted)' }}>No SKU impact detected</div>
          ) : (
            <div>
              <div className="sup-row sup-head" style={{ gridTemplateColumns: '86px 1fr 52px 76px' }}>
                <span>SKU</span><span>ID</span><span>GAP</span><span>RISK</span>
              </div>
              {alert.sku_risks.slice(0, 4).map(s => (
                <div key={s.sku_id} className="sup-row" style={{ gridTemplateColumns: '86px 1fr 52px 76px' }}>
                  <span className="mono" style={{ fontSize: 10.5, fontWeight: 500 }}>{s.sku_id}</span>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 12 }}>{s.sku_id}</div>
                    <div className="mono" style={{ fontSize: 10, color: 'var(--muted)' }}>stock {(s.current_stock ?? 0).toLocaleString()}</div>
                  </div>
                  <span className="mono" style={{ fontSize: 11.5, fontWeight: 600, color: (s.gap_days ?? 0) < 0 ? '#DC2626' : '#16A34A' }}>
                    {(s.gap_days ?? 0) > 0 ? '+' : ''}{s.gap_days ?? 0}d
                  </span>
                  <SeverityBar value={s.risk_score ?? 0}/>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Reasoning trace */}
      <div style={{ padding: '0 20px', marginBottom: 16 }}>
        <div className="panel">
          <div className="panel-head" style={{ cursor: 'pointer' }} onClick={() => setShowReasoning(v => !v)}>
            <span style={{ color: 'var(--indigo)' }}>{Icons.sparkles}</span>
            <div className="panel-title">How Ripple decided this</div>
            <span className="panel-sub">{alert.final_alert ? 'analysis complete' : 'pending'}</span>
            <div style={{ marginLeft: 'auto', transform: showReasoning ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s', color: 'var(--muted)' }}>
              {Icons.chevron}
            </div>
          </div>
          {showReasoning && (
            <div style={{ padding: '12px 16px' }}>
              {alert.final_alert
                ? <div style={{ fontSize: 12.5, color: 'var(--fg-2)', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{alert.final_alert}</div>
                : <div style={{ color: 'var(--muted)', fontSize: 12 }}>No reasoning trace available.</div>
              }
            </div>
          )}
        </div>
      </div>

      {/* Alternatives */}
      {(alert.alternatives?.length ?? 0) > 0 && (
        <div style={{ padding: '0 20px', marginBottom: 16 }}>
          <div className="panel">
            <div className="panel-head">
              <div className="panel-title">Alternative sources</div>
              <span className="panel-sub">hybrid rank (RAG + graph)</span>
            </div>
            <div>
              <div className="sup-row sup-head" style={{ gridTemplateColumns: '86px 1fr 46px 50px 76px' }}>
                <span>ID</span><span>SUPPLIER</span><span>LEAD</span><span>CONF</span><span>SCORE</span>
              </div>
              {alert.alternatives.slice(0, 5).map(a => (
                <div key={a.supplier_id} className="sup-row" style={{ gridTemplateColumns: '86px 1fr 46px 50px 76px' }}>
                  <span className="mono" style={{ fontSize: 10, fontWeight: 500 }}>{a.supplier_id}</span>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 12 }}>{a.name || a.supplier_id}</div>
                    <div className="mono" style={{ fontSize: 10, color: 'var(--muted)' }}>{a.country}</div>
                  </div>
                  <span className="mono" style={{ fontSize: 11 }}>{a.estimated_lead_time}d</span>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--muted-2)' }}>{((a.confidence ?? 0) * 100).toFixed(0)}%</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <div className="sev-bar" style={{ flex: 1 }}>
                      <div className="sev-bar-fill" style={{ width: `${(a.similarity_score ?? 0) * 100}%`, background: 'linear-gradient(90deg, #16A34A, #22C55E)' }}/>
                    </div>
                    <span className="mono" style={{ fontSize: 10, color: '#16A34A', fontWeight: 600 }}>{(a.similarity_score ?? 0).toFixed(2)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div style={{ padding: '16px 20px 24px', display: 'flex', gap: 8, flexWrap: 'wrap', borderTop: '1px solid var(--border)' }}>
        <button className="btn btn-primary" onClick={() => onStartChat(alert.session_id)}>
          {Icons.sparkles} Ask Ripple
        </button>
        <button className="btn">{Icons.download} Report</button>
        <button className="btn">Notify team</button>
        <button className="btn" style={{ marginLeft: 'auto', color: 'var(--muted)' }}>Dismiss</button>
      </div>
    </div>
  )
}
