import { createContext } from 'react'
import type { ResolvedTheme, ThemeMode } from './themes'

export type ThemeContextValue = { mode: ThemeMode; resolvedTheme: ResolvedTheme; setMode: (mode: ThemeMode) => void; toggleTheme: () => void }
export const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)
