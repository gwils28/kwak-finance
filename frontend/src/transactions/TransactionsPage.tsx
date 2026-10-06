import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getRouteApi } from "@tanstack/react-router";
import { type FormEvent, useId, useState } from "react";
import {
  type AccountOut,
  type CategoryOut,
  categoriseTransactions,
  createTransaction,
  deleteTransaction,
  listAccounts,
  listTransactions,
  type TransactionOut,
  unlinkTransfer,
  updateTransaction,
} from "../api/generated";
import { apiErrorMessage, detailSentence } from "../auth/errors";
import { Button, ErrorAlert, TextField } from "../components/ui";
import { useI18n } from "../i18n";
import { formatDate, todayIso } from "../lib/dates";
import { amountInput, formatEur, parseEurInput } from "../lib/money";
import { CategoryOptions, categoriesQuery } from "./categories";
import { RuleForm } from "./RuleForm";
import { afterTransferChange, TransferBanner } from "./TransferBanner";

export const PAGE_SIZE = 50;

export type TransactionSearch = {
  account?: string;
  from?: string;
  to?: string;
  q?: string;
  /** A category id, or "none" for transactions to categorise. */
  category?: string;
  page?: number;
};

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** Search params of /transactions, validated: anything malformed is dropped. */
export function parseTransactionSearch(search: Record<string, unknown>): TransactionSearch {
  const text = (v: unknown) => (typeof v === "string" && v.trim() ? v.trim() : undefined);
  const day = (v: unknown) => (typeof v === "string" && ISO_DATE.test(v) ? v : undefined);
  const page = Number(search.page);
  return {
    account: text(search.account),
    from: day(search.from),
    to: day(search.to),
    q: text(search.q),
    category: text(search.category),
    page: Number.isInteger(page) && page > 1 ? page : undefined,
  };
}

const route = getRouteApi("/app/transactions");
const CASH = new Set(["checking", "savings"]);
const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";

