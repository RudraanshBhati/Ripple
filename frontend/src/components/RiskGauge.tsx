import { motion } from 'framer-motion'

interface Props {
  score: number
  size?: number
}

function scoreColor(score: number) {
  if (score >= 0.8) return '#EF4444'
  if (score >= 0.6) return '#F97316'
  if (score >= 0.35) return '#F59E0B'
  return '#22C55E'
}

function arcPath(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const toRad = (d: number) => (d * Math.PI) / 180
  const sx = cx + r * Math.cos(toRad(startDeg))
  const sy = cy + r * Math.sin(toRad(startDeg))
  const ex = cx + r * Math.cos(toRad(endDeg))
  const ey = cy + r * Math.sin(toRad(endDeg))
  const sweep = endDeg - startDeg
  const largeArc = sweep > 180 ? 1 : 0
  return `M ${sx} ${sy} A ${r} ${r} 0 ${largeArc} 1 ${ex} ${ey}`
}

export function RiskGauge({ score, size = 96 }: Props) {
  const cx = 60
  const cy = 60
  const r = 46
  const startDeg = 150
  const totalArc = 240
  const endDeg = startDeg + totalArc
  const fillEnd = startDeg + score * totalArc
  const color = scoreColor(score)
  const label = score >= 0.8 ? 'CRITICAL' : score >= 0.6 ? 'HIGH' : score >= 0.35 ? 'MEDIUM' : 'LOW'

  return (
    <svg width={size} height={size} viewBox="0 0 120 120">
      {/* Track */}
      <path
        d={arcPath(cx, cy, r, startDeg, endDeg)}
        fill="none"
        stroke="#1e2d45"
        strokeWidth="8"
        strokeLinecap="round"
      />
      {/* Animated fill */}
      <motion.path
        d={arcPath(cx, cy, r, startDeg, fillEnd)}
        fill="none"
        stroke={color}
        strokeWidth="8"
        strokeLinecap="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 1.2, ease: 'easeOut', delay: 0.2 }}
        style={{ filter: `drop-shadow(0 0 6px ${color}80)` }}
      />
      {/* Score text */}
      <text
        x="60"
        y="57"
        textAnchor="middle"
        dominantBaseline="middle"
        fill="#F8FAFC"
        fontSize="18"
        fontWeight="600"
        fontFamily="JetBrains Mono, monospace"
      >
        {score.toFixed(2)}
      </text>
      <text
        x="60"
        y="73"
        textAnchor="middle"
        dominantBaseline="middle"
        fill={color}
        fontSize="8"
        fontWeight="500"
        fontFamily="Inter, sans-serif"
        letterSpacing="1"
      >
        {label}
      </text>
    </svg>
  )
}
