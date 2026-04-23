import type { Alert, SKURisk } from '../types'
import { SeverityBar } from './shared'

interface Props {
  alerts: Alert[]
}

export function SKUWatchlist({ alerts }: Props) {
  const skuMap = new Map<string, SKURisk & { alert_id: string }>()
  for (const alert of alerts) {
    for (const sku of (alert.sku_risks ?? [])) {
      const existing = skuMap.get(sku.sku_id)
      if (!existing || sku.risk_score > existing.risk_score) {
        skuMap.set(sku.sku_id, { ...sku, alert_id: alert._id })
      }
    }
  }
  const skus = Array.from(skuMap.values()).sort((a, b) => b.risk_score - a.risk_score).slice(0, 8)

  return (
    <div className="panel">
      <div className="panel-head">
        <div className="panel-title">SKU watchlist</div>
        <button className="btn btn-xs" style={{ marginLeft: 'auto' }}>view all</button>
      </div>
      {skus.length === 0 ? (
        <div style={{ padding: '14px', fontSize: 12, color: 'var(--muted)' }}>No at-risk SKUs detected</div>
      ) : (
        <div>
          <div className="sup-row sup-head" style={{ gridTemplateColumns: '100px 1fr 72px 72px 1fr 52px' }}>
            <span>ID</span><span>NAME</span><span>STOCK</span><span>RUNOUT</span><span>RISK</span><span>GAP</span>
          </div>
          {skus.map(s => (
            <div key={s.sku_id} className="sup-row" style={{ gridTemplateColumns: '100px 1fr 72px 72px 1fr 52px' }}>
              <span className="mono" style={{ fontSize: 10.5, fontWeight: 500 }}>{s.sku_id}</span>
              <span style={{ fontWeight: 500, fontSize: 12 }}>{s.sku_id}</span>
              <span className="mono" style={{ fontSize: 11 }}>{(s.current_stock ?? 0).toLocaleString()}</span>
              <span className="mono" style={{ fontSize: 11, color: (s.gap_days ?? 0) < 0 ? '#DC2626' : 'var(--fg-2)' }}>
                {s.runout_date ? new Date(s.runout_date).toLocaleDateString('en', { month: 'short', day: 'numeric' }) : 'N/A'}
              </span>
              <SeverityBar value={s.risk_score ?? 0}/>
              <span className="mono" style={{ fontSize: 11, fontWeight: 600, color: (s.gap_days ?? 0) < 0 ? '#DC2626' : '#16A34A', textAlign: 'right' }}>
                {(s.gap_days ?? 0) > 0 ? '+' : ''}{s.gap_days ?? 0}d
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
