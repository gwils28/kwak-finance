/**
 * The interface language, read by every formatter. Set by the I18nProvider; a module-level
 * value so plain functions (formatEur, formatDate…) need no React context.
 */
import type { Language } from "../api/generated";

const LOCALES: Record<Language, string> = { en: "en-GB", fr: "fr-FR" };
let current: Language = "en";

export function setCurrentLanguage(language: Language): void {
  current = language;
}

export function currentLanguage(): Language {
  return current;
}

export function locale(language: Language = current): string {
  return LOCALES[language];
}

const numberFormats = new Map<string, Intl.NumberFormat>();
const dateFormats = new Map<string, Intl.DateTimeFormat>();

/** A cached Intl.NumberFormat for the current language, or the one given (a document's). */
export function numberFormat(
  options: Intl.NumberFormatOptions,
  language: Language = current,
): Intl.NumberFormat {
  const key = `${locale(language)}|${JSON.stringify(options)}`;
  let format = numberFormats.get(key);
  if (!format) {
    format = new Intl.NumberFormat(locale(language), options);
    numberFormats.set(key, format);
  }
  return format;
}

/** A cached Intl.DateTimeFormat for the current language, or the one given. */
export function dateFormat(
  options: Intl.DateTimeFormatOptions,
  language: Language = current,
): Intl.DateTimeFormat {
  const key = `${locale(language)}|${JSON.stringify(options)}`;
  let format = dateFormats.get(key);
  if (!format) {
    format = new Intl.DateTimeFormat(locale(language), options);
    dateFormats.set(key, format);
  }
  return format;
}

/** French if the browser asks for it first, English otherwise. */
export function browserLanguage(): Language {
  const preferred =
    typeof navigator === "undefined" ? [] : (navigator.languages ?? [navigator.language]);
  return preferred[0]?.toLowerCase().startsWith("fr") ? "fr" : "en";
}
