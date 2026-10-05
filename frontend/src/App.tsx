import { useEffect, useState } from "react";
import { applyTheme, initialTheme, type Theme } from "./theme";

type ApiStatus = { kind: "loading" } | { kind: "ok"; version: string } | { kind: "down" };

export function App() {
  const [api, setApi] = useState<ApiStatus>({ kind: "loading" });
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((body: { version: string }) => setApi({ kind: "ok", version: body.version }))
      .catch(() => setApi({ kind: "down" }));
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    setTheme(next);
  };

  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      <header className="flex items-center justify-between">
        <h1 className="text-4xl font-black tracking-tight">Kwak Finance</h1>
        <button
          type="button"
          onClick={toggleTheme}
          className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm hover:border-accent"
        >
          {theme === "dark" ? "Light" : "Dark"} theme
        </button>
      </header>
      <p className="mt-2 text-muted">Household budget and net worth — phase 0 skeleton.</p>
      <p className="mt-8 text-sm">
        {api.kind === "loading" && <span className="text-muted">Checking API…</span>}
        {api.kind === "ok" && <span className="text-positive">API ok · v{api.version}</span>}
        {api.kind === "down" && <span className="text-negative">API unreachable</span>}
      </p>
    </main>
  );
}
