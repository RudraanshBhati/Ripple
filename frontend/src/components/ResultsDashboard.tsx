import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { CompleteResult } from '../types'
import { RiskGauge } from './RiskGauge'

function severityClass(score: number) {
  if (score >= 0.8) return { label: 'CRITICAL', bg: 'bg-red/10', border: 'border-red/40', text: 'text-red' }
  if (score >= 0.6) return { label: 'HIGH', bg: 'bg-amber/10', border: 'border-amber/40', text: 'text-amber' }
  if (score >= 0.35) return { label: 'MEDIUM', bg: 'bg-amber/5', border: 'border-amber/20', text: 'text-amber' }
  return { label: 'LOW', bg: 'bg-green/5', border: 'border-green/20', text: 'text-green' }
}

const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
}

const stagger = {
  show: { transition: { staggerChildren: 0.08 } },
}

interface Props {
  result: CompleteResult
}

export function ResultsDashboard({ result }: Props) {
  const [traceOpen, setTraceOpen] = useState(false)
  const sev = severityClass(result.severity_score)

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={stagger}
      className="w-full max-w-5xl mx-auto space-y-5 pb-16"
    >
      {/* Severity banner */}
      <motion.div
        variants={cardVariants}
        className={`rounded-xl border px-5 py-4 flex items-center justify-between ${sev.bg} ${sev.border}`}
      >
        <div className="flex items-center gap-3">
          <span className={`font-mono text-xs font-semibold tracking-widest px-2.5 py-1 rounded-full border ${sev.border} ${sev.text}`}>
            {sev.label}
          </span>
          <span className="text-sm text-muted font-mono">
            {result.signal_type?.replace('_', ' ')} · score {result.severity_score.toFixed(2)}
          </span>
        </div>
        {result.tier2_exposure && result.invisible_risk && (
          <motion.div
            animate={{ opacity: [1, 0.5, 1] }}
            transition={{ duration: 1.8, repeat: Infinity }}
            className="flex items-center gap-1.5 text-amber text-xs font-medium border border-amber/30 bg-amber/10 px-3 py-1 rounded-full"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-amber inline-block" />
            Invisible Tier-2 Risk
          </motion.div>
        )}
      </motion.div>

      {/* Final alert */}
      {result.final_alert && (
        <motion.div
          variants={cardVariants}
          className="rounded-xl border border-border bg-card p-5"
        >
          <p className="text-xs font-mono text-muted uppercase tracking-widest mb-3">Alert</p>
          <p className="text-sm text-[#F8FAFC] leading-relaxed whitespace-pre-wrap">{result.final_alert}</p>
        </motion.div>
      )}

      {/* SKU risks */}
      {result.sku_risks.length > 0 && (
        <motion.div variants={cardVariants}>
          <p className="text-xs font-mono text-muted uppercase tracking-widest mb-3">
            At-Risk SKUs ({result.sku_risks.length})
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {result.sku_risks.map((sku, i) => (
              <motion.div
                key={sku.sku_id}
                variants={cardVariants}
                transition={{ delay: i * 0.06 }}
                className="rounded-xl border border-border bg-card p-4 flex gap-4 items-start"
              >
                <RiskGauge score={sku.risk_score} size={80} />
                <div className="flex-1 min-w-0 pt-1">
                  <p className="text-sm font-mono font-medium text-[#F8FAFC] truncate">{sku.sku_id}</p>
                  <div className="mt-2 space-y-1">
                    <Row label="gap" value={`${sku.gap_days.toFixed(1)}d`} warn={sku.gap_days < 0} />
                    <Row label="lead time" value={`${sku.lead_time_days}d`} />
                    <Row label="confidence" value={`${(sku.confidence * 100).toFixed(0)}%`} />
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Affected suppliers */}
      {result.affected_suppliers.length > 0 && (
        <motion.div variants={cardVariants}>
          <p className="text-xs font-mono text-muted uppercase tracking-widest mb-3">
            Affected Suppliers ({result.affected_suppliers.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {result.affected_suppliers.map(s => (
              <div
                key={s.supplier_id}
                className="rounded-lg border border-border bg-elevated px-3 py-2 text-xs"
              >
                <span className="font-mono text-[#F8FAFC]">{s.supplier_id}</span>
                <span className="text-muted ml-2">{s.name} · {s.country}</span>
                <span className={`ml-2 px-1.5 py-0.5 rounded text-[10px] font-medium ${
                  s.exposure_type === 'direct' ? 'bg-red/10 text-red' : 'bg-amber/10 text-amber'
                }`}>
                  {s.exposure_type}
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Alternative suppliers */}
      {result.alternatives.length > 0 && (
        <motion.div variants={cardVariants}>
          <p className="text-xs font-mono text-muted uppercase tracking-widest mb-3">
            Alternative Suppliers ({result.alternatives.length})
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {result.alternatives.map((alt, i) => (
              <motion.div
                key={alt.supplier_id + i}
                variants={cardVariants}
                className="rounded-xl border border-border bg-card p-4"
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="text-sm font-medium text-[#F8FAFC]">{alt.name}</p>
                    <p className="text-xs text-muted mt-0.5">{alt.country}</p>
                  </div>
                  <span className="text-xs font-mono text-muted bg-elevated px-2 py-1 rounded">
                    {alt.supplier_id}
                  </span>
                </div>
                {/* Similarity bar */}
                <div className="mb-3">
                  <div className="flex justify-between text-xs text-muted mb-1">
                    <span>similarity</span>
                    <span className="font-mono">{(alt.similarity_score * 100).toFixed(0)}%</span>
                  </div>
                  <div className="h-1 bg-elevated rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${alt.similarity_score * 100}%` }}
                      transition={{ duration: 0.8, ease: 'easeOut', delay: 0.3 }}
                      className="h-full rounded-full bg-indigo"
                    />
                  </div>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-muted">lead time</span>
                  <span className="font-mono text-[#F8FAFC]">{alt.estimated_lead_time}d</span>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Reasoning trace */}
      <motion.div variants={cardVariants}>
        <button
          onClick={() => setTraceOpen(v => !v)}
          className="flex items-center gap-2 text-xs font-mono text-muted hover:text-[#F8FAFC] transition-colors mb-2"
        >
          <motion.span
            animate={{ rotate: traceOpen ? 90 : 0 }}
            transition={{ duration: 0.2 }}
            className="inline-block"
          >
            ▶
          </motion.span>
          Reasoning trace ({result.reasoning_trace.length} entries)
        </button>
        <AnimatePresence>
          {traceOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25 }}
              className="overflow-hidden"
            >
              <div className="rounded-xl border border-border bg-card p-4 max-h-64 overflow-y-auto">
                {result.reasoning_trace.map((line, i) => (
                  <p key={i} className="text-xs font-mono text-muted leading-relaxed">
                    <span className="text-border mr-2 select-none">{String(i + 1).padStart(2, '0')}</span>
                    {line}
                  </p>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </motion.div>
  )
}

function Row({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-muted">{label}</span>
      <span className={`font-mono ${warn ? 'text-red' : 'text-[#F8FAFC]'}`}>{value}</span>
    </div>
  )
}
