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
const SIGNED_RATE: Intl.NumberFormatOptions = {
  ...SIGNED_PERCENT,
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
};

// API amounts are decimal strings; Intl formats them exactly.
type Num = string | number;

/** "1621.04" -> "1 621 €" (fr) or "€1,621" (en): for overviews, where cents are noise. */
export function formatEurWhole(amount: Num): string {
  return numberFormat(WHOLE_EUR).format(amount as Intl.StringNumericLiteral);
}

const COMPACT_EUR: Intl.NumberFormatOptions = {
  ...EUR,
  notation: "compact",
  maximumFractionDigits: 1,
};

/** "250000" -> "€250K" (en) or "250 k€" (fr): for chart axes. */
export function formatEurCompact(amount: Num): string {
  return numberFormat(COMPACT_EUR).format(amount as Intl.StringNumericLiteral);
}

/** To the nearest €100, whole: the projection's amounts (F-SIM-5). */
export function formatEurHundreds(amount: Num): string {
  return formatEurWhole(Math.round(Number(amount) / 100) * 100);
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

/** A small yearly rate, to a tenth of a point, signed: "-0.003" -> "-0.3 %", "0.05" ->
 * "+5.0 %", where a whole percent would read 0 and hide that it is negative. */
export function formatRateSigned(ratio: Num): string {
  return numberFormat(SIGNED_RATE).format(ratio as Intl.StringNumericLiteral);
}

const RATE: Intl.NumberFormatOptions = { style: "percent", maximumFractionDigits: 2 };

/** A yearly rate to a hundredth of a point at most: "0.058" -> "5.8 %", "0.0325" -> "3.25 %". */
export function formatRate(ratio: Num): string {
  return numberFormat(RATE).format(ratio as Intl.StringNumericLiteral);
}

/** Moves a decimal string's point by `shift` places (right when positive), exactly. */
function shiftPoint(text: string, shift: number): string {
  const negative = text.startsWith("-");
  const [units = "", fraction = ""] = text.replace(/^[+-]/, "").split(".");
  const digits = units + fraction;
  const point = units.length + shift;
  const padded = point < 0 ? "0".repeat(-point) + digits : digits.padEnd(point, "0");
  const at = Math.max(point, 0);
  const whole = padded.slice(0, at).replace(/^0+(?=\d)/, "") || "0";
  const rest = padded.slice(at).replace(/0+$/, "");
  const value = rest ? `${whole}.${rest}` : whole;
  return negative && /[1-9]/.test(value) ? `-${value}` : value;
}

/** "0.065" -> "6.5" ("6,5" in French): a share as the percentage typed in an input. */
export function percentInput(share: string): string {
  const percent = shiftPoint(share, 2);
  return currentLanguage() === "fr" ? percent.replace(".", ",") : percent;
}

/** "6,5" -> "0.065": a typed percentage as a share, to `places` decimals of a percent at
 * most; null if it is not a number or is more precise. */
export function parsePercentInput(text: string, places = 1): string | null {
  const compact = text
    .replace(/[\s\u00a0\u202f%]/g, "")
    .replace(",", ".")
    .replace("−", "-");
  const match = /^[+-]?\d+(?:\.(\d+))?$/.exec(compact);
  if (!match || (match[1] ?? "").replace(/0+$/, "").length > places) return null;
  return shiftPoint(compact.replace(/^\+/, ""), -2);
}
