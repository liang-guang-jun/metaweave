import { tokens, type PrimitiveTokens } from './tokens'

export type ThemeMode = 'system' | 'light' | 'dark'
export type ResolvedTheme = 'light' | 'dark'

export type Theme = PrimitiveTokens & {
  mode: ResolvedTheme
  color: PrimitiveTokens['color'] & {
    background: { canvas: string; surface: string; elevated: string; inverse: string }
    text: { primary: string; secondary: string; muted: string; inverse: string; brand: string }
    border: { subtle: string; default: string; focus: string }
    interactive: { primary: string; primaryHover: string; primaryPressed: string; secondary: string }
    auth: { bannerBackground: string; bannerGrid: string; bannerGlowPrimary: string; bannerGlowSecondary: string; heroTitle: string; heroDescription: string; nodeBackground: string; nodeBackgroundEnd: string; nodeBorder: string; nodeBorderAccent: string; nodeAccent: string; nodeAccentAlt: string; nodeText: string; nodeLine: string; nodeLineSecondary: string; capabilityBorder: string; capabilityBackground: string; capabilityText: string }
    sidebar: { background: string; text: string; activeBackground: string; hoverBackground: string }
  }
}

const lightTheme: Theme = {
  ...tokens,
  mode: 'light',
  color: {
    ...tokens.color,
    background: { canvas: '#f6f8fb', surface: '#ffffff', elevated: '#ffffff', inverse: tokens.color.neutral[950] },
    text: { primary: '#172033', secondary: tokens.color.neutral[600], muted: tokens.color.neutral[500], inverse: '#ffffff', brand: tokens.color.brand[600] },
    border: { subtle: '#edf1f6', default: '#d8dee9', focus: '#4f8df4' },
    interactive: { primary: tokens.color.brand[500], primaryHover: tokens.color.brand[600], primaryPressed: tokens.color.brand[700], secondary: tokens.color.neutral[50] },
    auth: { bannerBackground: '#071a2b', bannerGrid: '#79c7ff1a', bannerGlowPrimary: '#1f6792', bannerGlowSecondary: '#3d267c', heroTitle: '#ffffff', heroDescription: '#c7d8e8', nodeBackground: '#12354c', nodeBackgroundEnd: '#20286a', nodeBorder: '#69d6ff', nodeBorderAccent: '#b8a5ff', nodeAccent: '#2fc6df', nodeAccentAlt: '#9783ff', nodeText: '#d6f5ff', nodeLine: '#68d8ff', nodeLineSecondary: '#ad9aff', capabilityBorder: '#83c5e333', capabilityBackground: '#08263a99', capabilityText: '#d6ecfa' },
    sidebar: { background: '#101828', text: '#94a3b8', activeBackground: '#25324a', hoverBackground: '#1b273a' },
  },
}

const darkTheme: Theme = {
  ...tokens,
  mode: 'dark',
  color: {
    ...tokens.color,
    background: { canvas: '#071321', surface: '#101828', elevated: '#162338', inverse: '#ffffff' },
    text: { primary: '#eff8ff', secondary: '#c7d8e8', muted: '#94a3b8', inverse: '#071321', brand: '#72ddff' },
    border: { subtle: '#1e3348', default: '#30465d', focus: '#72ddff' },
    interactive: { primary: '#3b82f6', primaryHover: '#60a5fa', primaryPressed: '#2563eb', secondary: '#1e3348' },
    auth: { bannerBackground: '#071a2b', bannerGrid: '#79c7ff1a', bannerGlowPrimary: '#1f6792', bannerGlowSecondary: '#3d267c', heroTitle: '#ffffff', heroDescription: '#c7d8e8', nodeBackground: '#12354c', nodeBackgroundEnd: '#20286a', nodeBorder: '#69d6ff', nodeBorderAccent: '#b8a5ff', nodeAccent: '#2fc6df', nodeAccentAlt: '#9783ff', nodeText: '#d6f5ff', nodeLine: '#68d8ff', nodeLineSecondary: '#ad9aff', capabilityBorder: '#83c5e333', capabilityBackground: '#08263a99', capabilityText: '#d6ecfa' },
    sidebar: { background: '#101828', text: '#94a3b8', activeBackground: '#25324a', hoverBackground: '#1b273a' },
  },
}

export const themes: Record<ResolvedTheme, Theme> = { light: lightTheme, dark: darkTheme }
