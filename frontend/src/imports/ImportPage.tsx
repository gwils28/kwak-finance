import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getRouteApi, Link } from "@tanstack/react-router";
import { type ChangeEvent, useId, useState } from "react";
import {
  createImport,
  type ImportBatchOut,
  type ImportPreview,
  listAccounts,
  listImports,
  previewImport,
  rollbackImport,
} from "../api/generated";
import { apiErrorMessage, detailSentence } from "../auth/errors";
import { Button, ErrorAlert } from "../components/ui";
import { formatDate } from "../lib/dates";
import { formatEur } from "../lib/money";

const route = getRouteApi("/app/accounts/$accountId/import");

const STATUS_LABELS = {
  new: "New",
  duplicate: "Already imported",
  before_opening: "Before opening date",
} as const;

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

async function failure(error: unknown, response: Response | undefined): Promise<never> {
  throw new Error(
    response?.status === 422
      ? (detailSentence(error) ?? "This file cannot be imported.")
      : apiErrorMessage(response, { 413: "This file is too large (2 MB at most)." }),
  );
}

export function ImportPage() {
  const { accountId } = route.useParams();
  const queryClient = useQueryClient();
  const inputId = useId();
  const accounts = useQuery({
    queryKey: ["accounts", { includeClosed: false }],
    queryFn: async () =>
      (await listAccounts({ query: { include_closed: false }, throwOnError: true })).data,
  });
  const account = accounts.data?.find((a) => a.id === accountId);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportBatchOut | null>(null);

  const preview = useMutation({
    mutationFn: async (chosen: File) => {
      const { data, error, response } = await previewImport({
        path: { account_id: accountId },
        body: { file: chosen },
      });
      return data ?? failure(error, response);
    },
  });

  const commit = useMutation({
    mutationFn: async (chosen: File) => {
      const { data, error, response } = await createImport({
        path: { account_id: accountId },
        body: { file: chosen },
      });
      return data ?? failure(error, response);
    },
    onSuccess: async (batch) => {
      setResult(batch);
      preview.reset();
      await queryClient.invalidateQueries({ queryKey: ["accounts"] });
      await queryClient.invalidateQueries({ queryKey: ["imports", accountId] });
    },
  });

  const choose = (event: ChangeEvent<HTMLInputElement>) => {
    const chosen = event.target.files?.[0] ?? null;
    setFile(chosen);
    setResult(null);
    commit.reset();
    if (chosen) preview.mutate(chosen);
  };

  const title = account ? `Import into ${account.name}` : "Import";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/accounts" className="text-sm text-muted hover:text-accent">
          ← Accounts
        </Link>
        <h1 className="mt-1 text-3xl font-black tracking-tight">{title}</h1>
        {account && (
          <p className="text-sm text-muted">
            {account.institution} · balance {formatEur(account.balance)} · operations before{" "}
            {formatDate(account.opening_date)} are ignored (opening date)
          </p>
        )}
      </div>
      <div className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-4">
        <label htmlFor={inputId} className="text-sm font-medium">
          Bank export (CSV)
        </label>
        <input id={inputId} type="file" accept=".csv,text/csv" onChange={choose} />
        <p className="text-xs text-muted">
          Société Générale: account page, “Télécharger”, CSV format. Nothing is saved until you
          confirm, and importing the same file twice adds nothing.
        </p>
      </div>
      {preview.isPending && <p className="text-sm text-muted">Reading the file…</p>}
      <ErrorAlert message={preview.error?.message ?? commit.error?.message ?? null} />
      {result && <ImportResult batch={result} />}
      {preview.data && file && (
        <Preview
          preview={preview.data}
          busy={commit.isPending}
          onImport={() => commit.mutate(file)}
        />
      )}
      <History accountId={accountId} />
    </div>
  );
}

