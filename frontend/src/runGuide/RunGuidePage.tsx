import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { LanguageSelect } from "../components/LanguageSelect";
import { ThemeToggle } from "../components/ThemeToggle";
import { useI18n } from "../i18n";

/** "Running Kwak Finance": open without signing in, so it helps before the first account. */
export function RunGuidePage() {
  const { t } = useI18n();
  const g = t.runGuide;
  return (
    <div className="min-h-screen">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-4 px-4 py-3">
          <Link to="/" className="text-sm hover:text-accent">
            ← {g.backToApp}
          </Link>
          <div className="flex items-center gap-3">
            <LanguageSelect />
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-3xl font-black tracking-tight">{g.title}</h1>
        <p className="mt-3 text-muted">{g.intro}</p>
        <nav
          aria-label={g.contents}
          className="mt-6 rounded-lg border border-border bg-surface p-4"
        >
          <p className="mb-2 text-sm font-semibold">{g.contents}</p>
          <ol className="list-inside list-decimal space-y-1 text-sm">
            {g.sections.map((section) => (
              <li key={section.id}>
                <a href={`#${section.id}`} className="hover:text-accent">
                  {section.title}
                </a>
              </li>
            ))}
          </ol>
        </nav>
        {g.sections.map((section) => (
          <section key={section.id} id={section.id} className="mt-10 scroll-mt-4">
            <h2
              className={`text-xl font-bold tracking-tight ${section.id === "danger" ? "text-negative" : ""}`}
            >
              {section.title}
            </h2>
            {section.steps.map((step) => (
              <div key={step.text} className="mt-4">
                <p>{step.text}</p>
                {step.commands && (
                  <Commands lines={step.commands} copyable={section.id !== "danger"} />
                )}
              </div>
            ))}
          </section>
        ))}
      </main>
    </div>
  );
}

/** Dangerous commands are shown but get no copy button, so nobody pastes them by reflex. */
function Commands({ lines, copyable }: { lines: string[]; copyable: boolean }) {
  return (
    <ul className="mt-2 space-y-2">
      {lines.map((line) => (
        <li key={line}>
          <CommandLine line={line} copyable={copyable} />
        </li>
      ))}
    </ul>
  );
}

function CommandLine({ line, copyable }: { line: string; copyable: boolean }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(line);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div
      className={`flex items-start gap-2 rounded-md border bg-surface px-3 py-2 ${copyable ? "border-border" : "border-negative"}`}
    >
      <code className="min-w-0 flex-1 overflow-x-auto whitespace-pre font-mono text-sm">
        {line}
      </code>
      {copyable && (
        <button
          type="button"
          onClick={copy}
          className="shrink-0 rounded px-2 text-xs text-muted hover:text-accent focus-visible:outline-2 focus-visible:outline-accent"
        >
          {copied ? t.runGuide.copied : t.runGuide.copy}
        </button>
      )}
    </div>
  );
}
