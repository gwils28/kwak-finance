/** A user-facing message for a failed API call. 429 always reports how long to wait. */
export function apiErrorMessage(
  response: Response | undefined,
  byStatus: Partial<Record<number, string>> = {},
): string {
  if (response?.status === 429) {
    const seconds = Number(response.headers.get("Retry-After"));
    const minutes = Number.isFinite(seconds) && seconds > 0 ? Math.ceil(seconds / 60) : null;
    const wait = minutes === null ? "later" : `in ${minutes} minute${minutes === 1 ? "" : "s"}`;
    return `Too many failed attempts. Try again ${wait}.`;
  }
  return (response && byStatus[response.status]) ?? "Something went wrong. Please try again.";
}
