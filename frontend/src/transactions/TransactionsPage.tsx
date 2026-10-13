import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getRouteApi, Link } from "@tanstack/react-router";
import { type FormEvent, useId, useState } from "react";
import {
  type AccountOut,
  type CategoryOut,
  categoriseTransactions,
  deleteTransaction,
  listAccounts,
  listTransactions,
  type TransactionOut,
  unlinkTransfer,
  updateTransaction,
} from "../api/generated";
import { Icon } from "../components/icons";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { formatDate } from "../lib/dates";
import { formatEur } from "../lib/money";
import { monthLabel, shiftMonth } from "../lib/months";
import { CategoryOptions, categoriesQuery } from "./categories";
import { RuleForm } from "./RuleForm";
import { TransactionForm } from "./TransactionForm";
import { afterTransferChange, TransferBanner } from "./TransferBanner";

export const PAGE_SIZE = 50;

export type TransactionSearch = {
  account?: string;
  from?: string;
  to?: string;
  q?: string;
  /** A category id, or "none" for transactions to categorise. */
  category?: string;
  /** "2026-04": the transactions counted in that budget month (F-TX-7). */
  month?: string;
  page?: number;
};

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const ISO_MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;

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
    month:
      typeof search.month === "string" && ISO_MONTH.test(search.month) ? search.month : undefined,
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
            budget_month: search.month,
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
        <div className="flex flex-wrap items-center gap-3">
          <Link
            to="/recurring"
            className="rounded-md border border-border bg-surface px-3 py-2 text-sm hover:border-accent"
          >
            {t.recurring.open}
          </Link>
          <Button
            onClick={() => {
              setEditing(null);
              setAdding(true);
            }}
          >
            {t.transactions.add}
          </Button>
        </div>
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
  const ids = { account: useId(), from: useId(), to: useId(), q: useId(), month: useId() };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onChange({ q: text.trim() || undefined });
  };
  return (
    <form
      onSubmit={submit}
      className="grid gap-3 rounded-lg border border-border bg-surface p-4 sm:grid-cols-3 lg:grid-cols-6"
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
        <label htmlFor={ids.month} className="text-sm font-medium" title={t.transactions.monthHelp}>
          {t.transactions.budgetMonth}
        </label>
        <input
          id={ids.month}
          type="month"
          className={fieldClass}
          value={search.month ?? ""}
          onChange={(e) => onChange({ month: e.target.value || undefined })}
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
  const [choosingMonth, setChoosingMonth] = useState<string | null>(null);
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
  const setMonth = useMutation({
    mutationFn: async ({ id, month }: { id: string; month: string | null }) =>
      updateTransaction({
        path: { transaction_id: id },
        body: { budget_month: month },
        throwOnError: true,
      }),
    onSuccess: async () => {
      setChoosingMonth(null);
      await refresh();
      await queryClient.invalidateQueries({ queryKey: ["budget"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
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
              <tr key={tx.id} className={`group ${selected.has(tx.id) ? "bg-bg" : ""}`}>
                <td className="px-3 py-2">
                  <input
                    type="checkbox"
                    aria-label={t.transactions.select(tx.label)}
                    checked={selected.has(tx.id)}
                    onChange={() => toggle(tx.id)}
                  />
                </td>
                <td className="whitespace-nowrap px-3 py-2">
                  {formatDate(tx.booked_on)}
                  {!tx.transfer_group_id && (
                    <MonthToggle
                      tx={tx}
                      open={choosingMonth === tx.id}
                      onClick={() => setChoosingMonth(choosingMonth === tx.id ? null : tx.id)}
                    />
                  )}
                  {choosingMonth === tx.id && (
                    <MonthSelect
                      tx={tx}
                      disabled={setMonth.isPending}
                      onChange={(month) => setMonth.mutate({ id: tx.id, month })}
                    />
                  )}
                </td>
                <td className="px-3 py-2" title={tx.bank_label ?? undefined}>
                  {tx.label}
                </td>
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

/** Opens the month choice from the date cell: the "counted in" note when the transaction counts
 * in another month, else a calendar icon shown on row hover (always on touch screens). */
function MonthToggle({
  tx,
  open,
  onClick,
}: {
  tx: TransactionOut;
  open: boolean;
  onClick: () => void;
}) {
  const { t } = useI18n();
  const moved = Boolean(tx.budget_month) && tx.budget_month !== tx.booked_on.slice(0, 7);
  const focus =
    "rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";
  return (
    <button
      type="button"
      aria-label={t.transactions.budgetMonthOf(tx.label)}
      aria-expanded={open}
      title={t.transactions.monthHelp}
      onClick={onClick}
      className={
        moved
          ? `block text-xs text-muted underline-offset-2 hover:text-accent hover:underline ${focus}`
          : `ml-1 inline-block align-middle text-muted opacity-0 hover:text-accent focus-visible:opacity-100 group-hover:opacity-100 pointer-coarse:opacity-100 ${open ? "opacity-100" : ""} ${focus}`
      }
    >
      {moved ? (
        t.transactions.countedIn(monthLabel(tx.budget_month))
      ) : (
        <Icon name="calendar" className="size-3.5" />
      )}
    </button>
  );
}

/** The month a transaction counts in: automatic (its category's rule), or set by hand to its
 * date's month, the one before or the one after (F-TX-7). */
function MonthSelect({
  tx,
  disabled,
  onChange,
}: {
  tx: TransactionOut;
  disabled: boolean;
  onChange: (month: string | null) => void;
}) {
  const { t } = useI18n();
  const own = tx.booked_on.slice(0, 7);
  return (
    <select
      aria-label={t.transactions.countsIn(tx.label)}
      className="mt-1 block rounded-md border border-border bg-surface px-1 py-0.5 text-xs"
      disabled={disabled}
      value={tx.budget_month_set ? tx.budget_month : ""}
      onChange={(e) => onChange(e.target.value || null)}
    >
      <option value="">
        {t.transactions.automatic(tx.budget_month_set ? null : monthLabel(tx.budget_month))}
      </option>
      {[-1, 0, 1].map((delta) => {
        const month = shiftMonth(own, delta);
        return (
          <option key={month} value={month}>
            {monthLabel(month)}
          </option>
        );
      })}
    </select>
  );
}
