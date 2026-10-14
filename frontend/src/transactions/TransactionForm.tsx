import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import {
  type AccountOut,
  createTransaction,
  enterTransfer,
  type TransactionOut,
  updateTransaction,
} from "../api/generated";
import { apiErrorMessage, detailSentence } from "../auth/errors";
import { Button, ErrorAlert, TextField } from "../components/ui";
import { useI18n } from "../i18n";
import { todayIso } from "../lib/dates";
import { amountInput, parseEurInput } from "../lib/money";
import { CategoryOptions, categoriesQuery } from "./categories";
import { afterTransferChange } from "./TransferBanner";

const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";

/** A new entry pre-filled by "Enter it" on a recurring item's occurrence (F-REC-3). */
export type EntryDraft = {
  account_id: string;
  booked_on: string;
  /** Signed, as the API's: "-950.00". */
  amount: string;
  label: string;
  category_id: string | null;
  /** Set for a transfer item: the entry is then a transfer to this account (F-TX-9). */
  destination_account_id?: string | null;
};

type Kind = "expense" | "income" | "transfer";

/** Enters a transaction or a transfer by hand (or edits one): from scratch, or from a draft
 * to confirm. */
export function TransactionForm({
  transaction = null,
  draft = null,
  accounts,
  onDone,
}: {
  transaction?: TransactionOut | null;
  draft?: EntryDraft | null;
  accounts: AccountOut[];
  onDone: () => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const categories = useQuery(categoriesQuery);
  const source = transaction ?? draft;
  const isIncome = source ? !source.amount.startsWith("-") : false;
  const [accountId, setAccountId] = useState(source?.account_id ?? accounts[0]?.id ?? "");
  // A recurring transfer may point to an account closed since: offer an open one instead.
  const [destinationId, setDestinationId] = useState(
    accounts.find((a) => a.id === draft?.destination_account_id)?.id ??
      accounts.find((a) => a.id !== accountId)?.id ??
      "",
  );
  const [bookedOn, setBookedOn] = useState(source?.booked_on ?? todayIso());
  const [kind, setKind] = useState<Kind>(
    draft?.destination_account_id ? "transfer" : isIncome ? "income" : "expense",
  );
  const [amount, setAmount] = useState(source ? amountInput(source.amount.replace("-", "")) : "");
  const [label, setLabel] = useState(source?.label ?? "");
  const [categoryId, setCategoryId] = useState(draft?.category_id ?? "");
  const [note, setNote] = useState(transaction?.note ?? "");
  const [invalid, setInvalid] = useState<string | null>(null);
  const ids = {
    account: useId(),
    destination: useId(),
    kind: useId(),
    category: useId(),
    note: useId(),
  };
  const transfer = kind === "transfer";
  // A side of a transfer keeps its direction: the other side mirrors it (F-TX-9).
  const kinds: Kind[] = transaction?.transfer_group_id
    ? []
    : transaction || accounts.length < 2
      ? ["expense", "income"]
      : ["expense", "income", "transfer"];
  const name = (id: string) => accounts.find((a) => a.id === id)?.name ?? "";

  const save = useMutation({
    mutationFn: async (parsed: string) => {
      const fields = { booked_on: bookedOn, label };
      // Only sent when it changes, so an edit stays a plain edit.
      const noteChange =
        note.trim() !== (transaction?.note ?? "") ? { note: note.trim() || null } : {};
      const { data, error, response } = transfer
        ? await enterTransfer({
            body: {
              source_account_id: accountId,
              destination_account_id: destinationId,
              booked_on: bookedOn,
              amount: parsed,
              outflow_label: label.trim() || t.transactions.transferTo(name(destinationId)),
              inflow_label: label.trim() || t.transactions.transferFrom(name(accountId)),
            },
          })
        : transaction
          ? await updateTransaction({
              path: { transaction_id: transaction.id },
              body: {
                ...fields,
                ...noteChange,
                amount: kind === "income" ? parsed : `-${parsed}`,
              },
            })
          : await createTransaction({
              body: {
                account_id: accountId,
                category_id: categoryId || null,
                amount: kind === "income" ? parsed : `-${parsed}`,
                ...fields,
                ...noteChange,
              },
            });
      if (!data) {
        throw new Error(
          response?.status === 422 || response?.status === 409
            ? (detailSentence(error) ?? t.errors.checkForm)
            : apiErrorMessage(t, response),
        );
      }
      return data;
    },
    onSuccess: async () => {
      await afterTransferChange(queryClient);
      await queryClient.invalidateQueries({ queryKey: ["accounts"] });
      await queryClient.invalidateQueries({ queryKey: ["recurring"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      onDone();
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const parsed = parseEurInput(amount);
    const problem =
      parsed === null || parsed.startsWith("-") || parsed === "0.00"
        ? t.transactions.invalidAmount
        : transfer && accountId === destinationId
          ? t.transactions.sameAccounts
          : null;
    setInvalid(problem);
    if (!problem && parsed) save.mutate(parsed);
  };

  const accountSelect = (id: string, value: string, onChange: (value: string) => void) => (
    <select id={id} className={fieldClass} value={value} onChange={(e) => onChange(e.target.value)}>
      {accounts.map((a) => (
        <option key={a.id} value={a.id}>
          {a.name} ({a.institution})
        </option>
      ))}
    </select>
  );

  const title = transaction ? t.transactions.editTitle : t.transactions.newTitle;
  return (
    <form
      aria-label={title}
      onSubmit={submit}
      className="grid gap-4 rounded-lg border border-accent bg-surface p-4 sm:grid-cols-2"
    >
      <h2 className="text-lg font-bold sm:col-span-2">{title}</h2>
      {kinds.length > 0 && (
        <fieldset className="flex items-center gap-4 sm:col-span-2">
          <legend className="sr-only">{t.transactions.direction}</legend>
          {kinds.map((value) => (
            <label key={value} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name={ids.kind}
                value={value}
                checked={kind === value}
                onChange={() => setKind(value)}
              />
              {t.transactions[value]}
            </label>
          ))}
        </fieldset>
      )}
      {transaction ? (
        <p className="text-sm sm:col-span-2">
          {t.transactions.accountLine(transaction.account_name)}
          {transaction.transfer_group_id && (
            <span className="block text-muted">
              {t.transactions.transferSide(
                (isIncome ? t.transactions.transferFrom : t.transactions.transferTo)(
                  transaction.transfer_account_name ?? "",
                ),
              )}
            </span>
          )}
        </p>
      ) : (
        <>
          <div className="flex flex-col gap-1">
            <label htmlFor={ids.account} className="text-sm font-medium">
              {transfer ? t.transactions.fromAccount : t.transactions.account}
            </label>
            {accountSelect(ids.account, accountId, setAccountId)}
          </div>
          {transfer && (
            <div className="flex flex-col gap-1">
              <label htmlFor={ids.destination} className="text-sm font-medium">
                {t.transactions.toAccount}
              </label>
              {accountSelect(ids.destination, destinationId, setDestinationId)}
            </div>
          )}
        </>
      )}
      <TextField
        label={t.transactions.date}
        type="date"
        required
        value={bookedOn}
        onChange={(e) => setBookedOn(e.target.value)}
      />
      <TextField
        label={t.transactions.amountEur}
        inputMode="decimal"
        required
        className="tabular"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
      />
      <div className="flex flex-col gap-1 sm:col-span-2">
        <TextField
          label={transfer ? t.transactions.labelOptional : t.transactions.label}
          required={!transfer}
          maxLength={200}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
        />
        {transfer && <p className="text-xs text-muted">{t.transactions.transferLabelHelp}</p>}
      </div>
      {!transfer && (
        <div className="flex flex-col gap-1 sm:col-span-2">
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
        </div>
      )}
      {!transaction && !transfer && (
        <div className="flex flex-col gap-1 sm:col-span-2">
          <label htmlFor={ids.category} className="text-sm font-medium">
            {t.transactions.category}
          </label>
          <select
            id={ids.category}
            className={fieldClass}
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
          >
            <option value="">{t.transactions.categoryByRules}</option>
            <CategoryOptions categories={categories.data ?? []} />
          </select>
        </div>
      )}
      <div className="sm:col-span-2">
        <ErrorAlert message={invalid ?? save.error?.message ?? null} />
      </div>
      <div className="flex gap-3 sm:col-span-2">
        <Button type="submit" disabled={save.isPending}>
          {t.common.save}
        </Button>
        <Button variant="ghost" onClick={onDone}>
          {t.common.cancel}
        </Button>
      </div>
    </form>
  );
}
