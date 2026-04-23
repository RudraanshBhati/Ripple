import { useNews } from "../hooks/useNews"
import { usePortWeather } from "../hooks/usePortWeather"
import { Icons, fmtTime } from "./shared"
import type { NewsArticle, PortWeather } from "../types"

// --- Port weather helpers ---

function condColor(p: PortWeather) {
  if (p.is_disruptive) return "var(--red)"
  if (p.wind_speed > 10 || p.visibility < 5000) return "var(--amber)"
  return "var(--green)"
}

function tempColor(temp: number) {
  if (temp >= 38) return "var(--red)"
  if (temp >= 30) return "var(--amber)"
  if (temp <= 0) return "#60A5FA"
  return "var(--fg)"
}

function PortCard({ port }: { port: PortWeather }) {
  const dot = condColor(port)
  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8,
      padding: "10px 14px", minWidth: 148, flexShrink: 0, position: "relative",
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontWeight: 700, fontSize: 12.5, color: "var(--fg)", whiteSpace: "nowrap" }}>{port.name}</span>
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: dot, flexShrink: 0, marginLeft: 6 }} />
      </div>
      <div className="mono" style={{ fontSize: 10, color: "var(--muted)", marginBottom: 6 }}>{port.region}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginBottom: 4 }}>
        <span style={{ fontSize: 22, fontWeight: 700, color: tempColor(port.temp), lineHeight: 1 }}>
          {port.temp}°
        </span>
        <span style={{ fontSize: 11, color: "var(--muted)" }}>C</span>
      </div>
      <div style={{ fontSize: 11, color: "var(--fg-2)", textTransform: "capitalize", marginBottom: 5, lineHeight: 1.3 }}>
        {port.description}
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <span className="mono" style={{ fontSize: 10, color: "var(--muted)" }}>💨 {port.wind_speed} m/s</span>
        <span className="mono" style={{ fontSize: 10, color: "var(--muted)" }}>💧 {port.humidity}%</span>
      </div>
      {port.is_disruptive && (
        <div style={{ marginTop: 6 }}>
          <span className="badge badge-red" style={{ fontSize: 9 }}>⚠ Disruptive</span>
        </div>
      )}
    </div>
  )
}

function PortWeatherStrip() {
  const { ports, loading, fetchedAt, refresh } = usePortWeather(600000)

  return (
    <div style={{ marginBottom: 14 }}>
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <div className="panel-head" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span className="panel-title">🌐 Port Weather — Live</span>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {fetchedAt && (
              <span className="mono" style={{ fontSize: 10, color: "var(--muted)" }}>
                Updated {fmtTime(fetchedAt)}
              </span>
            )}
            <button
              className="btn btn-xs"
              style={{ padding: "2px 8px", fontSize: 10, gap: 4 }}
              onClick={refresh}
              disabled={loading}
            >
              <span style={{ display: "inline-block", animation: loading ? "spin 1s linear infinite" : "none" }}>
                {Icons.sparkles}
              </span>
              Refresh
            </button>
          </div>
        </div>
        <div style={{
          display: "flex", gap: 10, overflowX: "auto", padding: "12px 14px 14px",
          scrollbarWidth: "thin",
        }}>
          {loading && ports.length === 0 && (
            <div style={{ color: "var(--muted)", fontSize: 12, padding: "8px 4px" }}>
              Fetching port weather…
            </div>
          )}
          {!loading && ports.length === 0 && (
            <div style={{ color: "var(--muted)", fontSize: 12, padding: "8px 4px" }}>
              No weather data — check OPENWEATHER_API_KEY is set.
            </div>
          )}
          {ports.map(p => <PortCard key={p.name} port={p} />)}
        </div>
      </div>
    </div>
  )
}

// --- News article helpers ---

const CATEGORY_CONFIG = {
  weather:      { label: "Weather",      badge: "badge-amber",  icon: "🌩" },
  geopolitical: { label: "Geopolitical", badge: "badge-red",    icon: "⚡" },
  other:        { label: "Other",        badge: "badge-indigo", icon: "📰" },
}

