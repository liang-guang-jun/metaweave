import { useEffect, useMemo, useState, type PropsWithChildren } from "react";
import { ThemeProvider as StyledThemeProvider } from "styled-components";
import { themes, type ResolvedTheme, type ThemeMode } from "./themes";
import { ThemeContext } from "./ThemeContext";

const STORAGE_KEY = "metaweave-theme-mode";
function readMode(): ThemeMode {
  if (typeof window === "undefined") return "system";
  const saved = window.localStorage.getItem(STORAGE_KEY);
  return saved === "light" || saved === "dark" ? saved : "system";
}

function getSystemTheme(): ResolvedTheme {
  return typeof window !== "undefined" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function ThemeProvider({ children }: PropsWithChildren) {
  const [mode, setModeState] = useState<ThemeMode>(readMode);
  const [systemTheme, setSystemTheme] = useState<ResolvedTheme>(getSystemTheme);
  const resolvedTheme: ResolvedTheme = mode === "system" ? systemTheme : mode;

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = (event: MediaQueryListEvent) =>
      setSystemTheme(event.matches ? "dark" : "light");
    media.addEventListener("change", handleChange);
    return () => media.removeEventListener("change", handleChange);
  }, []);

  const theme = useMemo(() => themes[resolvedTheme], [resolvedTheme]);
  const setMode = (nextMode: ThemeMode) => {
    setModeState(nextMode);
    if (nextMode === "system") window.localStorage.removeItem(STORAGE_KEY);
    else window.localStorage.setItem(STORAGE_KEY, nextMode);
  };
  const toggleTheme = () =>
    setMode(resolvedTheme === "dark" ? "light" : "dark");
  const value = { mode, resolvedTheme, setMode, toggleTheme };
  return (
    <ThemeContext.Provider value={value}>
      <StyledThemeProvider theme={theme}>
        <div data-theme={resolvedTheme}>{children}</div>
      </StyledThemeProvider>
    </ThemeContext.Provider>
  );
}
