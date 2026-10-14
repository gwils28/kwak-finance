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

/** "-84.30" -> -8430: whole cents, so sums of amounts stay exact. */
export function toCents(amount: string): number {
  const [units, cents = ""] = amount.replace("-", "").split(".");
  const value = Number(units) * 100 + Number(cents.padEnd(2, "0").slice(0, 2));
  return amount.startsWith("-") ? -value : value;
}

/** -880 -> "-8.80": back to the API's decimal string. */
export function fromCents(cents: number): string {
  const size = Math.abs(cents);
  const text = `${Math.trunc(size / 100)}.${String(size % 100).padStart(2, "0")}`;
  return cents < 0 ? `-${text}` : text;
}

/** "0.00", "-0.00", "0": the API's decimal string is zero, read without a float. */
export function isZero(amount: string): boolean {
  return /^[+-]?0*(\.0*)?$/.test(amount) && /\d/.test(amount);
}

/** "12.50" -> "12,50" in French: how an API amount reads in an input. */
export function amountInput(amount: string): string {
  return currentLanguage() === "fr" ? amount.replace(".", ",") : amount;
}

/** "60.00" -> "60", "12.50" -> "12,50" (fr): an amount in an input, without empty cents. */
export function amountInputShort(amount: string): string {
  return amount.endsWith(".00") ? amount.slice(0, -3) : amountInput(amount);
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
