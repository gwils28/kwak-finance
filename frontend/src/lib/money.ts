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