export function TransactionsPage() {
  const { t } = useI18n();
  const search = route.useSearch();
  const navigate = route.useNavigate();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<TransactionOut | null>(null);
  const [ruleFrom, setRuleFrom] = useState<TransactionOut | null>(null);
  const [notice, setNotice] = useState("");
  const categories = useQuery(categoriesQuery);
  const accounts = useQuery({
    queryKey: ["accounts", { includeClosed: true }],
    queryFn: async () =>
      (await listAccounts({ query: { include_closed: true }, throwOnError: true })).data,
  });
  const page = search.page ?? 1;
  const transactions = useQuery({
    queryKey: ["transactions", search],
    queryFn: async () =>
      (
        await listTransactions({
          query: {
            account_id: search.account,
            date_from: search.from,
            date_to: search.to,
            q: search.q,
            category_id: search.category === "none" ? undefined : search.category,
            uncategorised: search.category === "none" ? true : undefined,
            limit: PAGE_SIZE,
            offset: (page - 1) * PAGE_SIZE,
          },
          throwOnError: true,
        })
      ).data,
    placeholderData: keepPreviousData,
  });
  const toCategorise = useQuery({
    queryKey: ["toCategorise"],
    queryFn: async () =>
      (await listTransactions({ query: { uncategorised: true, limit: 1 }, throwOnError: true }))
        .data.total,
  });

  const setFilter = (changes: Partial<TransactionSearch>) =>
    navigate({ search: (prev) => ({ ...prev, ...changes, page: undefined }) });

  const total = transactions.data?.total ?? 0;
  const first = (page - 1) * PAGE_SIZE + 1;
  const last = Math.min(page * PAGE_SIZE, total);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-baseline gap-4">
          <h1 className="text-3xl font-black tracking-tight">{t.transactions.title}</h1>
          {Boolean(toCategorise.data) && (
            <Button variant="ghost" onClick={() => setFilter({ category: "none" })}>
              {t.transactions.toCategoriseCount(toCategorise.data ?? 0)}
            </Button>
          )}
        </div>
        <Button
          onClick={() => {
            setEditing(null);
            setAdding(true);
          }}
        >
          {t.transactions.add}
        </Button>
      </div>
      {(adding || editing) && accounts.data && (
        <TransactionForm
          key={editing?.id ?? "new"}
          transaction={editing}
          accounts={accounts.data.filter((a) => CASH.has(a.type) && !a.closed_on)}
          onDone={() => {
            setAdding(false);
            setEditing(null);
          }}
        />
      )}
      <TransferBanner onNotice={setNotice} />
      {ruleFrom && categories.data && (
        <RuleForm
          key={ruleFrom.id}
          transaction={ruleFrom}
          categories={categories.data}
          onDone={(message) => {
            setRuleFrom(null);
            setNotice(message);
          }}
        />
      )}
      {notice && (
        <p className="rounded-md border border-accent px-3 py-2 text-sm" aria-live="polite">
          {notice}
        </p>
      )}
      <Filters
        search={search}
        accounts={accounts.data ?? []}
        categories={categories.data ?? []}
        onChange={setFilter}
      />
      {transactions.isError && <ErrorAlert message={t.transactions.loadFailed} />}
      {transactions.data && transactions.data.total === 0 && (
        <p className="text-muted">{t.transactions.noMatch}</p>
      )}
      {transactions.data && transactions.data.total > 0 && (
        <>
          <p className="text-sm text-muted">
            {total <= PAGE_SIZE
              ? t.transactions.count(total)
              : t.transactions.range(first, last, total)}
          </p>
          <TransactionTable
            items={transactions.data.items}
            categories={categories.data ?? []}
            onNotice={setNotice}
            onRule={setRuleFrom}
            onEdit={(tx) => {
              setAdding(false);
              setEditing(tx);
            }}
          />
          {total > PAGE_SIZE && (
            <div className="flex gap-3">
              <Button
                variant="ghost"
                disabled={page === 1}
                onClick={() => navigate({ search: (prev) => ({ ...prev, page: page - 1 }) })}
              >
                {t.transactions.previous}
              </Button>
              <Button
                variant="ghost"
                disabled={last >= total}
                onClick={() => navigate({ search: (prev) => ({ ...prev, page: page + 1 }) })}
              >
                {t.transactions.next}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Filters({
  search,
  accounts,
  categories,
  onChange,
}: {
  search: TransactionSearch;
  accounts: AccountOut[];
  categories: CategoryOut[];
  onChange: (changes: Partial<TransactionSearch>) => void;
}) {
  const { t } = useI18n();
  const [text, setText] = useState(search.q ?? "");
  const ids = { account: useId(), from: useId(), to: useId(), q: useId() };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onChange({ q: text.trim() || undefined });
  };
  return (
    <form
      onSubmit={submit}
      className="grid gap-3 rounded-lg border border-border bg-surface p-4 sm:grid-cols-2 lg:grid-cols-5"
    >
      <div className="flex flex-col gap-1">
        <label htmlFor={ids.account} className="text-sm font-medium">
          {t.transactions.account}
        </label>
        <select
          id={ids.account}
          className={fieldClass}
          value={search.account ?? ""}
          onChange={(e) => onChange({ account: e.target.value || undefined })}
        >
          <option value="">{t.transactions.allAccounts}</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} ({a.institution})
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="category-filter" className="text-sm font-medium">
          {t.transactions.category}
        </label>
        <select
          id="category-filter"
          className={fieldClass}
          value={search.category ?? ""}
          onChange={(e) => onChange({ category: e.target.value || undefined })}
        >
          <option value="">{t.transactions.allCategories}</option>
          <option value="none">{t.transactions.toCategorise}</option>
          <CategoryOptions categories={categories} />
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={ids.from} className="text-sm font-medium">
          {t.transactions.from}
        </label>
        <input
          id={ids.from}
          type="date"
          className={fieldClass}
          value={search.from ?? ""}
          onChange={(e) => onChange({ from: e.target.value || undefined })}
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={ids.to} className="text-sm font-medium">
          {t.transactions.to}
        </label>
        <input
          id={ids.to}
          type="date"
          className={fieldClass}
          value={search.to ?? ""}
          onChange={(e) => onChange({ to: e.target.value || undefined })}
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={ids.q} className="text-sm font-medium">
          {t.transactions.search}
        </label>
        <input
          id={ids.q}
          type="search"
          placeholder={t.transactions.searchPlaceholder}
          className={fieldClass}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            // Emptying the field (e.g. its clear button) drops the filter without Enter.
            if (e.target.value === "") onChange({ q: undefined });
          }}
        />
      </div>
      {/* Enter only submits a form with several fields when it has a submit button. */}
      <button type="submit" className="sr-only">
        {t.transactions.applyFilters}
      </button>
    </form>
  );
}

function TransactionTable({
  items,
  categories,
  onEdit,
  onRule,
  onNotice,
}: {
  items: TransactionOut[];
  categories: CategoryOut[];
  onEdit: (tx: TransactionOut) => void;
  onRule: (tx: TransactionOut) => void;
  onNotice: (message: string) => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkCategory, setBulkCategory] = useState("");
  const bulkSelect = useId();

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["transactions"] });
    await queryClient.invalidateQueries({ queryKey: ["toCategorise"] });
  };
  const remove = useMutation({
    mutationFn: async (id: string) =>
      deleteTransaction({ path: { transaction_id: id }, throwOnError: true }),
    onSuccess: async () => {
      setConfirming(null);
      await refresh();
      await queryClient.invalidateQueries({ queryKey: ["accounts"] });
    },
  });
  const setCategory = useMutation({
    mutationFn: async ({ id, categoryId }: { id: string; categoryId: string | null }) =>
      updateTransaction({
        path: { transaction_id: id },
        body: { category_id: categoryId },
        throwOnError: true,
      }),
    onSuccess: refresh,
  });
  const unlink = useMutation({
    mutationFn: async (groupId: string) =>
      unlinkTransfer({ path: { group_id: groupId }, throwOnError: true }),
    onSuccess: () => afterTransferChange(queryClient),
  });
  const bulk = useMutation({
    mutationFn: async () =>
      (
        await categoriseTransactions({
          body: { transaction_ids: [...selected], category_id: bulkCategory || null },
          throwOnError: true,
        })
      ).data.updated,
    onSuccess: async (updated) => {
      setSelected(new Set());
      onNotice(t.transactions.categorised(updated));
      await refresh();
    },
  });

  const allSelected = items.length > 0 && items.every((tx) => selected.has(tx.id));
  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (!next.delete(id)) next.add(id);
      return next;
    });

  return (
    <div className="flex flex-col gap-3">
      {selected.size > 0 && (
        <section
          aria-label={t.transactions.selected(selected.size)}
          className="flex flex-wrap items-center gap-3 rounded-lg border border-accent bg-surface px-4 py-3"
        >
          <span className="text-sm font-medium">{t.transactions.selected(selected.size)}</span>
          <label htmlFor={bulkSelect} className="sr-only">
            {t.transactions.selectionCategory}
          </label>
          <select
            id={bulkSelect}
            className={fieldClass}
            value={bulkCategory}
            onChange={(e) => setBulkCategory(e.target.value)}
          >
            <option value="">{t.transactions.toCategorise}</option>
            <CategoryOptions categories={categories} />
          </select>
          <Button disabled={bulk.isPending} onClick={() => bulk.mutate()}>
            {t.common.apply}
          </Button>
          <Button variant="ghost" onClick={() => setSelected(new Set())}>
            {t.common.clear}
          </Button>
        </section>
      )}
      <div className="overflow-x-auto rounded-lg border border-border bg-surface">
        <table aria-label={t.transactions.title} className="w-full text-sm">
          <thead className="text-left text-muted">
            <tr>
              <th className="px-3 py-2">
                <input
                  type="checkbox"
                  aria-label={t.transactions.selectAll}
                  checked={allSelected}
                  onChange={() =>
                    setSelected(allSelected ? new Set() : new Set(items.map((tx) => tx.id)))
                  }
                />
              </th>
              <th className="px-3 py-2 font-medium">{t.transactions.date}</th>
              <th className="px-3 py-2 font-medium">{t.transactions.label}</th>
              <th className="px-3 py-2 font-medium">{t.transactions.category}</th>
              <th className="px-3 py-2 font-medium">{t.transactions.account}</th>
              <th className="px-3 py-2 text-right font-medium">{t.transactions.amount}</th>
              <th className="px-3 py-2">
                <span className="sr-only">{t.transactions.actions}</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((tx) => (
              <tr key={tx.id} className={selected.has(tx.id) ? "bg-bg" : ""}>
                <td className="px-3 py-2">
                  <input
                    type="checkbox"
                    aria-label={t.transactions.select(tx.label)}
                    checked={selected.has(tx.id)}
                    onChange={() => toggle(tx.id)}
                  />
                </td>
                <td className="whitespace-nowrap px-3 py-2">{formatDate(tx.booked_on)}</td>
                <td className="px-3 py-2">{tx.label}</td>
                <td className="px-3 py-2">
                  {tx.transfer_group_id ? (
                    <span className="flex items-center gap-2">
                      <span className="whitespace-nowrap rounded-md bg-bg px-2 py-1 text-xs">
                        {(tx.amount.startsWith("-")
                          ? t.transactions.transferTo
                          : t.transactions.transferFrom)(tx.transfer_account_name ?? "")}
                      </span>
                      <Button
                        variant="ghost"
                        aria-label={t.transactions.unlinkNamed(tx.label)}
                        disabled={unlink.isPending}
                        onClick={() => tx.transfer_group_id && unlink.mutate(tx.transfer_group_id)}
                      >
                        {t.transactions.unlink}
                      </Button>
                    </span>
                  ) : (
                    <select
                      aria-label={t.transactions.categoryOf(tx.label)}
                      className={`max-w-48 rounded-md border bg-surface px-2 py-1 ${
                        tx.category_id ? "border-border" : "border-warning"
                      }`}
                      value={tx.category_id ?? ""}
                      onChange={(e) =>
                        setCategory.mutate({ id: tx.id, categoryId: e.target.value || null })
                      }
                    >
                      <option value="">{t.transactions.toCategorise}</option>
                      <CategoryOptions categories={categories} />
                    </select>
                  )}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-muted">{tx.account_name}</td>
                <td
                  className={`tabular whitespace-nowrap px-3 py-2 text-right ${
                    tx.amount.startsWith("-") ? "" : "text-positive"
                  }`}
                >
                  {formatEur(tx.amount)}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-right">
                  <span className="flex items-center justify-end gap-2">
                    <Button
                      variant="ghost"
                      aria-label={t.transactions.ruleFrom(tx.label)}
                      onClick={() => onRule(tx)}
                    >
                      {t.transactions.rule}
                    </Button>
                    {tx.source === "import" ? (
                      <span className="text-xs text-muted">{t.transactions.imported}</span>
                    ) : confirming === tx.id ? (
                      <>
                        <Button
                          variant="ghost"
                          className="border-negative text-negative"
                          disabled={remove.isPending}
                          onClick={() => remove.mutate(tx.id)}
                        >
                          {t.transactions.confirmDelete}
                        </Button>
                        <Button variant="ghost" onClick={() => setConfirming(null)}>
                          {t.common.cancel}
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button
                          variant="ghost"
                          aria-label={t.transactions.editNamed(tx.label)}
                          onClick={() => onEdit(tx)}
                        >
                          {t.common.edit}
                        </Button>
                        <Button
                          variant="ghost"
                          aria-label={t.transactions.deleteNamed(tx.label)}
                          onClick={() => setConfirming(tx.id)}
                        >
                          {t.common.delete}
                        </Button>
                      </>
                    )}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TransactionForm({
  transaction,
  accounts,
  onDone,
}: {
  transaction: TransactionOut | null;
  accounts: AccountOut[];
  onDone: () => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const isIncome = transaction ? !transaction.amount.startsWith("-") : false;
  const [accountId, setAccountId] = useState(transaction?.account_id ?? accounts[0]?.id ?? "");
  const [bookedOn, setBookedOn] = useState(transaction?.booked_on ?? todayIso());
  const [kind, setKind] = useState<"expense" | "income">(isIncome ? "income" : "expense");
  const [amount, setAmount] = useState(
    transaction ? amountInput(transaction.amount.replace("-", "")) : "",
  );
  const [label, setLabel] = useState(transaction?.label ?? "");
  const [invalid, setInvalid] = useState(false);
  const ids = { account: useId(), kind: useId() };

  const save = useMutation({
    mutationFn: async (signed: string) => {
      const fields = { booked_on: bookedOn, amount: signed, label };
      const { data, error, response } = transaction
        ? await updateTransaction({ path: { transaction_id: transaction.id }, body: fields })
        : await createTransaction({ body: { account_id: accountId, ...fields } });
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
