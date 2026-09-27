export const tokens = {
  color: {
    brand: { 50: '#eff6ff', 100: '#dbeafe', 500: '#2563eb', 600: '#1d4ed8', 700: '#1e40af' },
    accent: { cyan: '#38bdf8', indigo: '#6366f1', violet: '#8b5cf6', purple: '#a855f7' },
    neutral: { 0: '#ffffff', 50: '#f8fafc', 100: '#f1f5f9', 200: '#e2e8f0', 300: '#cbd5e1', 400: '#94a3b8', 500: '#64748b', 600: '#475569', 700: '#334155', 800: '#1e293b', 900: '#0f172a', 950: '#071321' },
    status: { success: '#16a34a', warning: '#d97706', error: '#dc2626', info: '#0284c7' },
  },
  font: {
    family: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    mono: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
    size: { xs: '0.75rem', sm: '0.8125rem', md: '0.875rem', lg: '1rem', xl: '1.125rem', '2xl': '1.5rem', '3xl': '2rem', '4xl': 'clamp(2.25rem, 3.6vw, 3.625rem)' },
    weight: { regular: 400, medium: 500, semibold: 650, bold: 700, heavy: 760 },
    lineHeight: { tight: 1.04, snug: 1.2, normal: 1.5, relaxed: 1.65 },
    letterSpacing: { tight: '-0.055em', snug: '-0.03em', normal: '0', wide: '0.12em' },
  },
  space: { 0: '0', 1: '0.25rem', 2: '0.5rem', 3: '0.75rem', 4: '1rem', 5: '1.25rem', 6: '1.5rem', 8: '2rem', 10: '2.5rem', 12: '3rem', 16: '4rem' },
  radius: { sm: '0.375rem', md: '0.625rem', lg: '0.875rem', xl: '1.25rem', pill: '999px' },
  border: { thin: '1px', medium: '2px' },
  shadow: { sm: '0 6px 14px rgba(30, 41, 59, 0.05)', md: '0 10px 18px rgba(37, 99, 235, 0.17)', lg: '0 24px 70px rgba(26, 37, 56, 0.12)' },
  motion: { fast: '0.16s', normal: '0.32s', slow: '0.55s', drawer: '0.6s', ease: 'cubic-bezier(0.2, 0.8, 0.2, 1)', labelEase: 'cubic-bezier(0.42, 0, 0.58, 1)' },
  breakpoint: { sm: '520px', md: '720px', lg: '920px', xl: '1200px' },
  zIndex: { base: 0, content: 1, overlay: 10, toast: 100 },
} as const

export type PrimitiveTokens = typeof tokens
