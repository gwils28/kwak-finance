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
  updateAccount,
} from "../api/generated";
import { apiErrorMessage, detailSentence, translateApiMessage } from "../auth/errors";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import type { Messages } from "../i18n/en";
import { formatDate } from "../lib/dates";
import { formatEur } from "../lib/money";

const route = getRouteApi("/app/accounts/$accountId/import");

async function failure(
  t: Messages,
  error: unknown,
  response: Response | undefined,
): Promise<never> {
  throw new Error(
    response?.status === 422
      ? (detailSentence(error) ?? t.imports.cannotImport)
      : apiErrorMessage(t, response, { 413: t.imports.tooLarge }),
  );
}

export function ImportPage() {
  const { accountId } = route.useParams();
  const { t } = useI18n();
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
      return data ?? failure(t, error, response);
    },
  });

  const commit = useMutation({
    mutationFn: async (chosen: File) => {
      const { data, error, response } = await createImport({
        path: { account_id: accountId },
        body: { file: chosen },
      });
      return data ?? failure(t, error, response);
    },
    onSuccess: async (batch) => {
      setResult(batch);
      preview.reset();
      await queryClient.invalidateQueries({ queryKey: ["accounts"] });
      await queryClient.invalidateQueries({ queryKey: ["imports", accountId] });
    },
  });

  const openOn = useMutation({
    mutationFn: async (openingDate: string) =>
      updateAccount({
        path: { account_id: accountId },
        body: { opening_date: openingDate },
        throwOnError: true,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["accounts"] });
      if (file) preview.mutate(file);
    },
  });

  const choose = (event: ChangeEvent<HTMLInputElement>) => {
    const chosen = event.target.files?.[0] ?? null;
    setFile(chosen);
    setResult(null);
    commit.reset();
    if (chosen) preview.mutate(chosen);
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/accounts" className="text-sm text-muted hover:text-accent">
          {t.imports.back}
        </Link>
        <h1 className="mt-1 text-3xl font-black tracking-tight">
          {account ? t.imports.titleInto(account.name) : t.imports.title}
        </h1>
        {account && (
          <p className="text-sm text-muted">
            {t.imports.accountLine(
              account.institution,
              formatEur(account.balance),
              formatDate(account.opening_date),
            )}
          </p>
        )}
      </div>
      <div className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-4">
        <label htmlFor={inputId} className="text-sm font-medium">
          {t.imports.fileLabel}
        </label>
        <input id={inputId} type="file" accept=".csv,text/csv" onChange={choose} />
        <p className="text-xs text-muted">{t.imports.fileHelp}</p>
      </div>
      {preview.isPending && <p className="text-sm text-muted">{t.imports.reading}</p>}
      <ErrorAlert message={preview.error?.message ?? commit.error?.message ?? null} />
      {result && <ImportResult batch={result} />}
      {preview.data && file && (
        <Preview
          preview={preview.data}
          openingDate={account?.opening_date}
          busy={commit.isPending || openOn.isPending}
          onImport={() => commit.mutate(file)}
          onOpenOn={(day) => openOn.mutate(day)}
        />
      )}
      <History accountId={accountId} />
    </div>
  );
}

