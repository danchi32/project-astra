export type Theme = "light" | "dark" | "system";

const KEY = "astra-theme";

export function getTheme(): Theme {
  if (typeof window === "undefined") return "system";
  return (localStorage.getItem(KEY) as Theme) || "system";
}

export function applyTheme(theme: Theme): void {
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const dark = theme === "dark" || (theme === "system" && prefersDark);
  document.documentElement.classList.toggle("dark", dark);
}

export function setTheme(theme: Theme): void {
  localStorage.setItem(KEY, theme);
  applyTheme(theme);
}
