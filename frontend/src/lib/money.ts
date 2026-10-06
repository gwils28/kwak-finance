/**
 * The API sends amounts as decimal strings ("1234.56"), never floats. Keep them as strings:
 * Intl formats a decimal string exactly.
 */
const EUR = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" });

export function formatEur(amount: string): string {
  return EUR.format(amount as Intl.StringNumericLiteral);
}

/** "1 500,5" or "1500.50" -> "1500.50"; null if not a whole number of cents. */
export function parseEurInput(text: string): string | null {
  const compact = text.replace(/[\s  €]/g, "").replace(",", ".");
  const match = /^([+-]?)(\d+)(?:\.(\d{1,2}))?$/.exec(compact);
  if (!match) return null;
  const [, sign, units, cents = ""] = match;
  return `${sign === "-" ? "-" : ""}${units}.${cents.padEnd(2, "0")}`;
}

const WHOLE_EUR = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});
const SIGNED_EUR = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
  signDisplay: "exceptZero",
});
const PERCENT = new Intl.NumberFormat("fr-FR", { style: "percent", maximumFractionDigits: 0 });
const SIGNED_PERCENT = new Intl.NumberFormat("fr-FR", {
  style: "percent",
  maximumFractionDigits: 0,
  signDisplay: "exceptZero",
});

// API amounts are decimal strings; Intl formats them exactly.
type Num = string | number;

/** "1621.04" -> "1 621 €": for overviews, where cents are noise. */
export function formatEurWhole(amount: Num): string {
  return WHOLE_EUR.format(amount as Intl.StringNumericLiteral);
}

/** "-60.00" -> "-60 €", "12" -> "+12 €". */
export function formatEurSigned(amount: Num): string {
  return SIGNED_EUR.format(amount as Intl.StringNumericLiteral);
}

/** A ratio as a percentage: "0.3564" -> "36 %". */
export function formatPercent(ratio: Num): string {
  return PERCENT.format(ratio as Intl.StringNumericLiteral);
}

/** A signed ratio: "0.2" -> "+20 %". */
export function formatPercentSigned(ratio: Num): string {
  return SIGNED_PERCENT.format(ratio as Intl.StringNumericLiteral);
}
