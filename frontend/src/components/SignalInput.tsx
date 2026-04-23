import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'

const EXAMPLES = [
  'Major flooding in Zhengzhou, Henan province disrupts manufacturing operations',
  'Taiwan port strike at Keelung entering day 3, container backlogs reported',
  'Light fog at Rotterdam causes minor delays, expected to clear by noon',
]

interface Props {
  onSubmit: (signal: string) => void
  compact?: boolean
  disabled?: boolean
}

export function SignalInput({ onSubmit, compact, disabled }: Props) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (!compact && textareaRef.current) textareaRef.current.focus()
  }, [compact])

  function handleSubmit() {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSubmit(trimmed)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSubmit()
  }

  return (
    <motion.div layout className="w-full max-w-2xl mx-auto">
      {!compact && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex gap-2 flex-wrap justify-center mb-3"
        >
          {EXAMPLES.map((ex, i) => (
            <button
              key={i}
              onClick={() => setValue(ex)}
              className="text-xs px-3 py-1.5 rounded-full border border-border text-muted hover:border-ring hover:text-[#F8FAFC] transition-colors"
            >
              {ex.length > 48 ? ex.slice(0, 48) + '…' : ex}
            </button>
          ))}
        </motion.div>
      )}

      <div className="relative rounded-xl border border-border bg-card focus-within:border-ring transition-colors">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder="Describe a supply chain disruption signal…"
          rows={compact ? 2 : 4}
          className="w-full bg-transparent text-[#F8FAFC] placeholder-muted text-sm font-sans px-4 pt-4 pb-12 resize-none outline-none rounded-xl"
        />
        <div className="absolute bottom-3 right-3 flex items-center gap-2">
          {!compact && (
            <span className="text-xs text-muted">⌘ Enter to analyze</span>
          )}
          <button
            onClick={handleSubmit}
            disabled={!value.trim() || disabled}
            className="px-4 py-1.5 rounded-lg bg-indigo text-white text-sm font-medium
                       hover:bg-indigo/80 disabled:opacity-40 disabled:cursor-not-allowed
                       transition-all active:scale-95"
          >
            Analyze
          </button>
        </div>
      </div>
    </motion.div>
  )
}
