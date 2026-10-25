import { useEffect, useState } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "kwak-theme";

export function initialTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // Storage unavailable: fall back to the OS preference.
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Non-critical.
  }
}

const pageTheme = (): Theme =>
  document.documentElement.dataset.theme === "dark" ? "dark" : "light";

/** The theme on the page now, following each switch (the toggle sets it on the root). */
export function useDocumentTheme(): Theme {
  const [theme, setTheme] = useState<Theme>(pageTheme);
  useEffect(() => {
    const observer = new MutationObserver(() => setTheme(pageTheme()));
    observer.observe(document.documentElement, { attributeFilter: ["data-theme"] });
    // A switch between the first render and this subscription would otherwise be missed.
    setTheme(pageTheme());
    return () => observer.disconnect();
  }, []);
  return theme;
}
