/**
 * The API sends amounts as decimal strings ("1234.56"), never floats. Keep them as strings:
 * Intl formats a decimal string exactly. Formats follow the interface language.
 */
import { currentLanguage, numberFormat } from "./locale";

const EUR: Intl.NumberFormatOptions = { style: "currency", currency: "EUR" };

export function formatEur(amount: string): string {
  return numberFormat(EUR).format(amount as Intl.StringNumericLiteral);
}

/** "1 500,5" or "1500.50" -> "1500.50"; null if not a whole number of cents. */
export function parseEurInput(text: string): string | null {
  const compact = text.replace(/[\s  €]/g, "").replace(",", ".");
  const match = /^([+-]?)(\d+)(?:\.(\d{1,2}))?$/.exec(compact);
  if (!match) return null;
  const [, sign, units, cents = ""] = match;
  return `${sign === "-" ? "-" : ""}${units}.${cents.padEnd(2, "0")}`;
}

/** "12.50" -> "12,50" in French: how an API amount reads in an input. */
export function amountInput(amount: string): string {
  return currentLanguage() === "fr" ? amount.replace(".", ",") : amount;
}

const WHOLE_EUR: Intl.NumberFormatOptions = { ...EUR, maximumFractionDigits: 0 };
const SIGNED_EUR: Intl.NumberFormatOptions = { ...WHOLE_EUR, signDisplay: "exceptZero" };
const PERCENT: Intl.NumberFormatOptions = { style: "percent", maximumFractionDigits: 0 };
const SIGNED_PERCENT: Intl.NumberFormatOptions = { ...PERCENT, signDisplay: "exceptZero" };

// API amounts are decimal strings; Intl formats them exactly.
type Num = string | number;

/** "1621.04" -> "1 621 €" (fr) or "€1,621" (en): for overviews, where cents are noise. */
export function formatEurWhole(amount: Num): string {
  return numberFormat(WHOLE_EUR).format(amount as Intl.StringNumericLiteral);
}

/** "-60.00" -> "-60 €", "12" -> "+12 €". */
export function formatEurSigned(amount: Num): string {
  return numberFormat(SIGNED_EUR).format(amount as Intl.StringNumericLiteral);
}

/** A ratio as a percentage: "0.3564" -> "36 %". */
export function formatPercent(ratio: Num): string {
  return numberFormat(PERCENT).format(ratio as Intl.StringNumericLiteral);
}

/** A signed ratio: "0.2" -> "+20 %". */
export function formatPercentSigned(ratio: Num): string {
  return numberFormat(SIGNED_PERCENT).format(ratio as Intl.StringNumericLiteral);
}
