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
  updateTransaction,
} from "../api/generated";
import { apiErrorMessage, detailSentence } from "../auth/errors";
import { Button, ErrorAlert, TextField } from "../components/ui";
import { formatDate, todayIso } from "../lib/dates";
import { formatEur, parseEurInput } from "../lib/money";
import { CategoryOptions, categoriesQuery } from "./categories";
import { RuleForm } from "./RuleForm";

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
          <h1 className="text-3xl font-black tracking-tight">Transactions</h1>
          {Boolean(toCategorise.data) && (
            <Button variant="ghost" onClick={() => setFilter({ category: "none" })}>
              {toCategorise.data} to categorise
            </Button>
          )}
        </div>
        <Button
          onClick={() => {
            setEditing(null);
            setAdding(true);
          }}
        >
          Add a transaction
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
      {transactions.isError && <ErrorAlert message="Could not load the transactions." />}
      {transactions.data && transactions.data.total === 0 && (
        <p className="text-muted">No transactions match these filters.</p>
      )}
      {transactions.data && transactions.data.total > 0 && (
        <>
          <p className="text-sm text-muted">
            {total <= PAGE_SIZE
              ? `${total} transaction${total === 1 ? "" : "s"}`
              : `${first}–${last} of ${total}`}
          </p>
          <TransactionTable
            items={transactions.data.items}
            categories={categories.data ?? []}
            onNotice={setNotice}
            onRule={setRuleFrom}
            onEdit={(t) => {
              setAdding(false);
              setEditing(t);
            }}
          />
          {total > PAGE_SIZE && (
            <div className="flex gap-3">
              <Button
                variant="ghost"
                disabled={page === 1}
                onClick={() => navigate({ search: (prev) => ({ ...prev, page: page - 1 }) })}
              >
                Previous
              </Button>
              <Button
                variant="ghost"
                disabled={last >= total}
                onClick={() => navigate({ search: (prev) => ({ ...prev, page: page + 1 }) })}
              >
                Next
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
          Account
        </label>
        <select
          id={ids.account}
          className={fieldClass}
          value={search.account ?? ""}
          onChange={(e) => onChange({ account: e.target.value || undefined })}
        >
          <option value="">All accounts</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} ({a.institution})
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="category-filter" className="text-sm font-medium">
          Category
        </label>
        <select
          id="category-filter"
          className={fieldClass}
          value={search.category ?? ""}
          onChange={(e) => onChange({ category: e.target.value || undefined })}
        >
          <option value="">All categories</option>
          <option value="none">To categorise</option>
          <CategoryOptions categories={categories} />
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={ids.from} className="text-sm font-medium">
          From
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
          To
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
          Search
        </label>
        <input
          id={ids.q}
          type="search"
          placeholder="Label, then Enter"
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
        Apply filters
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
  onEdit: (t: TransactionOut) => void;
  onRule: (t: TransactionOut) => void;
  onNotice: (message: string) => void;
}) {
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
      onNotice(`${updated} transaction${updated === 1 ? "" : "s"} categorised.`);
      await refresh();
    },
  });

  const allSelected = items.length > 0 && items.every((t) => selected.has(t.id));
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
          aria-label={`${selected.size} selected`}
          className="flex flex-wrap items-center gap-3 rounded-lg border border-accent bg-surface px-4 py-3"
        >
          <span className="text-sm font-medium">{selected.size} selected</span>
          <label htmlFor={bulkSelect} className="sr-only">
            Category for the selection
          </label>
          <select
            id={bulkSelect}
            className={fieldClass}
            value={bulkCategory}
            onChange={(e) => setBulkCategory(e.target.value)}
          >
            <option value="">To categorise</option>
            <CategoryOptions categories={categories} />
          </select>
          <Button disabled={bulk.isPending} onClick={() => bulk.mutate()}>
            Apply
          </Button>
          <Button variant="ghost" onClick={() => setSelected(new Set())}>
            Clear
          </Button>
        </section>
      )}
      <div className="overflow-x-auto rounded-lg border border-border bg-surface">
        <table aria-label="Transactions" className="w-full text-sm">
          <thead className="text-left text-muted">
            <tr>
              <th className="px-3 py-2">
                <input
                  type="checkbox"
                  aria-label="Select all on this page"
                  checked={allSelected}
                  onChange={() =>
                    setSelected(allSelected ? new Set() : new Set(items.map((t) => t.id)))
                  }
                />
              </th>
              <th className="px-3 py-2 font-medium">Date</th>
              <th className="px-3 py-2 font-medium">Label</th>
              <th className="px-3 py-2 font-medium">Category</th>
              <th className="px-3 py-2 font-medium">Account</th>
              <th className="px-3 py-2 text-right font-medium">Amount</th>
              <th className="px-3 py-2">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((t) => (
              <tr key={t.id} className={selected.has(t.id) ? "bg-bg" : ""}>
                <td className="px-3 py-2">
                  <input
                    type="checkbox"
                    aria-label={`Select ${t.label}`}
                    checked={selected.has(t.id)}
                    onChange={() => toggle(t.id)}
                  />
                </td>
                <td className="whitespace-nowrap px-3 py-2">{formatDate(t.booked_on)}</td>
                <td className="px-3 py-2">{t.label}</td>
                <td className="px-3 py-2">
                  <select
                    aria-label={`Category of ${t.label}`}
                    className={`max-w-48 rounded-md border bg-surface px-2 py-1 ${
                      t.category_id ? "border-border" : "border-warning"
                    }`}
                    value={t.category_id ?? ""}
                    onChange={(e) =>
                      setCategory.mutate({ id: t.id, categoryId: e.target.value || null })
                    }
                  >
                    <option value="">To categorise</option>
                    <CategoryOptions categories={categories} />
                  </select>
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-muted">{t.account_name}</td>
                <td
                  className={`tabular whitespace-nowrap px-3 py-2 text-right ${
                    t.amount.startsWith("-") ? "" : "text-positive"
                  }`}
                >
                  {formatEur(t.amount)}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-right">
                  <span className="flex items-center justify-end gap-2">
                    <Button
                      variant="ghost"
                      aria-label={`Create a rule from ${t.label}`}
                      onClick={() => onRule(t)}
                    >
                      Rule
                    </Button>
                    {t.source === "import" ? (
                      <span className="text-xs text-muted">Imported</span>
                    ) : confirming === t.id ? (
                      <>
                        <Button
                          variant="ghost"
                          className="border-negative text-negative"
                          disabled={remove.isPending}
                          onClick={() => remove.mutate(t.id)}
                        >
                          Confirm delete
                        </Button>
                        <Button variant="ghost" onClick={() => setConfirming(null)}>
                          Cancel
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button
                          variant="ghost"
                          aria-label={`Edit ${t.label}`}
                          onClick={() => onEdit(t)}
                        >
                          Edit
                        </Button>
                        <Button
                          variant="ghost"
                          aria-label={`Delete ${t.label}`}
                          onClick={() => setConfirming(t.id)}
                        >
                          Delete
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
  const queryClient = useQueryClient();
  const isIncome = transaction ? !transaction.amount.startsWith("-") : false;
  const [accountId, setAccountId] = useState(transaction?.account_id ?? accounts[0]?.id ?? "");
  const [bookedOn, setBookedOn] = useState(transaction?.booked_on ?? todayIso());
  const [kind, setKind] = useState<"expense" | "income">(isIncome ? "income" : "expense");
  const [amount, setAmount] = useState(
    transaction ? transaction.amount.replace("-", "").replace(".", ",") : "",
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
            ? (detailSentence(error) ?? "Check the form.")
            : apiErrorMessage(response),
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

  const title = transaction ? "Edit transaction" : "New transaction";
  return (
    <form
      aria-label={title}
      onSubmit={submit}
      className="grid gap-4 rounded-lg border border-accent bg-surface p-4 sm:grid-cols-2"
    >
      <h2 className="text-lg font-bold sm:col-span-2">{title}</h2>
      {transaction ? (
        <p className="text-sm sm:col-span-2">Account: {transaction.account_name}</p>
      ) : (
        <div className="flex flex-col gap-1">
          <label htmlFor={ids.account} className="text-sm font-medium">
            Account
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
        label="Date"
        type="date"
        required
        value={bookedOn}
        onChange={(e) => setBookedOn(e.target.value)}
      />
      <fieldset className="flex items-center gap-4">
        <legend className="sr-only">Direction</legend>
        {(["expense", "income"] as const).map((value) => (
          <label key={value} className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name={ids.kind}
              value={value}
              checked={kind === value}
              onChange={() => setKind(value)}
            />
            {value === "expense" ? "Expense" : "Income"}
          </label>
        ))}
      </fieldset>
      <TextField
        label="Amount (€)"
        inputMode="decimal"
        required
        className="tabular"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
      />
      <div className="sm:col-span-2">
        <TextField
          label="Label"
          required
          maxLength={200}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
        />
      </div>
      <div className="sm:col-span-2">
        <ErrorAlert
          message={
            invalid
              ? "Enter a positive amount in euros, e.g. 12,50, and pick Expense or Income."
              : (save.error?.message ?? null)
          }
        />
      </div>
      <div className="flex gap-3 sm:col-span-2">
        <Button type="submit" disabled={save.isPending}>
          Save
        </Button>
        <Button variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
