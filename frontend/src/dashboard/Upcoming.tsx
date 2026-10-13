import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { type Scope, upcomingRecurring } from "../api/generated";
import { Button } from "../components/ui";
import { useI18n } from "../i18n";
import { formatDate } from "../lib/dates";
import { formatEur, formatEurWhole } from "../lib/money";
import { entryDraft, StatusBadge, useCashAccounts, useSkip } from "../recurring/shared";
import { type EntryDraft, TransactionForm } from "../transactions/TransactionForm";

/** F-REC-4: what is still expected this month, late first, and the balance it leads to. */
export function Upcoming({ scope }: { scope: Scope }) {
  const { t } = useI18n();
  const [entry, setEntry] = useState<EntryDraft | null>(null);
  const accounts = useCashAccounts();
  const skip = useSkip();
  const query = useQuery({
    queryKey: ["recurring", "upcoming", { scope }],
    queryFn: async () => (await upcomingRecurring({ query: { scope }, throwOnError: true })).data,
    placeholderData: keepPreviousData,
  });
  const data = query.data;
  if (!data || data.occurrences.length === 0) return null;

  return (
    <section
      aria-label={t.recurring.upcomingTitle}
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h2 className="text-lg font-bold">{t.recurring.upcomingTitle}</h2>
          <p className="max-w-xl text-xs text-muted">{t.recurring.upcomingHelp}</p>
        </div>
        <div className="flex flex-col items-end gap-0.5">
          <span className="text-sm text-muted">{t.recurring.projectedBalance}</span>
          <span className="text-2xl font-semibold">{formatEurWhole(data.projected_balance)}</span>
          <span className="text-xs text-muted">
            {t.recurring.currentBalance(formatEurWhole(data.current_balance))}
          </span>
        </div>
      </div>
      {entry && accounts && (
        <TransactionForm draft={entry} accounts={accounts} onDone={() => setEntry(null)} />
      )}
      <ul className="divide-y divide-border text-sm">
        {data.occurrences.map((o) => {
          const date = formatDate(o.due);
          return (
            <li
              key={`${o.item_id}|${o.due}`}
              className="flex flex-wrap items-center justify-between gap-3 py-2"
            >
              <span className="flex flex-wrap items-center gap-3">
                <span className="w-24 whitespace-nowrap">{date}</span>
                <StatusBadge status={o.status} />
                <span className="flex flex-col">
                  <span className="font-medium">{o.label}</span>
                  <span className="text-xs text-muted">{o.account_name}</span>
                </span>
              </span>
              <span className="flex items-center gap-2">
                <span
                  className={`tabular whitespace-nowrap ${o.expected.startsWith("-") ? "" : "text-positive"}`}
                >
                  {o.estimated ? t.recurring.approx(formatEur(o.expected)) : formatEur(o.expected)}
                </span>
                <Button
                  variant="ghost"
                  aria-label={t.recurring.enterNamed(o.label, date)}
                  onClick={() => setEntry(entryDraft(o, o))}
                >
                  {t.recurring.enterIt}
                </Button>
                <Button
                  variant="ghost"
                  aria-label={t.recurring.skipNamed(o.label, date)}
                  disabled={skip.isPending}
                  onClick={() => skip.mutate({ itemId: o.item_id, due: o.due, skip: true })}
                >
                  {t.recurring.skip}
                </Button>
              </span>
            </li>
          );
        })}
      </ul>
      <Link to="/recurring" className="self-start text-sm text-accent hover:underline">
        {t.recurring.manage}
      </Link>
    </section>
  );
}
