import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/shared/theme/useTheme";
import { Clickable } from "@/shared/ui/Clickable";

export function ThemeSwitcher() {
  const { resolvedTheme, toggleTheme } = useTheme();
  return (
    <Clickable
      type="button"
      onClick={toggleTheme}
      aria-label={`Switch to ${resolvedTheme === "dark" ? "light" : "dark"} theme`}
      title={`Switch to ${resolvedTheme === "dark" ? "light" : "dark"} theme`}
    >
      {resolvedTheme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
    </Clickable>
  );
}
