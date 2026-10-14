import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import {
  type CategoryOut,
  splitTransaction,
  type TransactionOut,
  unsplitTransaction,
  updateTransaction,
} from "../api/generated";
import { apiErrorMessage, detailSentence } from "../auth/errors";
import { Icon } from "../components/icons";
import { Button, ErrorAlert, TextField } from "../components/ui";
import { useI18n } from "../i18n";
import { amountInput, formatEur, fromCents, parseEurInput, toCents } from "../lib/money";
import { CategoryOptions } from "./categories";

const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";
/** The API takes 20 parts at most, the rest included. */
const MAX_GIVEN = 19;

type Row = { categoryId: string; amount: string };

/** A transaction's note, and its split over categories (F-TX-4). */
export function DetailsPanel({
  transaction,
  categories,
  onDone,
}: {
  transaction: TransactionOut;
  categories: CategoryOut[];
  onDone: () => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const parts = transaction.parts;
  const outflow = transaction.amount.startsWith("-");
  const [note, setNote] = useState(transaction.note ?? "");
  const [splitting, setSplitting] = useState(parts.length > 0);
  const [rows, setRows] = useState<Row[]>(
    parts.length > 0
      ? parts.slice(0, -1).map((p) => ({
          categoryId: p.category_id ?? "",
          amount: amountInput(p.amount.replace("-", "")),
        }))
      : [{ categoryId: transaction.category_id ?? "", amount: "" }],
  );
  const [restCategory, setRestCategory] = useState(parts.at(-1)?.category_id ?? "");
  const [invalid, setInvalid] = useState(false);
  const ids = { note: useId(), rest: useId(), part: useId() };
  // A transfer moves money between your accounts: it has no categories to split into.
  const canSplit = !transaction.transfer_group_id;

  const parsed = rows.map((r) => parseEurInput(r.amount));
  const given = parsed.every((p) => p !== null && !p.startsWith("-") && p !== "0.00");
  const restCents =
    Math.abs(toCents(transaction.amount)) -
    parsed.reduce((sum, p) => sum + (p ? toCents(p) : 0), 0);

  const refresh = async () => {
    for (const key of ["transactions", "toCategorise", "budget", "dashboard"]) {
      await queryClient.invalidateQueries({ queryKey: [key] });
    }
  };
  const fail = (error: unknown, response?: Response) =>
    new Error(
      response?.status === 422 || response?.status === 409
        ? (detailSentence(error) ?? t.errors.checkForm)
        : apiErrorMessage(t, response),
    );
  const noteChanged = note.trim() !== (transaction.note ?? "");
  // Only sent when the parts change: a note edit must not send back parts loaded earlier.
  const sign = outflow ? "-" : "";
  const wanted = rows.map((r, i) => ({
    category_id: r.categoryId || null,
    amount: `${sign}${parsed[i]}`,
  }));
  const splitChanged =
    splitting &&
    (parts.length !== wanted.length + 1 ||
      (parts.at(-1)?.category_id ?? null) !== (restCategory || null) ||
      wanted.some(
        (w, i) => w.category_id !== parts[i]?.category_id || w.amount !== parts[i]?.amount,
      ));

  const saveNote = async () => {
    if (!noteChanged) return;
    const { error, response } = await updateTransaction({
      path: { transaction_id: transaction.id },
      body: { note: note.trim() || null },
    });
    if (!response?.ok) throw fail(error, response);
  };
  // The split first: if it is refused, nothing has changed yet.
  const save = useMutation({
    mutationFn: async () => {
      if (splitChanged) {
        const { error, response } = await splitTransaction({
          path: { transaction_id: transaction.id },
          body: { parts: wanted, rest_category_id: restCategory || null },
        });
        if (!response?.ok) throw fail(error, response);
      }
      await saveNote();
    },
    onSettled: refresh,
    onSuccess: onDone,
  });
  const unsplit = useMutation({
    mutationFn: async () => {
      const { error, response } = await unsplitTransaction({
        path: { transaction_id: transaction.id },
      });
      if (!response?.ok) throw fail(error, response);
      await saveNote();
    },
    onSettled: refresh,
    onSuccess: onDone,
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const bad = splitting && (!given || restCents <= 0);
    setInvalid(bad);
    if (!bad) save.mutate();
  };
  const setRow = (index: number, change: Partial<Row>) =>
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, ...change } : r)));

  return (
    <form
      aria-label={t.transactions.details}
      onSubmit={submit}
      className="flex flex-col gap-4 rounded-lg border border-accent bg-surface p-4"
    >
      <div>
        <h2 className="text-lg font-bold">{t.transactions.details}</h2>
        <p className="text-sm">
          {t.transactions.linkSource(transaction.label, formatEur(transaction.amount))}
        </p>
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={ids.note} className="text-sm font-medium">
          {t.transactions.note}
        </label>
        <textarea
          id={ids.note}
          className={fieldClass}
          rows={2}
          maxLength={500}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <p className="text-xs text-muted">{t.transactions.noteHelp}</p>
      </div>
      {!canSplit && <p className="text-xs text-muted">{t.transactions.splitTransfer}</p>}
      {canSplit && !splitting && (
        <Button variant="ghost" className="self-start" onClick={() => setSplitting(true)}>
          {t.transactions.splitIt}
        </Button>
      )}
      {canSplit && splitting && (
        <fieldset className="flex flex-col gap-3">
          <legend className="text-sm font-medium">{t.transactions.split}</legend>
          <p className="text-xs text-muted">{t.transactions.splitHelp}</p>
          {rows.map((row, i) => {
            const n = i + 1;
            return (
              <div key={`${ids.part}-${n}`} className="flex flex-wrap items-end gap-3">
                <div className="flex flex-col gap-1">
                  <label htmlFor={`${ids.part}-c${n}`} className="text-sm">
                    {t.transactions.partCategory(n)}
                  </label>
                  <select
                    id={`${ids.part}-c${n}`}
                    className={fieldClass}
                    value={row.categoryId}
                    onChange={(e) => setRow(i, { categoryId: e.target.value })}
                  >
                    <option value="">{t.transactions.toCategorise}</option>
                    <CategoryOptions categories={categories} />
                  </select>
                </div>
                <TextField
                  label={t.transactions.partAmount(n)}
                  inputMode="decimal"
                  className="tabular w-32"
                  value={row.amount}
                  onChange={(e) => setRow(i, { amount: e.target.value })}
                />
                {rows.length > 1 && (
                  <Button
                    variant="ghost"
                    aria-label={t.transactions.removePart(n)}
                    onClick={() => setRows((prev) => prev.filter((_, j) => j !== i))}
                  >
                    <Icon name="close" className="size-4" />
                  </Button>
                )}
              </div>
            );
          })}
          {rows.length < MAX_GIVEN && (
            <Button
              variant="ghost"
              className="self-start"
              onClick={() => setRows((prev) => [...prev, { categoryId: "", amount: "" }])}
            >
              {t.transactions.addPart}
            </Button>
          )}
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <label htmlFor={ids.rest} className="text-sm">
                {t.transactions.restCategory}
              </label>
              <select
                id={ids.rest}
                className={fieldClass}
                value={restCategory}
                onChange={(e) => setRestCategory(e.target.value)}
              >
                <option value="">{t.transactions.toCategorise}</option>
                <CategoryOptions categories={categories} />
              </select>
            </div>
            <span className="tabular pb-2 text-sm">
              {t.transactions.rest(formatEur(fromCents(restCents)))}
            </span>
          </div>
        </fieldset>
      )}
      <ErrorAlert
        message={
          invalid
            ? t.transactions.splitInvalid
            : (save.error?.message ?? unsplit.error?.message ?? null)
        }
      />
      <div className="flex flex-wrap gap-3">
        <Button type="submit" disabled={save.isPending}>
          {t.common.save}
        </Button>
        {parts.length > 0 && (
          <Button variant="ghost" disabled={unsplit.isPending} onClick={() => unsplit.mutate()}>
            {t.transactions.removeSplit}
          </Button>
        )}
        <Button variant="ghost" onClick={onDone}>
          {t.common.cancel}
        </Button>
      </div>
    </form>
  );
}
