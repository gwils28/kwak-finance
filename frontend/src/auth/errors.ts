import { API_MESSAGES_FR, API_PATTERNS_FR } from "../i18n/common";
import type { Messages } from "../i18n/en";
import { currentLanguage } from "../lib/locale";

/** A user-facing message for a failed API call. 429 always reports how long to wait. */
export function apiErrorMessage(
  t: Messages,
  response: Response | undefined,
  byStatus: Partial<Record<number, string>> = {},
): string {
  if (response?.status === 429) {
    const seconds = Number(response.headers.get("Retry-After"));
    const minutes = Number.isFinite(seconds) && seconds > 0 ? Math.ceil(seconds / 60) : null;
    return t.errors.tooManyAttempts(minutes);
  }
  return (response && byStatus[response.status]) ?? t.errors.generic;
}

/** An API (or bank file) message in the interface language; unknown ones stay in English. */
export function translateApiMessage(message: string): string {
  if (currentLanguage() !== "fr") return message;
  const exact = API_MESSAGES_FR[message];
  if (exact) return exact;
  for (const [pattern, french] of API_PATTERNS_FR) {
    if (pattern.test(message)) return message.replace(pattern, french);
  }
  return message;
}

function sentence(text: string): string {
  const capitalised = text.charAt(0).toUpperCase() + text.slice(1);
  return capitalised.endsWith(".") ? capitalised : `${capitalised}.`;
}

/** The API's `detail` as a translated sentence: "password too short" -> "Password too short." */
export function detailSentence(error: unknown): string | null {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  if (typeof detail !== "string" || detail === "") return null;
  return sentence(translateApiMessage(detail));
}
