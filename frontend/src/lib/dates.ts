const DATE = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" });

/** Today in the browser's time zone, as the API's ISO date: "2026-10-06". */
export function todayIso(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** "2026-01-08" -> "8 Jan 2026". Parsed as a calendar date, not a UTC instant. */
export function formatDate(iso: string): string {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  return DATE.format(new Date(year ?? 1970, (month ?? 1) - 1, day ?? 1));
}
