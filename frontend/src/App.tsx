import { useState, useEffect } from "react"
import { useAlerts } from "./hooks/useAlerts"
import { useChat } from "./hooks/useChat"
import { useRipple } from "./hooks/useRipple"
import { AlertsFeed } from "./components/AlertsFeed"
import { AlertDetail } from "./components/AlertDetail"
import { ChatPanel } from "./components/ChatPanel"
import { KPIStrip } from "./components/KPIStrip"
import { SKUWatchlist } from "./components/SKUWatchlist"
import { SignalsPanel } from "./components/SignalsPanel"
import { AgentsPanel } from "./components/AgentsPanel"
import { NewsDashboard } from "./components/NewsDashboard"
import { Logo, Icons } from "./components/shared"

function NewSignalModal({ onClose, onAnalyze }: { onClose: () => void; onAnalyze: (s: string) => void }) {
  const [text, setText] = useState("")
  const EXAMPLES = [
    "Severe flooding in Zhengzhou, China — Henan province factories shutting down",
    "Keelung port strike escalating, Taiwan — 48h backlog projected",
    "Red Sea shipping delays — vessels rerouting Cape of Good Hope, +14d transit",
  ]
  return (
    <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal-box">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <div style={{ fontSize: 15, fontWeight: 700 }}>New signal analysis</div>
          <button className="icon-btn" style={{ width: 28, height: 28 }} onClick={onClose}>{Icons.x}</button>
        </div>
        <p style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 12, lineHeight: 1.5 }}>
          Paste a disruption signal — news headline, weather alert, port update, or any supply chain event.
        </p>
        <textarea
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder="e.g. Flooding in Zhengzhou, China disrupts MCU manufacturing…"
          style={{
            width: "100%", minHeight: 100, border: "1px solid var(--border)", borderRadius: 8,
            padding: "10px 12px", fontSize: 13, fontFamily: "inherit", color: "var(--fg)",
            background: "var(--bg)", resize: "vertical", outline: "none", lineHeight: 1.5,
          }}
        />
        <div style={{ marginTop: 10, marginBottom: 14 }}>
          <div className="mono" style={{ fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>Examples</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {EXAMPLES.map(e => (
              <button key={e} className="btn btn-xs"
                style={{ justifyContent: "flex-start", textAlign: "left", height: "auto", padding: "5px 8px", whiteSpace: "normal", lineHeight: 1.4 }}
                onClick={() => setText(e)}>
                {e}
              </button>
            ))}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={!text.trim()} onClick={() => { onAnalyze(text.trim()); onClose() }}>
            {Icons.sparkles} Analyze
          </button>
        </div>
      </div>
    </div>
  )
}

