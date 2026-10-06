import { createContext, type ReactNode, useContext, useMemo, useState } from "react";
import type { Language } from "../api/generated";
import { browserLanguage, setCurrentLanguage } from "../lib/locale";
import { en, type Messages } from "./en";
import { fr } from "./fr";

export const MESSAGES: Record<Language, Messages> = { en, fr };
export const LANGUAGE_NAMES: Record<Language, string> = { en: "English", fr: "Français" };

const STORAGE_KEY = "kwak-language";

/** The language to start with: the one last used on this browser, else the browser's own. */
export function initialLanguage(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "en" || stored === "fr") return stored;
  } catch {
    // Storage unavailable: fall back to the browser language.
  }
  return browserLanguage();
}

type I18n = { language: Language; t: Messages; setLanguage: (language: Language) => void };

const I18nContext = createContext<I18n | null>(null);

function apply(language: Language): void {
  setCurrentLanguage(language);
  document.documentElement.lang = language;
  try {
    localStorage.setItem(STORAGE_KEY, language);
  } catch {
    // Non-critical.
  }
}

export function I18nProvider({ initial, children }: { initial: Language; children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() => {
    apply(initial);
    return initial;
  });
  const value = useMemo<I18n>(
    () => ({
      language,
      t: MESSAGES[language],
      setLanguage: (next) => {
        apply(next);
        setLanguageState(next);
      },
    }),
    [language],
  );
  // Keyed by language: every formatted date and amount below re-renders in the new locale.
  return (
    <I18nContext.Provider value={value}>
      <div key={language} className="contents">
        {children}
      </div>
    </I18nContext.Provider>
  );
}

export function useI18n(): I18n {
  const i18n = useContext(I18nContext);
  if (!i18n) throw new Error("useI18n outside I18nProvider");
  return i18n;
}
