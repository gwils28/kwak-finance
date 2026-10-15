/** The colour keys a wealth category can take (`WEALTH_COLOURS` in kwak_core.wealth), in order. */
export const WEALTH_COLOURS = [
  "savings",
  "current",
  "stocks",
  "crypto",
  "bonds",
  "private-equity",
  "gold",
  "real-estate",
  "equipment",
  "exotic",
  "debts",
] as const;

/** A category's colour: its `wealth-*` token (spec §7). */
export const wealthColour = (key: string) => `var(--color-wealth-${key})`;
