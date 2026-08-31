/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Page background
        void: '#07090C',
        // Surface scale
        surface: {
          base:    '#0D1017',
          raised:  '#131820',
          overlay: '#1A2030',
        },
        // Zone A — AI Advisory (Violet)
        ai: {
          base:   '#7C3AED',
          dim:    '#4C1D95',
          text:   '#C4B5FD',
          border: 'rgba(124, 58, 237, 0.25)',
          muted:  'rgba(124, 58, 237, 0.12)',
        },
        // Zone B — Deterministic / Guardrail (Teal)
        guard: {
          base:   '#0D9488',
          dim:    '#134E4A',
          text:   '#5EEAD4',
          border: 'rgba(13, 148, 136, 0.25)',
          muted:  'rgba(13, 148, 136, 0.12)',
        },
        // Zone C — Recovered / Success (Emerald)
        recover: {
          base:   '#059669',
          text:   '#6EE7B7',
          border: 'rgba(5, 150, 105, 0.25)',
          muted:  'rgba(5, 150, 105, 0.12)',
        },
        // Zone D — Risk / Escalation (Amber)
        risk: {
          base:   '#D97706',
          text:   '#FCD34D',
          border: 'rgba(217, 119, 6, 0.25)',
          muted:  'rgba(217, 119, 6, 0.12)',
        },
        // Zone E — Hard Failure (Rose)
        halt: {
          base:   '#E11D48',
          text:   '#FDA4AF',
          border: 'rgba(225, 29, 72, 0.25)',
          muted:  'rgba(225, 29, 72, 0.10)',
        },
        // Category colors (independent of zone system)
        cat: {
          c1: { base: '#D97706', text: '#FCD34D', muted: 'rgba(217, 119, 6, 0.12)' },    // amber
          c2: { base: '#2563EB', text: '#93C5FD', muted: 'rgba(37, 99, 235, 0.12)' },    // blue
          c3: { base: '#EA580C', text: '#FDBA74', muted: 'rgba(234, 88, 12, 0.12)' },    // orange
          c4: { base: '#E11D48', text: '#FDA4AF', muted: 'rgba(225, 29, 72, 0.10)' },    // rose
          c5: { base: '#52525B', text: '#A1A1AA', muted: 'rgba(82, 82, 91, 0.15)' },     // zinc
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Cascadia Code', 'monospace'],
      },
      fontSize: {
        '2xs': ['10px', { lineHeight: '14px' }],
      },
      borderWidth: {
        '3': '3px',
      },
      animation: {
        'fade-in':       'fadeIn 0.15s ease-out forwards',
        'slide-up':      'slideUp 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'slide-in-right':'slideInRight 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'shimmer':       'shimmer 1.5s infinite',
        'live-pulse':    'livePulse 2s ease-in-out infinite',
        'spin-slow':     'spin 2s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%':   { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInRight: {
          '0%':   { opacity: '0', transform: 'translateX(12px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% center' },
          '100%': { backgroundPosition: '200% center' },
        },
        livePulse: {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '0.4' },
        },
      },
      boxShadow: {
        'ai':    '0 0 0 1px rgba(124, 58, 237, 0.25), 0 4px 16px -4px rgba(124, 58, 237, 0.15)',
        'guard': '0 0 0 1px rgba(13, 148, 136, 0.25), 0 4px 16px -4px rgba(13, 148, 136, 0.10)',
      },
    },
  },
  plugins: [],
}