function Preview({
  preview,
  busy,
  onImport,
}: {
  preview: ImportPreview;
  busy: boolean;
  onImport: () => void;
}) {
  const { counts } = preview;
  const summary = [
    `${counts.new} new`,
    counts.duplicate > 0 && `${counts.duplicate} already imported`,
    counts.before_opening > 0 && `${counts.before_opening} before the opening date`,
    counts.error > 0 && plural(counts.error, "error"),
  ].filter(Boolean);

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold">Preview</h2>
          <p className="text-sm text-muted">{preview.format_label}</p>
          {preview.period && (
            <p className="text-sm text-muted">
              From {formatDate(preview.period.start)} to {formatDate(preview.period.end)}
              {preview.bank_balance &&
                ` · bank balance ${formatEur(preview.bank_balance.amount)} on ${formatDate(preview.bank_balance.on)}`}
            </p>
          )}
          <p className="mt-1 font-medium">{summary.join(" · ")}</p>
        </div>
        <Button onClick={onImport} disabled={busy || counts.new === 0}>
          {counts.new === 0
            ? "Nothing new to import"
            : `Import ${plural(counts.new, "new operation")}`}
        </Button>
      </div>
      {preview.already_imported_at && (
        <p className="rounded-md border border-warning px-3 py-2 text-sm">
          This file was already imported on {formatDate(preview.already_imported_at)}.
        </p>
      )}
      {preview.errors.length > 0 && (
        <ul className="rounded-md border border-negative px-3 py-2 text-sm text-negative">
          {preview.errors.map((e) => (
            <li key={`${e.line}-${e.message}`}>
              {e.line === 0 ? "File" : `Line ${e.line}`}: {e.message}
            </li>
          ))}
        </ul>
      )}
      <div className="overflow-x-auto rounded-lg border border-border bg-surface">
        <table aria-label="Rows in the file" className="w-full text-sm">
          <thead className="text-left text-muted">
            <tr>
              <th className="px-3 py-2 font-medium">Date</th>
              <th className="px-3 py-2 font-medium">Label</th>
              <th className="px-3 py-2 text-right font-medium">Amount</th>
              <th className="px-3 py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {preview.rows.map((r) => (
              <tr key={r.line} className={r.status === "new" ? "" : "text-muted"}>
                <td className="whitespace-nowrap px-3 py-2">{formatDate(r.booked_on)}</td>
                <td className="px-3 py-2">{r.label}</td>
                <td
                  className={`tabular whitespace-nowrap px-3 py-2 text-right ${
                    Number(r.amount) < 0 ? "" : "text-positive"
                  }`}
                >
                  {formatEur(r.amount)}
                </td>
                <td className="whitespace-nowrap px-3 py-2">{STATUS_LABELS[r.status]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ImportResult({ batch }: { batch: ImportBatchOut }) {
  const check = batch.balance_check;
  const skipped = [
    batch.duplicate_count > 0 && `${batch.duplicate_count} already imported`,
    batch.skipped_count > 0 && `${batch.skipped_count} before the opening date`,
  ].filter(Boolean);
  return (
    <section className="flex flex-col gap-2 rounded-lg border border-accent bg-surface p-4">
      <p className="font-medium">{plural(batch.imported_count, "operation")} imported.</p>
      {skipped.length > 0 && <p className="text-sm text-muted">Skipped: {skipped.join(", ")}.</p>}
      {check && check.difference === "0.00" && (
        <p className="text-sm text-positive">
          The balance matches the bank: {formatEur(check.bank)} on {formatDate(check.on)}.
        </p>
      )}
      {check && check.difference !== "0.00" && (
        <p role="alert" className="text-sm text-warning">
          The computed balance ({formatEur(check.computed)}) differs from the bank's (
          {formatEur(check.bank)}) by {formatEur(check.difference)} on {formatDate(check.on)}. Check
          the account's opening balance and date, or import the missing period.
        </p>
      )}
    </section>
  );
}

function History({ accountId }: { accountId: string }) {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState<string | null>(null);
  const batches = useQuery({
    queryKey: ["imports", accountId],
    queryFn: async () =>
      (await listImports({ path: { account_id: accountId }, throwOnError: true })).data,
  });
  const rollback = useMutation({
    mutationFn: async (batchId: string) =>
      rollbackImport({ path: { batch_id: batchId }, throwOnError: true }),
    onSuccess: async () => {
      setConfirming(null);
      await queryClient.invalidateQueries({ queryKey: ["imports", accountId] });
      await queryClient.invalidateQueries({ queryKey: ["accounts"] });
    },
  });

  if (!batches.data || batches.data.length === 0) return null;
  return (
    <section>
      <h2 className="mb-2 text-xl font-bold">Previous imports</h2>
      <ul
        aria-label="Previous imports"
        className="divide-y divide-border rounded-lg border border-border bg-surface"
      >
        {batches.data.map((b) => (
          <li key={b.id} className="flex flex-wrap items-center justify-between gap-4 px-4 py-3">
            <div>
              <p className="font-medium">{b.file_name}</p>
              <p className="text-sm text-muted">
                {formatDate(b.created_at)} · {plural(b.imported_count, "operation")} imported
                {b.rolled_back_at && ` · Rolled back on ${formatDate(b.rolled_back_at)}`}
              </p>
            </div>
            {!b.rolled_back_at &&
              b.imported_count > 0 &&
              (confirming === b.id ? (
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    className="border-negative text-negative"
                    disabled={rollback.isPending}
                    onClick={() => rollback.mutate(b.id)}
                  >
                    Confirm: delete its {plural(b.imported_count, "operation")}
                  </Button>
                  <Button variant="ghost" onClick={() => setConfirming(null)}>
                    Cancel
                  </Button>
                </div>
              ) : (
                <Button variant="ghost" onClick={() => setConfirming(b.id)}>
                  Roll back
                </Button>
              ))}
          </li>
        ))}
      </ul>
    </section>
  );
}
