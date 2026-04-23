/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      colors: {
        base: '#020617',
        card: '#0E1223',
        elevated: '#131c2e',
        border: '#1e2d45',
        ring: '#334155',
        muted: '#94A3B8',
        green: '#22C55E',
        red: '#EF4444',
        amber: '#F59E0B',
        blue: '#3B82F6',
        indigo: '#6366F1',
      },
    },
  },
  plugins: [],
}

