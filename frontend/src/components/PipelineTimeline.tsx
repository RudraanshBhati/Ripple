import { motion } from 'framer-motion'
import type { AgentUpdate } from '../types'

const PIPELINE_STEPS = [
  { id: 'agent_2', label: 'Signal Scraper', icon: '📡' },
  { id: 'agent_3', label: 'Supplier Mapping', icon: '🗺' },
  { id: 'agent_4', label: 'Risk Scorer', icon: '⚡' },
  { id: 'agent_5', label: 'Alt Sourcing', icon: '🔍' },
  { id: 'agent_1_synthesis', label: 'Alert Synthesis', icon: '✦' },
]
const NO_ALERT_STEP = { id: 'no_alert', label: 'No Alert', icon: '✓' }

function stepSummary(agent: string, data: Record<string, unknown>): string {
  if (agent === 'agent_2') {
    const sev = data.severity_score as number
    const type = data.signal_type as string
    return `${type ?? '—'} · severity ${sev?.toFixed(2) ?? '—'}`
  }
  if (agent === 'agent_3') {
    const n = (data.affected_suppliers as unknown[])?.length ?? 0
    const t2 = data.tier2_exposure ? ' · tier-2 risk' : ''
    return `${n} supplier${n !== 1 ? 's' : ''} affected${t2}`
  }
  if (agent === 'agent_4') {
    const n = (data.sku_risks as unknown[])?.length ?? 0
    return `${n} SKU${n !== 1 ? 's' : ''} at risk`
  }
  if (agent === 'agent_5') {
    const n = (data.alternatives as unknown[])?.length ?? 0
    return `${n} alternative${n !== 1 ? 's' : ''} found`
  }
  if (agent === 'agent_1_synthesis') return 'alert composed'
  if (agent === 'no_alert') return 'below severity threshold'
  return ''
}

interface Props {
  updates: AgentUpdate[]
  isRunning: boolean
}

export function PipelineTimeline({ updates, isRunning }: Props) {
  const completedIds = new Set(updates.map(u => u.agent))
  const hasNoAlert = completedIds.has('no_alert')
  const steps = hasNoAlert
    ? [PIPELINE_STEPS[0], NO_ALERT_STEP]
    : PIPELINE_STEPS

  const activeIndex = steps.findIndex(s => !completedIds.has(s.id))

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', damping: 22, stiffness: 120 }}
      className="w-full max-w-lg mx-auto my-8"
    >
      <p className="text-xs font-mono text-muted uppercase tracking-widest mb-5 text-center">
        Pipeline
      </p>
      <div className="relative flex flex-col gap-0">
        {steps.map((step, i) => {
          const done = completedIds.has(step.id)
          const active = isRunning && i === activeIndex
          const update = updates.find(u => u.agent === step.id)

          return (
            <motion.div
              key={step.id}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex items-start gap-4"
            >
              {/* Spine */}
              <div className="flex flex-col items-center">
                {/* Dot */}
                <div className="relative mt-0.5">
                  {active && (
                    <motion.div
                      className="absolute inset-0 rounded-full bg-blue/40"
                      animate={{ scale: [1, 2, 1], opacity: [0.8, 0, 0.8] }}
                      transition={{ duration: 1.6, repeat: Infinity }}
                    />
                  )}
                  <div
                    className={`w-3 h-3 rounded-full border-2 transition-all duration-300 ${
                      done
                        ? 'bg-green border-green shadow-[0_0_8px_#22C55E80]'
                        : active
                        ? 'bg-blue border-blue'
                        : 'bg-card border-border'
                    }`}
                  />
                </div>
                {/* Line to next */}
                {i < steps.length - 1 && (
                  <div
                    className={`w-px flex-1 min-h-[32px] mt-1 transition-colors duration-500 ${
                      done ? 'bg-green/30' : 'bg-border'
                    }`}
                  />
                )}
              </div>

              {/* Content */}
              <div className="pb-8 flex-1">
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-medium transition-colors duration-300 ${
                    done ? 'text-[#F8FAFC]' : active ? 'text-blue' : 'text-muted'
                  }`}>
                    {step.icon} {step.label}
                  </span>
                  {active && (
                    <span className="flex gap-0.5">
                      {[0, 1, 2].map(d => (
                        <motion.span
                          key={d}
                          className="w-1 h-1 rounded-full bg-blue"
                          animate={{ opacity: [0.3, 1, 0.3] }}
                          transition={{ duration: 0.9, repeat: Infinity, delay: d * 0.2 }}
                        />
                      ))}
                    </span>
                  )}
                </div>
                {done && update && (
                  <motion.p
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-xs font-mono text-muted mt-0.5"
                  >
                    {stepSummary(step.id, update.data)}
                  </motion.p>
                )}
              </div>
            </motion.div>
          )
        })}
      </div>
    </motion.div>
  )
}
