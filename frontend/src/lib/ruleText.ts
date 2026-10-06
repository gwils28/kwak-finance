/**
 * The part of a bank label worth matching in a rule: the merchant or the other party,
 * without card numbers, dates and references that change every time.
 */
const PARTY = /\b(?:DE|POUR):\s*(.+?)(?=\s+(?:ID|MOTIF|REF|DATE):|\s+\d{2}\s\d{2}\s|$)/;
const NOISE = /^(?:CARTE|X\d+|\d{2}\/\d{2}|\d{2}H\d{2})$/;

export function suggestRuleText(label: string): string {
  const party = PARTY.exec(label)?.[1]?.trim();
  if (party) return party;
  // Drop the card prefix, dates and any token carrying a long number (references).
  const words = label.split(/\s+/).filter((w) => w && !NOISE.test(w) && !/\d{4,}/.test(w));
  return words.join(" ") || label.trim();
}
