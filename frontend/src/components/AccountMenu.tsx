import { Link } from "@tanstack/react-router";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";
import type { Language } from "../api/generated";
import { LANGUAGE_NAMES, useI18n } from "../i18n";
import { applyTheme, initialTheme, type Theme } from "../theme";
import { Icon } from "./icons";

const ITEM =
  "flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm hover:bg-bg focus-visible:outline-2 focus-visible:outline-accent";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="border-t border-border p-1.5">
      <p className="px-3 pt-1.5 pb-1 text-xs font-semibold uppercase tracking-wide text-muted">
        {title}
      </p>
      {children}
    </div>
  );
}

/**
 * The signed-in user's menu: household settings (categories, members, activity log, the demo),
 * language, theme and sign-out, so the header keeps its tabs for the everyday pages.
 */
export function AccountMenu({
  name,
  email,
  inDemo,
  onDemo,
  onLanguageChange,
  onSignOut,
}: {
  name: string;
  email: string;
  /** In the demo, its members are fictitious: the members page is left out (F-ADM-5). */
  inDemo: boolean;
  /** Open the demo, or leave it when in it. */
  onDemo: () => void;
  onLanguageChange: (language: Language) => void;
  onSignOut: () => void;
}) {
  const { t, language, setLanguage } = useI18n();
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const languageName = useId();

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      button.current?.focus();
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const close = () => setOpen(false);
  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    setTheme(next);
  };

  return (
    <div ref={root} className="relative">
      <button
        ref={button}
        type="button"
        aria-label={t.nav.accountMenu(name)}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-full border border-border py-1 pr-2.5 pl-1 text-sm hover:border-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        <span
          aria-hidden="true"
          className="flex size-7 items-center justify-center rounded-full bg-primary-100 font-display font-bold text-primary-800 dark:bg-primary-900 dark:text-primary-200"
        >
          {name.charAt(0).toUpperCase()}
        </span>
        <span className="hidden max-w-32 truncate sm:inline">{name}</span>
        <Icon
          name="chevron"
          className={`size-4 text-muted transition ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div
          id={panelId}
          className="absolute right-0 z-20 mt-2 w-64 overflow-hidden rounded-lg border border-border bg-surface shadow-lg"
        >
          <div className="px-4 py-3">
            <p className="truncate font-semibold">{name}</p>
            {/* The demo members' addresses are technical: none to show. */}
            {!inDemo && <p className="truncate text-sm text-muted">{email}</p>}
          </div>

          <Section title={t.nav.household}>
            <Link to="/spending/categories" className={ITEM} onClick={close}>
              <Icon name="tag" className="size-4 text-muted" />
              {t.nav.categories}
            </Link>
            {!inDemo && (
              <Link to="/members" className={ITEM} onClick={close}>
                <Icon name="users" className="size-4 text-muted" />
                {t.nav.members}
              </Link>
            )}
            <Link to="/activity" className={ITEM} onClick={close}>
              <Icon name="history" className="size-4 text-muted" />
              {t.nav.activity}
            </Link>
            <button
              type="button"
              className={ITEM}
              onClick={() => {
                close();
                onDemo();
              }}
            >
              <Icon name="flask" className="size-4 text-muted" />
              {inDemo ? t.demo.leave : t.demo.open}
            </button>
          </Section>

          <Section title={t.nav.preferences}>
            <fieldset className="px-3 py-1.5">
              <legend className="sr-only">{t.common.language}</legend>
              <div className="grid grid-cols-2 rounded-md border border-border p-0.5 text-sm">
                {(Object.keys(LANGUAGE_NAMES) as Language[]).map((code) => (
                  <label key={code} className="cursor-pointer">
                    <input
                      type="radio"
                      name={languageName}
                      value={code}
                      checked={language === code}
                      onChange={() => {
                        setLanguage(code);
                        onLanguageChange(code);
                      }}
                      className="peer sr-only"
                    />
                    <span
                      lang={code}
                      className="block rounded px-2 py-1 text-center text-muted peer-checked:bg-accent peer-checked:font-semibold peer-checked:text-bg peer-focus-visible:outline-2 peer-focus-visible:outline-accent"
                    >
                      {LANGUAGE_NAMES[code]}
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
            <button type="button" className={ITEM} onClick={toggleTheme}>
              <Icon name={theme === "dark" ? "sun" : "moon"} className="size-4 text-muted" />
              {theme === "dark" ? t.common.lightTheme : t.common.darkTheme}
            </button>
          </Section>

          <div className="border-t border-border p-1.5">
            <button type="button" className={ITEM} onClick={onSignOut}>
              <Icon name="signOut" className="size-4 text-muted" />
              {t.common.signOut}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
