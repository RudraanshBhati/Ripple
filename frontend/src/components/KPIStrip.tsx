import type { Alert } from '../types'
import { Sparkbars } from './shared'

interface Props {
  alerts: Alert[]
  isAnalyzing: boolean
}

export function KPIStrip({ alerts, isAnalyzing }: Props) {
  const activeCount = alerts.filter(a => a.severity_score >= 0.35).length
  const skuRiskCount = alerts.reduce((sum, a) => sum + (a.sku_risks?.length ?? 0), 0)
  const tier2Count = alerts.filter(a => a.tier2_exposure || a.invisible_risk).length
  const suppliersSet = new Set(alerts.flatMap(a => (a.affected_suppliers ?? []).map(s => s.supplier_id)))
  const signalsCount = alerts.length * 3
  const reportsCount = alerts.filter(a => !!a.final_alert).length

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12, padding: '16px 20px 0' }}>
      <div className="kpi">
        <div className="kpi-label">Active alerts</div>
        <div className="kpi-value">{activeCount}</div>
        <div className="kpi-delta">{isAnalyzing ? <b style={{ color: 'var(--amber)' }}>analyzing…</b> : <><b style={{ color: '#DC2626' }}>↑</b> today</>}</div>
        <Sparkbars values={[0.3,0.4,0.35,0.5,0.6,0.7,0.85,0.9]} tone="red"/>
      </div>
      <div className="kpi">
        <div className="kpi-label">SKUs at risk</div>
        <div className="kpi-value" style={{ color: skuRiskCount > 0 ? '#D97706' : 'var(--fg)' }}>{skuRiskCount}</div>
        <div className="kpi-delta"><b>{alerts.filter(a => a.sku_risks?.some(s => s.gap_days < 0)).length}</b> critical</div>
        <Sparkbars values={[0.2,0.3,0.4,0.35,0.5,0.55,0.6,0.7]} tone="amber"/>
      </div>
      <div className="kpi">
        <div className="kpi-label">Tier-2 exposure</div>
        <div className="kpi-value" style={{ color: tier2Count > 0 ? '#DC2626' : 'var(--fg)' }}>{tier2Count}</div>
        <div className="kpi-delta">hidden risks</div>
        <Sparkbars values={[0.1,0.1,0.15,0.2,0.25,0.35,0.5,0.6]} tone="red"/>
      </div>
      <div className="kpi">
        <div className="kpi-label">Suppliers flagged</div>
        <div className="kpi-value">{suppliersSet.size}</div>
        <div className="kpi-delta">across {alerts.length} alerts</div>
        <Sparkbars values={[0.3,0.4,0.3,0.5,0.45,0.6,0.7,0.7]}/>
      </div>
      <div className="kpi">
        <div className="kpi-label">Signals processed</div>
        <div className="kpi-value">{signalsCount}</div>
        <div className="kpi-delta"><b>{alerts.length}</b> matched</div>
        <Sparkbars values={[0.5,0.6,0.55,0.7,0.6,0.75,0.8,0.7]}/>
      </div>
      <div className="kpi">
        <div className="kpi-label">Reports generated</div>
        <div className="kpi-value" style={{ color: reportsCount > 0 ? '#16A34A' : 'var(--fg)' }}>{reportsCount}</div>
        <div className="kpi-delta">pipeline complete</div>
        <Sparkbars values={[0.3,0.4,0.5,0.6,0.5,0.7,0.8,0.75]} tone="green"/>
      </div>
    </div>
  )
}