function ArticleCard({ article }: { article: NewsArticle }) {
  const cfg = CATEGORY_CONFIG[article.category]
  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      className="alert-row"
      style={{ display: "block", textDecoration: "none", color: "inherit", padding: "12px 14px", borderRadius: 6 }}
    >
      {article.image && (
        <img
          src={article.image}
          alt=""
          style={{ width: "100%", height: 110, objectFit: "cover", borderRadius: 4, marginBottom: 8 }}
          onError={e => { (e.target as HTMLImageElement).style.display = "none" }}
        />
      )}
      <div style={{ fontWeight: 600, fontSize: 13, lineHeight: 1.4, color: "var(--fg)", marginBottom: 4 }}>
        {article.title}
      </div>
      {article.description && (
        <div style={{
          fontSize: 12, color: "var(--fg-2)", lineHeight: 1.4, marginBottom: 6,
          display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden",
        } as React.CSSProperties}>
          {article.description}
        </div>
      )}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className={`badge ${cfg.badge}`} style={{ fontSize: 10 }}>{cfg.icon} {cfg.label}</span>
          <span className="mono" style={{ fontSize: 10.5, color: "var(--muted)" }}>{article.source}</span>
        </div>
        <span className="mono" style={{ fontSize: 10.5, color: "var(--muted)", whiteSpace: "nowrap" }}>
          {fmtTime(article.published_at)}
        </span>
      </div>
    </a>
  )
}

function NewsColumn({ title, articles, loading, icon }: {
  title: string; articles: NewsArticle[]; loading: boolean; icon: string
}) {
  return (
    <div className="panel" style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div className="panel-head">
        <span className="panel-title">
          <span style={{ marginRight: 5 }}>{icon}</span>{title}
        </span>
        <span className="mono" style={{ fontSize: 10.5, color: "var(--muted)" }}>
          {loading ? "Refreshing…" : `${articles.length} articles`}
        </span>
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: "6px 4px" }}>
        {articles.length === 0 && !loading && (
          <div style={{ padding: "28px 16px", textAlign: "center", color: "var(--muted)", fontSize: 12, lineHeight: 1.6 }}>
            No articles yet.<br/>Click Refresh or wait for the next scan.
          </div>
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {articles.map(a => <ArticleCard key={a._id} article={a} />)}
        </div>
      </div>
    </div>
  )
}

// --- Main dashboard ---

export function NewsDashboard() {
  const { weather, geopolitical, other, loading, lastFetched, refresh, triggerScan, clearAndRescan, scanning } = useNews(60000)
  const busy = loading || scanning

  return (
    <div style={{ padding: "16px 20px 24px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 16, color: "var(--fg)" }}>News Dashboard</div>
          <div className="mono" style={{ fontSize: 10.5, color: "var(--muted)", marginTop: 2 }}>
            {lastFetched ? `Articles updated ${fmtTime(lastFetched.toISOString())}` : "Loading…"}
            {scanning && <span style={{ color: "var(--amber)", marginLeft: 8 }}>Scanning…</span>}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="btn btn-xs"
            style={{ gap: 5, fontSize: 11, padding: "4px 10px" }}
            onClick={triggerScan}
            disabled={busy}
            title="Fetch new articles from NewsAPI and classify with AI"
          >
            <span style={{ display: "inline-block", animation: scanning ? "spin 1s linear infinite" : "none" }}>
              {Icons.sparkles}
            </span>
            {scanning ? "Scanning…" : "Scan Now"}
          </button>
          <button
            className="btn btn-xs"
            style={{ fontSize: 11, padding: "4px 10px", opacity: 0.7 }}
            onClick={clearAndRescan}
            disabled={busy}
            title="Wipe stored articles and re-fetch from scratch"
          >
            Clear &amp; Rescan
          </button>
          <button
            className="btn btn-xs"
            style={{ fontSize: 11, padding: "4px 10px" }}
            onClick={refresh}
            disabled={busy}
          >
            Refresh
          </button>
        </div>
      </div>

      <PortWeatherStrip />

      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr 1fr",
        gap: 12,
        height: "calc(100vh - 380px)",
        minHeight: 480,
      }}>
        <NewsColumn title="Weather" articles={weather} loading={loading} icon="🌩" />
        <NewsColumn title="Geopolitical" articles={geopolitical} loading={loading} icon="⚡" />
        <NewsColumn title="Other" articles={other} loading={loading} icon="📰" />
      </div>
    </div>
  )
}
