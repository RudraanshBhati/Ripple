import type { AgentUpdate } from '../types'
import { Icons } from './shared'

interface Props {
  agentUpdates: AgentUpdate[]
  isAnalyzing: boolean
}

const AGENT_DISPLAY: Record<string, string> = {
  orchestrator: 'Orchestrator',
  agent_2: 'Signal Scraper',
  agent_3: 'Supplier Mapping',
  agent_4: 'Risk & Chat',
  agent_5: 'Alt Sourcing',
  agent_1_synthesis: 'Report Compiler',
  no_alert: 'No Alert',
}

const AGENT_ORDER = ['agent_2', 'agent_3', 'agent_4', 'agent_5', 'agent_1_synthesis']

export function AgentsPanel({ agentUpdates, isAnalyzing }: Props) {
  const recentAgents = new Map<string, { status: string; last: string }>()

  for (const update of agentUpdates) {
    recentAgents.set(update.agent, {
      status: 'done',
      last: new Date(update.completedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    })
  }

  const lastAgent = agentUpdates.length > 0 ? agentUpdates[agentUpdates.length - 1].agent : null
  if (isAnalyzing && lastAgent) {
    recentAgents.set(lastAgent, { status: 'running', last: 'now' })
  }

  const agents = AGENT_ORDER.map((id, idx) => {
    const info = recentAgents.get(id)
    let status = 'idle'
    if (info) {
      status = info.status
    } else if (isAnalyzing && agentUpdates.length === 0 && idx === 0) {
      status = 'running'
    }
    return { id, name: AGENT_DISPLAY[id] ?? id, status, last: info?.last ?? '--' }
  })

  const doneCount = agents.filter(a => a.status === 'done').length

  return (
    <div className="panel">
      <div className="panel-head">
        <span style={{ color: doneCount > 0 ? '#16A34A' : 'var(--muted)' }}>{Icons.activity}</span>
        <div className="panel-title">Agents</div>
        <span className="panel-sub">{doneCount}/{agents.length}</span>
        {isAnalyzing && (
          <span className="badge badge-amber" style={{ marginLeft: 'auto' }}>running</span>
        )}
      </div>
      <div>
        {agents.map((a, i) => (
          <div key={a.id} style={{
            padding: '10px 14px',
            borderBottom: i < agents.length - 1 ? '1px solid var(--border)' : 'none',
            display: 'flex', gap: 10, alignItems: 'center',
          }}>
            <span className="mono" style={{ fontSize: 10, color: 'var(--muted)', width: 18 }}>#{i + 1}</span>
            <span style={{ flex: 1, fontSize: 12.5, fontWeight: 500 }}>{a.name}</span>
            <span className={`badge ${a.status === 'running' ? 'badge-amber' : a.status === 'done' ? 'badge-green' : 'badge-ghost'}`}>
              {a.status}
            </span>
            <span className="mono" style={{ fontSize: 10, color: 'var(--muted-2)', width: 40, textAlign: 'right' }}>{a.last}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
