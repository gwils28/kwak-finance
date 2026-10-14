import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { linkTransfer, type TransactionOut, transferCandidates } from "../api/generated";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { formatDate } from "../lib/dates";
import { formatEur } from "../lib/money";
import { afterTransferChange } from "./TransferBanner";

/** "Link to…" (F-TX-5): pick the other side of a transfer the detection missed. */
export function LinkPanel({
  transaction,
  onDone,
}: {
  transaction: TransactionOut;
  onDone: (message: string) => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const candidates = useQuery({
    queryKey: ["transferCandidates", transaction.id],
    queryFn: async () =>
      (await transferCandidates({ path: { transaction_id: transaction.id }, throwOnError: true }))
        .data,
  });
  const link = useMutation({
    mutationFn: async (otherId: string) => {
      const outflow = transaction.amount.startsWith("-");
      const { response } = await linkTransfer({
        body: outflow
          ? { outflow_id: transaction.id, inflow_id: otherId }
          : { outflow_id: otherId, inflow_id: transaction.id },
      });
      if (!response?.ok) throw new Error(t.transactions.linkFailed);
    },
    onSuccess: async () => {
      await afterTransferChange(queryClient);
      onDone(t.transactions.transfersLinked(1));
    },
  });

  return (
    <section
      aria-label={t.transactions.linkTitle}
      className="flex flex-col gap-3 rounded-lg border border-accent bg-surface p-4"
    >
      <div>
        <h2 className="text-lg font-bold">{t.transactions.linkTitle}</h2>
        <p className="text-sm">
          {t.transactions.linkSource(transaction.label, formatEur(transaction.amount))}
        </p>
        <p className="text-xs text-muted">{t.transactions.linkHelp}</p>
      </div>
      {candidates.isError && <ErrorAlert message={t.transactions.loadFailed} />}
      {candidates.data?.length === 0 && (
        <p className="text-sm text-muted">{t.transactions.noCandidates}</p>
      )}
      {candidates.data && candidates.data.length > 0 && (
        <ul className="divide-y divide-border text-sm">
          {candidates.data.map((c) => {
            const date = formatDate(c.booked_on);
            return (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-3 py-2">
                <span className="flex flex-wrap items-center gap-3">
                  <span className="w-24 whitespace-nowrap">{date}</span>
                  <span className="flex flex-col">
                    <span className="font-medium">{c.label}</span>
                    <span className="text-xs text-muted">{c.account_name}</span>
                  </span>
                </span>
                <span className="flex items-center gap-2">
                  <span className="tabular whitespace-nowrap">{formatEur(c.amount)}</span>
                  <Button
                    variant="ghost"
                    aria-label={t.transactions.linkWith(c.label, date)}
                    disabled={link.isPending}
                    onClick={() => link.mutate(c.id)}
                  >
                    {t.transactions.link}
                  </Button>
                </span>
              </li>
            );
          })}
        </ul>
      )}
      <ErrorAlert message={link.error?.message ?? null} />
      <Button variant="ghost" className="self-start" onClick={() => onDone("")}>
        {t.common.cancel}
      </Button>
    </section>
  );
}