export default function App() {
  const { alerts, loading: alertsLoading, refresh: refreshAlerts } = useAlerts(10000)
  const { appState, agentUpdates, sessionId: analysisSessionId, analyze } = useRipple()
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null)
  const [chatSessionId, setChatSessionId] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [activeNav, setActiveNav] = useState("Dashboard")
  const [scanStatus, setScanStatus] = useState<{ running: boolean; last_run: string | null; signals_new: number }>({
    running: false, last_run: null, signals_new: 0,
  })

  const { messages, sending, sendMessage, clearMessages } = useChat(chatSessionId)
  const isAnalyzing = appState === "running"

  useEffect(() => {
    if (appState === "done" && analysisSessionId) {
      setChatSessionId(analysisSessionId)
      refreshAlerts()
    }
  }, [appState, analysisSessionId, refreshAlerts])

  // Poll scrape status every 4 s; refresh alerts when a scan finishes
  useEffect(() => {
    let wasRunning = false
    const poll = async () => {
      try {
        const r = await fetch("/api/scrape-status")
        if (!r.ok) return
        const status = await r.json()
        setScanStatus(status)
        if (wasRunning && !status.running && status.signals_new > 0) refreshAlerts()
        wasRunning = status.running
      } catch {}
    }
    poll()
    const id = setInterval(poll, 4000)
    return () => clearInterval(id)
  }, [refreshAlerts])

  const handleScanNow = async () => {
    await fetch("/api/trigger-scrape", { method: "POST" })
    setScanStatus(s => ({ ...s, running: true }))
  }

  useEffect(() => {
    if (!selectedAlertId && alerts.length > 0) {
      setSelectedAlertId(alerts[0]._id)
      if (alerts[0].session_id) setChatSessionId(alerts[0].session_id)
    }
  }, [alerts, selectedAlertId])

  const selectedAlert = alerts.find(a => a._id === selectedAlertId) ?? null

  const handleSelectAlert = (id: string) => {
    setSelectedAlertId(id)
    const alert = alerts.find(a => a._id === id)
    if (alert?.session_id) setChatSessionId(alert.session_id)
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
      <div className="sap-chrome">
        <div className="sap-logo">SAP</div>
        <span className="sap-crumb">Home &rsaquo; Supply Chain &rsaquo; <b>Ripple</b></span>
        <div className="sap-icons">
          <span className="mono" style={{ fontSize: 10 }}>client 100</span>
          <span style={{ fontSize: 11 }}>user@ripple.io</span>
        </div>
      </div>

      <div className="ripple-header">
        <div className="brand">
          <Logo size={34}/>
          <div>
            <div className="brand-text">Ripple</div>
            <div className="brand-sub">for SAP</div>
          </div>
        </div>
        <div className="nav-links">
          {["Dashboard", "Alerts", "Suppliers", "SKUs", "Reports", "News"].map(n => (
            <button key={n} className={"nav-link " + (activeNav === n ? "active" : "")} onClick={() => setActiveNav(n)}>{n}</button>
          ))}
        </div>
        <div className="search">
          <span style={{ position: "absolute", left: 11, color: "var(--muted)" }}>{Icons.search}</span>
          <span style={{ flex: 1, userSelect: "none" }}>Search alerts, SKUs, suppliers…</span>
          <span className="badge badge-ghost" style={{ fontSize: 10 }}>⌘K</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            className={"btn btn-xs" + (scanStatus.running ? " btn-ghost" : "")}
            style={{ gap: 5, fontSize: 11, padding: "4px 10px" }}
            onClick={handleScanNow}
            disabled={scanStatus.running}
            title={scanStatus.last_run ? `Last scan: ${new Date(scanStatus.last_run).toLocaleTimeString()}` : "Scan world signals now"}
          >
            <span style={{ display: "inline-block", animation: scanStatus.running ? "spin 1s linear infinite" : "none" }}>
              {Icons.sparkles}
            </span>
            {scanStatus.running ? "Scanning…" : "Scan now"}
            {!scanStatus.running && scanStatus.signals_new > 0 && (
              <span className="badge" style={{ background: "var(--indigo)", color: "#fff", fontSize: 9, padding: "1px 5px" }}>
                {scanStatus.signals_new} new
              </span>
            )}
          </button>
          <button className="icon-btn">{Icons.help}</button>
          <button className="icon-btn">
            {Icons.bell}
            {alerts.length > 0 && <span className="notif-dot"/>}
          </button>
          <button className="icon-btn">{Icons.settings}</button>
          <div className="avatar">AC</div>
        </div>
      </div>

      <KPIStrip alerts={alerts} isAnalyzing={isAnalyzing}/>

      {activeNav === "News" ? (
        <NewsDashboard />
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "340px 1fr 380px", gap: 12, padding: "16px 20px 0", height: "calc(100vh - 220px)", minHeight: 720 }}>
            <AlertsFeed alerts={alerts} loading={alertsLoading} selectedId={selectedAlertId} onSelect={handleSelectAlert}/>
            <div className="panel" style={{ overflowY: "auto" }}>
              <AlertDetail alert={selectedAlert} onStartChat={sid => setChatSessionId(sid)}/>
            </div>
            <ChatPanel messages={messages} sending={sending} sessionId={chatSessionId} onSend={sendMessage} onNew={() => setShowModal(true)} onClear={clearMessages}/>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr 1fr", gap: 12, padding: "12px 20px 24px" }}>
            <SKUWatchlist alerts={alerts}/>
            <SignalsPanel alerts={alerts}/>
            <AgentsPanel agentUpdates={agentUpdates} isAnalyzing={isAnalyzing}/>
          </div>
        </>
      )}

      {showModal && <NewSignalModal onClose={() => setShowModal(false)} onAnalyze={s => analyze(s, "default")}/>}
    </div>
  )
}
