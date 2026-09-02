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
        // ── Backgrounds ──
        void: '#07090C',
        surface: {
          base:    '#0D1017',
          raised:  '#131820',
          overlay: '#1A2030',
        },

        // ── Zone A: AI Advisory (Violet) ──
        // Use ONLY for: LLM proposals, AI reasoning, advisory outputs
        ai: {
          base:   '#7C3AED',
          dim:    '#4C1D95',
          text:   '#C4B5FD',
          border: 'rgba(124, 58, 237, 0.22)',
          muted:  'rgba(124, 58, 237, 0.10)',
        },

        // ── Zone B: Guardrail Authorization (Teal) ──
        // Use ONLY for: deterministic validation, policy authorization, safety checks
        guard: {
          base:   '#0D9488',
          dim:    '#134E4A',
          text:   '#5EEAD4',
          border: 'rgba(13, 148, 136, 0.22)',
          muted:  'rgba(13, 148, 136, 0.10)',
        },

        // ── Zone C: Verified Recovery (Emerald) ──
        // Use ONLY for: captured payments, attributed revenue, confirmed recovery
        recover: {
          base:   '#059669',
          text:   '#6EE7B7',
          border: 'rgba(5, 150, 105, 0.22)',
          muted:  'rgba(5, 150, 105, 0.10)',
        },

        // ── Zone D: Risk / Escalation (Amber) ──
        // Use for: revenue at risk, escalated cases, attention states
        risk: {
          base:   '#D97706',
          text:   '#FCD34D',
          border: 'rgba(217, 119, 6, 0.22)',
          muted:  'rgba(217, 119, 6, 0.10)',
        },

        // ── Zone E: Hard Failure (Rose) ──
        // Use for: TERMINAL_NO_ACTION, hard blocks, errors
        halt: {
          base:   '#E11D48',
          text:   '#FDA4AF',
          border: 'rgba(225, 29, 72, 0.22)',
          muted:  'rgba(225, 29, 72, 0.08)',
        },

        // ── Failure Category Colors (independent of zone system) ──
        cat: {
          c1: { base: '#D97706', text: '#FCD34D', muted: 'rgba(217, 119, 6, 0.10)' },
          c2: { base: '#2563EB', text: '#93C5FD', muted: 'rgba(37, 99, 235, 0.10)' },
          c3: { base: '#EA580C', text: '#FDBA74', muted: 'rgba(234, 88, 12, 0.10)' },
          c4: { base: '#E11D48', text: '#FDA4AF', muted: 'rgba(225, 29, 72, 0.08)' },
          c5: { base: '#52525B', text: '#A1A1AA', muted: 'rgba(82, 82, 91, 0.12)' },
        },

        // ── Text Scale ──
        text: {
          primary:   '#F0F2F5',
          secondary: '#9CA3AF',
          tertiary:  '#4B5563',
          disabled:  '#374151',
        },
      },

      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Cascadia Code', 'monospace'],
      },

      fontSize: {
        '2xs': ['10px', { lineHeight: '14px' }],
        'xs':  ['11px', { lineHeight: '16px' }],
        'sm':  ['12px', { lineHeight: '18px' }],
        'base': ['13px', { lineHeight: '20px' }],
      },

      borderWidth: {
        '1': '1px',
        '2': '2px',
        '3': '3px',
      },

      maxWidth: {
        'content': '1280px',
        'content-sm': '960px',
      },

      animation: {
        'fade-in':        'fadeIn 0.15s ease-out forwards',
        'slide-up':       'slideUp 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'slide-in-right': 'slideInRight 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'shimmer':        'shimmer 1.6s ease-in-out infinite',
        'live-pulse':     'livePulse 2s ease-in-out infinite',
        'spin-slow':      'spin 2s linear infinite',
        'state-enter':    'stateEnter 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards',
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
          '50%':      { opacity: '0.35' },
        },
        stateEnter: {
          '0%':   { opacity: '0', transform: 'translateY(4px) scale(0.98)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
      },

      boxShadow: {
        'ai':      '0 0 0 1px rgba(124, 58, 237, 0.20), 0 4px 16px -4px rgba(124, 58, 237, 0.12)',
        'guard':   '0 0 0 1px rgba(13, 148, 136, 0.20), 0 4px 16px -4px rgba(13, 148, 136, 0.10)',
        'recover': '0 0 0 1px rgba(5, 150, 105, 0.20), 0 4px 16px -4px rgba(5, 150, 105, 0.10)',
        'card':    '0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)',
        'toast':   '0 8px 32px rgba(0,0,0,0.5)',
      },
    },
  },
  plugins: [],
}
