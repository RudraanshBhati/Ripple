export interface SKURisk {
  sku_id: string
  current_stock: number
  daily_consumption: number
  runout_date: string
  lead_time_days: number
  gap_days: number
  risk_score: number
  confidence: number
}

export interface Supplier {
  supplier_id: string
  name: string
  country: string
  tier: number | string
  exposure_type: string
}

export interface Alternative {
  supplier_id: string
  name: string
  country: string
  similarity_score: number
  estimated_lead_time: number
  confidence: number
}

export interface Alert {
  _id: string
  session_id: string
  user_id: string
  signal: string
  signal_type: string | null
  severity_score: number
  alert_type: string
  final_alert: string | null
  affected_entities: string[]
  affected_suppliers: Supplier[]
  sku_risks: SKURisk[]
  alternatives: Alternative[]
  tier2_exposure: boolean
  invisible_risk: boolean
  created_at: string
}

export interface ChatMessage {
  _id?: string
  session_id: string
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
  metadata?: Record<string, unknown>
}

export interface AgentUpdate {
  agent: string
  data: Record<string, unknown>
  trace: string[]
  completedAt: number
}

export interface CompleteResult {
  session_id: string
  final_alert: string | null
  signal_type: string | null
  severity_score: number
  affected_suppliers: Supplier[]
  tier2_exposure: boolean
  invisible_risk: boolean
  sku_risks: SKURisk[]
  alternatives: Alternative[]
  reasoning_trace: string[]
}

export type AppState = 'idle' | 'running' | 'done' | 'error'

export interface PortWeather {
  name: string
  label: string
  region: string
  lat: number
  lon: number
  temp: number
  feels_like: number
  humidity: number
  description: string
  condition_id: number
  icon: string
  wind_speed: number
  visibility: number
  is_disruptive: boolean
}

export interface NewsArticle {
  _id: string
  title: string
  description: string
  url: string
  source: string
  image: string
  content: string
  published_at: string
  fetched_at: string
  category: "weather" | "geopolitical" | "other"
}
