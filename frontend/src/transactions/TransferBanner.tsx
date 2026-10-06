import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  acceptTransferSuggestions,
  linkTransfer,
  type TransferSuggestion,
  transferSuggestions,
} from "../api/generated";
import { Button } from "../components/ui";
import { formatDate } from "../lib/dates";
import { formatEur } from "../lib/money";

/** Refresh everything a transfer changes: lists, counters, budget, suggestions. */
export async function afterTransferChange(queryClient: ReturnType<typeof useQueryClient>) {
  for (const key of ["transactions", "toCategorise", "transferSuggestions", "budget"]) {
    await queryClient.invalidateQueries({ queryKey: [key] });
  }
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

/** "N transfers between your accounts found": review and link them (F-TX-5). */
export function TransferBanner({ onNotice }: { onNotice: (message: string) => void }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const suggestions = useQuery({
    queryKey: ["transferSuggestions"],
    queryFn: async () => (await transferSuggestions({ throwOnError: true })).data,
  });
  const linkOne = useMutation({
    mutationFn: async (s: TransferSuggestion) =>
      linkTransfer({
        body: { outflow_id: s.outflow.id, inflow_id: s.inflow.id },
        throwOnError: true,
      }),
    onSuccess: () => afterTransferChange(queryClient),
  });
  const linkAll = useMutation({
    mutationFn: async () =>
      (await acceptTransferSuggestions({ body: {}, throwOnError: true })).data.linked,
    onSuccess: async (linked) => {
      onNotice(
        `${plural(linked, "transfer")} linked: ${linked === 1 ? "it no longer counts" : "they no longer count"} as spending.`,
      );
      await afterTransferChange(queryClient);
    },
  });

  const list = suggestions.data ?? [];
  if (list.length === 0) return null;
  return (
    <section
      aria-label="Transfers between your accounts"
      className="flex flex-col gap-3 rounded-lg border border-warning bg-surface px-4 py-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm">
          <span className="font-medium">
            {plural(list.length, "transfer")} between your accounts found
          </span>
          . Linked, they count neither as spending nor as income.
        </p>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => setOpen((o) => !o)}>
            {open ? "Hide" : "Review"}
          </Button>
          <Button disabled={linkAll.isPending} onClick={() => linkAll.mutate()}>
            Link all
          </Button>
        </div>
      </div>
      {open && (
        <ul className="divide-y divide-border text-sm">
          {list.map((s) => (
            <li
              key={`${s.outflow.id}-${s.inflow.id}`}
              className="flex flex-wrap items-center justify-between gap-3 py-2"
            >
              <span>
                <span className="tabular">{formatEur(s.inflow.amount)}</span> from{" "}
                <span className="font-medium">{s.outflow.account_name}</span> (
                {formatDate(s.outflow.booked_on)}) to{" "}
                <span className="font-medium">{s.inflow.account_name}</span> (
                {formatDate(s.inflow.booked_on)})
                <span className="block text-xs text-muted">
                  {s.outflow.label} → {s.inflow.label}
                </span>
              </span>
              <Button
                variant="ghost"
                disabled={linkOne.isPending}
                onClick={() => linkOne.mutate(s)}
              >
                Link
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
