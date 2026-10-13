import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import {
  type AccountOut,
  createTransaction,
  type TransactionOut,
  updateTransaction,
} from "../api/generated";
import { apiErrorMessage, detailSentence } from "../auth/errors";
import { Button, ErrorAlert, TextField } from "../components/ui";
import { useI18n } from "../i18n";
import { todayIso } from "../lib/dates";
import { amountInput, parseEurInput } from "../lib/money";
import { CategoryOptions, categoriesQuery } from "./categories";

const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";

/** A new entry pre-filled by "Enter it" on a recurring item's occurrence (F-REC-3). */
export type EntryDraft = {
  account_id: string;
  booked_on: string;
  /** Signed, as the API's: "-950.00". */
  amount: string;
  label: string;
  category_id: string | null;
};

/** Enters a transaction by hand (or edits one): from scratch, or from a draft to confirm. */
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
  const [bookedOn, setBookedOn] = useState(source?.booked_on ?? todayIso());
  const [kind, setKind] = useState<"expense" | "income">(isIncome ? "income" : "expense");
  const [amount, setAmount] = useState(source ? amountInput(source.amount.replace("-", "")) : "");
  const [label, setLabel] = useState(source?.label ?? "");
  const [categoryId, setCategoryId] = useState(draft?.category_id ?? "");
  const [invalid, setInvalid] = useState(false);
  const ids = { account: useId(), kind: useId(), category: useId() };

  const save = useMutation({
    mutationFn: async (signed: string) => {
      const fields = { booked_on: bookedOn, amount: signed, label };
      const { data, error, response } = transaction
        ? await updateTransaction({ path: { transaction_id: transaction.id }, body: fields })
        : await createTransaction({
            body: { account_id: accountId, category_id: categoryId || null, ...fields },
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
      await queryClient.invalidateQueries({ queryKey: ["transactions"] });
      await queryClient.invalidateQueries({ queryKey: ["accounts"] });
      await queryClient.invalidateQueries({ queryKey: ["recurring"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      onDone();
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const parsed = parseEurInput(amount);
    const ok = parsed !== null && !parsed.startsWith("-") && parsed !== "0.00";
    setInvalid(!ok);
    if (ok) save.mutate(kind === "expense" ? `-${parsed}` : parsed);
  };

  const title = transaction ? t.transactions.editTitle : t.transactions.newTitle;
  return (
    <form
      aria-label={title}
      onSubmit={submit}
      className="grid gap-4 rounded-lg border border-accent bg-surface p-4 sm:grid-cols-2"
    >
      <h2 className="text-lg font-bold sm:col-span-2">{title}</h2>
      {transaction ? (
        <p className="text-sm sm:col-span-2">
          {t.transactions.accountLine(transaction.account_name)}
        </p>
      ) : (
        <div className="flex flex-col gap-1">
          <label htmlFor={ids.account} className="text-sm font-medium">
            {t.transactions.account}
          </label>
          <select
            id={ids.account}
            className={fieldClass}
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
          >
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({a.institution})
              </option>
            ))}
          </select>
        </div>
      )}
      <TextField
        label={t.transactions.date}
        type="date"
        required
        value={bookedOn}
        onChange={(e) => setBookedOn(e.target.value)}
      />
      <fieldset className="flex items-center gap-4">
        <legend className="sr-only">{t.transactions.direction}</legend>
        {(["expense", "income"] as const).map((value) => (
          <label key={value} className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name={ids.kind}
              value={value}
              checked={kind === value}
              onChange={() => setKind(value)}
            />
            {value === "expense" ? t.transactions.expense : t.transactions.income}
          </label>
        ))}
      </fieldset>
      <TextField
        label={t.transactions.amountEur}
        inputMode="decimal"
        required
        className="tabular"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
      />
      <div className="sm:col-span-2">
        <TextField
          label={t.transactions.label}
          required
          maxLength={200}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
        />
      </div>
      {!transaction && (
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
        <ErrorAlert
          message={invalid ? t.transactions.invalidAmount : (save.error?.message ?? null)}
        />
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