function Preview({
  preview,
  openingDate,
  busy,
  onImport,
  onOpenOn,
}: {
  preview: ImportPreview;
  openingDate: string | undefined;
  busy: boolean;
  onImport: () => void;
  onOpenOn: (day: string) => void;
}) {
  const { t } = useI18n();
  const { counts } = preview;
  const earliest = preview.rows
    .filter((r) => r.status === "before_opening")
    .map((r) => r.booked_on)
    .sort()[0];
  const summary = [
    t.imports.countNew(counts.new),
    counts.duplicate > 0 && t.imports.countDuplicate(counts.duplicate),
    counts.before_opening > 0 && t.imports.countBeforeOpening(counts.before_opening),
    counts.error > 0 && t.imports.countErrors(counts.error),
  ].filter(Boolean);

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold">{t.imports.preview}</h2>
          <p className="text-sm text-muted">{preview.format_label}</p>
          {preview.period && (
            <p className="text-sm text-muted">
              {t.imports.period(formatDate(preview.period.start), formatDate(preview.period.end))}
              {preview.bank_balance &&
                t.imports.bankBalance(
                  formatEur(preview.bank_balance.amount),
                  formatDate(preview.bank_balance.on),
                )}
            </p>
          )}
          <p className="mt-1 font-medium">{summary.join(" · ")}</p>
        </div>
        <Button onClick={onImport} disabled={busy || counts.new === 0}>
          {counts.new === 0 ? t.imports.nothingNew : t.imports.importNew(counts.new)}
        </Button>
      </div>
      {counts.before_opening > 0 && earliest && (
        <div className="flex flex-col gap-2 rounded-md border border-warning px-3 py-2 text-sm">
          <p>
            {t.imports.beforeOpening(
              counts.before_opening,
              openingDate ? formatDate(openingDate) : null,
            )}
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="ghost" disabled={busy} onClick={() => onOpenOn(earliest)}>
              {t.imports.openOn(formatDate(earliest))}
            </Button>
            <span className="text-xs text-muted">{t.imports.openOnHelp}</span>
          </div>
        </div>
      )}
      {preview.already_imported_at && (
        <p className="rounded-md border border-warning px-3 py-2 text-sm">
          {t.imports.alreadyImported(formatDate(preview.already_imported_at))}
        </p>
      )}
      {preview.errors.length > 0 && (
        <ul className="rounded-md border border-negative px-3 py-2 text-sm text-negative">
          {preview.errors.map((e) => (
            <li key={`${e.line}-${e.message}`}>
              {e.line === 0 ? t.imports.fileError : t.imports.lineError(e.line)}:{" "}
              {translateApiMessage(e.message)}
            </li>
          ))}
        </ul>
      )}
      <div className="overflow-x-auto rounded-lg border border-border bg-surface">
        <table aria-label={t.imports.rowsTable} className="w-full text-sm">
          <thead className="text-left text-muted">
            <tr>
              <th className="px-3 py-2 font-medium">{t.imports.date}</th>
              <th className="px-3 py-2 font-medium">{t.imports.label}</th>
              <th className="px-3 py-2 text-right font-medium">{t.imports.amount}</th>
              <th className="px-3 py-2 font-medium">{t.imports.status}</th>
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
                <td className="whitespace-nowrap px-3 py-2">{t.imports.statuses[r.status]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ImportResult({ batch }: { batch: ImportBatchOut }) {
  const { t } = useI18n();
  const check = batch.balance_check;
  const skipped = [
    batch.duplicate_count > 0 && t.imports.countDuplicate(batch.duplicate_count),
    batch.skipped_count > 0 && t.imports.countBeforeOpening(batch.skipped_count),
  ].filter(Boolean);
  return (
    <section className="flex flex-col gap-2 rounded-lg border border-accent bg-surface p-4">
      <p className="font-medium">{t.imports.imported(batch.imported_count)}</p>
      {skipped.length > 0 && (
        <p className="text-sm text-muted">{t.imports.skipped(skipped.join(", "))}</p>
      )}
      {check && check.difference === "0.00" && (
        <p className="text-sm text-positive">
          {t.imports.balanceMatches(formatEur(check.bank), formatDate(check.on))}
        </p>
      )}
      {check && check.difference !== "0.00" && (
        <p role="alert" className="text-sm text-warning">
          {t.imports.balanceDiffers(
            formatEur(check.computed),
            formatEur(check.bank),
            formatEur(check.difference),
            formatDate(check.on),
          )}
        </p>
      )}
    </section>
  );
}

function History({ accountId }: { accountId: string }) {
  const { t } = useI18n();
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
      <h2 className="mb-2 text-xl font-bold">{t.imports.previous}</h2>
      <ul
        aria-label={t.imports.previous}
        className="divide-y divide-border rounded-lg border border-border bg-surface"
      >
        {batches.data.map((b) => (
          <li key={b.id} className="flex flex-wrap items-center justify-between gap-4 px-4 py-3">
            <div>
              <p className="font-medium">{b.file_name}</p>
              <p className="text-sm text-muted">
                {t.imports.historyLine(formatDate(b.created_at), b.imported_count)}
                {b.rolled_back_at && t.imports.rolledBack(formatDate(b.rolled_back_at))}
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
                    {t.imports.confirmRollback(b.imported_count)}
                  </Button>
                  <Button variant="ghost" onClick={() => setConfirming(null)}>
                    {t.common.cancel}
                  </Button>
                </div>
              ) : (
                <Button variant="ghost" onClick={() => setConfirming(b.id)}>
                  {t.imports.rollBack}
                </Button>
              ))}
          </li>
        ))}
      </ul>
    </section>
  );
}
