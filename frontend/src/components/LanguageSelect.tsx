import { useId } from "react";
import type { Language } from "../api/generated";
import { LANGUAGE_NAMES, useI18n } from "../i18n";

/** Pick the interface language; `onChange` saves it with the account when signed in. */
export function LanguageSelect({ onChange }: { onChange?: (language: Language) => void }) {
  const { language, setLanguage, t } = useI18n();
  const id = useId();
  return (
    <span className="flex items-center gap-1">
      <label htmlFor={id} className="sr-only">
        {t.common.language}
      </label>
      <select
        id={id}
        className="rounded-md border border-border bg-surface px-2 py-2 text-sm"
        value={language}
        onChange={(e) => {
          const next = e.target.value as Language;
          setLanguage(next);
          onChange?.(next);
        }}
      >
        {(Object.keys(LANGUAGE_NAMES) as Language[]).map((code) => (
          <option key={code} value={code} lang={code}>
            {LANGUAGE_NAMES[code]}
          </option>
        ))}
      </select>
    </span>
  );
}
