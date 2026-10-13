import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listAccounts,
  type OccurrenceOut,
  type OccurrenceStatus,
  type RecurringOut,
  skipOccurrence,
  unskipOccurrence,
} from "../api/generated";
import { useI18n } from "../i18n";
import { dateFormat } from "../lib/locale";
import type { EntryDraft } from "../transactions/TransactionForm";

const CASH = new Set(["checking", "savings"]);

/** Open cash accounts: the ones a transaction or a recurring item can be entered on. */
export function useCashAccounts() {
  const accounts = useQuery({
    queryKey: ["accounts", { includeClosed: true }],
    queryFn: async () =>
      (await listAccounts({ query: { include_closed: true }, throwOnError: true })).data,
  });
  return accounts.data?.filter((a) => CASH.has(a.type) && !a.closed_on);
}

/** "Enter it" (F-REC-3): the item's account, label, category and the occurrence's expected
 * amount, on the date the API proposes. */
export function entryDraft(
  item: Pick<RecurringOut, "account_id" | "label" | "category_id">,
  occurrence: Pick<OccurrenceOut, "enter_on" | "expected">,
): EntryDraft {
  return {
    account_id: item.account_id,
    booked_on: occurrence.enter_on,
    amount: occurrence.expected,
    label: item.label,
    category_id: item.category_id,
  };
}

const LOOK: Record<OccurrenceStatus, string> = {
  upcoming: "border-border text-muted",
  late: "border-warning text-warning",
  fulfilled: "border-positive text-positive",
  skipped: "border-border text-muted line-through",
};

/** The status in words, the colour only reinforcing it. */
export function StatusBadge({ status }: { status: OccurrenceStatus }) {
  const { t } = useI18n();
  return (
    <span className={`whitespace-nowrap rounded-md border px-2 py-0.5 text-xs ${LOOK[status]}`}>
      {t.recurring.status[status]}
    </span>
  );
}

/** Skips an occurrence, or restores a skipped one (F-REC-3). */
export function useSkip() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ itemId, due, skip }: { itemId: string; due: string; skip: boolean }) => {
      const options = { path: { item_id: itemId, due }, throwOnError: true } as const;
      return skip ? skipOccurrence(options) : unskipOccurrence(options);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["recurring"] }),
  });
}

/** Monday to Sunday in the interface language: 0 is Monday, as the API's weekly day. */
export function weekdayName(day: number): string {
  return dateFormat({ weekday: "long" }).format(new Date(2024, 0, 1 + day));
}

function monthName(iso: string): string {
  return dateFormat({ month: "long" }).format(new Date(2024, Number(iso.slice(5, 7)) - 1, 1));
}

/** "Monthly, on the 3rd", "Every Saturday"… */
export function useSchedule() {
  const { t } = useI18n();
  return (item: Pick<RecurringOut, "frequency" | "day" | "start_on">) => {
    switch (item.frequency) {
      case "weekly":
        return t.recurring.weekly(weekdayName(item.day));
      case "monthly":
        return t.recurring.monthly(item.day);
      case "quarterly":
        return t.recurring.quarterly(item.day, monthName(item.start_on));
      case "yearly":
        return t.recurring.yearly(item.day, monthName(item.start_on));
    }
  };
}
