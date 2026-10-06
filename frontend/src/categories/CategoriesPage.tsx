import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import {
  applyRules,
  type CategoryKind,
  type CategoryOut,
  createCategory,
  deleteCategory,
  deleteRule,
  listAccounts,
  listRules,
  type RuleOut,
  updateCategory,
  updateRule,
} from "../api/generated";
import { apiErrorMessage, detailSentence } from "../auth/errors";
import { Button, ErrorAlert, TextField } from "../components/ui";
import { formatEur, parseEurInput } from "../lib/money";
import { CategoryOptions, categoriesQuery } from "../transactions/categories";

const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";

/** Raise a readable error from an SDK result, or return its data. */
function unwrap<T>(result: { data?: T; error?: unknown; response?: Response }): T {
  if (result.data === undefined && result.response?.status !== 204) {
    throw new Error(detailSentence(result.error) ?? apiErrorMessage(result.response));
  }
  return result.data as T;
}

function useRefresh() {
  const queryClient = useQueryClient();
  return async () => {
    for (const key of [
      "categories",
      "rules",
      "transactions",
      "toCategorise",
      "budget",
      "dashboard",
    ]) {
      await queryClient.invalidateQueries({ queryKey: [key] });
    }
  };
}

export function CategoriesPage() {
  const categories = useQuery(categoriesQuery);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const all = categories.data ?? [];
  const report = { onError: setError, onNotice: setNotice };

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl font-black tracking-tight">Categories</h1>
        <p className="text-sm text-muted">
          Two levels: categories and their subcategories. Deleting one sends its transactions back
          to "to categorise".
        </p>
      </div>
      <ErrorAlert message={error} />
      {notice && (
        <p className="rounded-md border border-accent px-3 py-2 text-sm" aria-live="polite">
          {notice}
        </p>
      )}
      <NewCategoryForm {...report} />
      {categories.isPending && <p className="text-sm text-muted">Loading…</p>}
      {categories.data && (
        <div className="grid gap-6 lg:grid-cols-2">
          <CategoryTree title="Spending" kind="expense" categories={all} {...report} />
          <CategoryTree title="Income" kind="income" categories={all} {...report} />
        </div>
      )}
      <RulesSection categories={all} {...report} />
    </div>
  );
}

type Report = { onError: (message: string | null) => void; onNotice: (message: string) => void };

function NewCategoryForm({ onError }: Report) {
  const refresh = useRefresh();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<CategoryKind>("expense");
  const kindId = useId();
  const create = useMutation({
    mutationFn: async () => unwrap(await createCategory({ body: { name, kind, parent_id: null } })),
    onSuccess: async () => {
      setName("");
      onError(null);
      await refresh();
    },
    onError: (exc) => onError(exc.message),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate();
  };
  return (
    <form
      aria-label="New category"
      onSubmit={submit}
      className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-surface p-4"
    >
      <TextField
        label="Name"
        required
        maxLength={60}
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <div className="flex flex-col gap-1">
        <label htmlFor={kindId} className="text-sm font-medium">
          Kind
        </label>
        <select
          id={kindId}
          className={fieldClass}
          value={kind}
          onChange={(e) => setKind(e.target.value as CategoryKind)}
        >
          <option value="expense">Spending</option>
          <option value="income">Income</option>
        </select>
      </div>
      <Button type="submit" disabled={create.isPending}>
        Add
      </Button>
    </form>
  );
}

function CategoryTree({
  title,
  kind,
  categories,
  ...report
}: { title: string; kind: CategoryKind; categories: CategoryOut[] } & Report) {
  const parents = categories.filter((c) => c.kind === kind && c.parent_id === null);
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-xl font-bold">{title}</h2>
      <ul
        aria-label={`${title} categories`}
        className="divide-y divide-border rounded-lg border border-border bg-surface"
      >
        {parents.map((parent) => (
          <li key={parent.id} aria-label={parent.name} className="px-4 py-3">
            <CategoryLine category={parent} parents={parents} {...report} />
            <ChildList parent={parent} categories={categories} parents={parents} {...report} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function ChildList({
  parent,
  categories,
  parents,
  ...report
}: { parent: CategoryOut; categories: CategoryOut[]; parents: CategoryOut[] } & Report) {
  const refresh = useRefresh();
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const children = categories.filter((c) => c.parent_id === parent.id);
  const add = useMutation({
    mutationFn: async () =>
      unwrap(await createCategory({ body: { name, kind: parent.kind, parent_id: parent.id } })),
    onSuccess: async () => {
      setName("");
      setAdding(false);
      report.onError(null);
      await refresh();
    },
    onError: (exc) => report.onError(exc.message),
  });
  return (
    <div className="mt-2 pl-6">
      {children.length > 0 && (
        <ul aria-label={`Subcategories of ${parent.name}`} className="flex flex-col gap-1">
          {children.map((child) => (
            <li key={child.id} aria-label={child.name}>
              <CategoryLine category={child} parents={parents} {...report} />
            </li>
          ))}
        </ul>
      )}
      {adding ? (
        <form
          className="mt-2 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) add.mutate();
          }}
        >
          <input
            aria-label={`New subcategory of ${parent.name}`}
            className="rounded-md border border-border bg-surface px-2 py-1 text-sm"
            maxLength={60}
            // biome-ignore lint/a11y/noAutofocus: the field appears because the user asked for it.
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Escape" && setAdding(false)}
          />
          <Button type="submit" variant="ghost">
            Add
          </Button>
        </form>
      ) : (
        <button
          type="button"
          className="mt-1 text-sm text-muted hover:text-accent"
          aria-label={`Add a subcategory to ${parent.name}`}
          onClick={() => setAdding(true)}
        >
          + Subcategory
        </button>
      )}
    </div>
  );
}

function CategoryLine({
  category,
  parents,
  onError,
}: { category: CategoryOut; parents: CategoryOut[] } & Report) {
  const refresh = useRefresh();
  const [renaming, setRenaming] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [name, setName] = useState(category.name);
  const patch = useMutation({
    mutationFn: async (body: { name?: string; parent_id?: string }) =>
      unwrap(await updateCategory({ path: { category_id: category.id }, body })),
    onSuccess: async () => {
      setRenaming(false);
      onError(null);
      await refresh();
    },
    onError: (exc) => onError(exc.message),
  });
  const remove = useMutation({
    mutationFn: async () => unwrap(await deleteCategory({ path: { category_id: category.id } })),
    onSuccess: async () => {
      onError(null);
      await refresh();
    },
    onError: (exc) => {
      setConfirming(false);
      onError(exc.message);
    },
  });
  const isChild = category.parent_id !== null;

  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      {renaming ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim() && name !== category.name) patch.mutate({ name });
            else setRenaming(false);
          }}
        >
          <input
            aria-label={`New name for ${category.name}`}
            className="rounded-md border border-border bg-surface px-2 py-1 text-sm"
            maxLength={60}
            // biome-ignore lint/a11y/noAutofocus: the field appears because the user asked for it.
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Escape" && setRenaming(false)}
          />
        </form>
      ) : (
        <span className={isChild ? "" : "font-semibold"}>{category.name}</span>
      )}
      <span className="flex flex-wrap items-center gap-2">
        {isChild && (
          <select
            aria-label={`Move ${category.name} to`}
            className="rounded-md border border-border bg-surface px-2 py-1 text-xs"
            value={category.parent_id ?? ""}
            onChange={(e) => patch.mutate({ parent_id: e.target.value })}
          >
            {parents.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        )}
        <Button
          variant="ghost"
          className="px-2 py-1 text-xs"
          aria-label={`Rename ${category.name}`}
          onClick={() => setRenaming(true)}
        >
          Rename
        </Button>
        {confirming ? (
          <>
            <Button
              variant="ghost"
              className="border-negative px-2 py-1 text-xs text-negative"
              aria-label={`Confirm: delete ${category.name}`}
              disabled={remove.isPending}
              onClick={() => remove.mutate()}
            >
              Delete it
            </Button>
            <Button
              variant="ghost"
              className="px-2 py-1 text-xs"
              onClick={() => setConfirming(false)}
            >
              Cancel
            </Button>
          </>
        ) : (
          <Button
            variant="ghost"
            className="px-2 py-1 text-xs"
            aria-label={`Delete ${category.name}`}
            onClick={() => setConfirming(true)}
          >
            Delete
          </Button>
        )}
      </span>
    </div>
  );
}

function ruleName(rule: RuleOut): string {
  return rule.label_contains ?? rule.category_name;
}

function ruleConditions(rule: RuleOut, accounts: Map<string, string>): string {
  const parts = [];
  if (rule.label_contains) parts.push(`Label contains "${rule.label_contains}"`);
  if (rule.amount_min && rule.amount_max) {
    parts.push(`from ${formatEur(rule.amount_min)} to ${formatEur(rule.amount_max)}`);
  } else if (rule.amount_min) {
    parts.push(`at least ${formatEur(rule.amount_min)}`);
  } else if (rule.amount_max) {
    parts.push(`at most ${formatEur(rule.amount_max)}`);
  }
  if (rule.account_id) parts.push(`on ${accounts.get(rule.account_id) ?? "an account"}`);
  return parts.join(" · ");
}

function RulesSection({ categories, onError, onNotice }: { categories: CategoryOut[] } & Report) {
  const refresh = useRefresh();
  const rules = useQuery({
    queryKey: ["rules"],
    queryFn: async () => (await listRules({ throwOnError: true })).data,
  });
  const accounts = useQuery({
    queryKey: ["accounts", { includeClosed: false }],
    queryFn: async () =>
      (await listAccounts({ query: { include_closed: false }, throwOnError: true })).data,
  });
  const names = new Map((accounts.data ?? []).map((a) => [a.id, a.name]));
  const [editing, setEditing] = useState<string | null>(null);
  const list = rules.data ?? [];

  const swap = useMutation({
    mutationFn: async ([a, b]: [RuleOut, RuleOut]) => {
      // a moves to b's place; equal priorities would not reorder, so step past b.
      const target = a.priority === b.priority ? b.priority - 1 : b.priority;
      unwrap(await updateRule({ path: { rule_id: a.id }, body: { priority: target } }));
      unwrap(await updateRule({ path: { rule_id: b.id }, body: { priority: a.priority } }));
    },
    onSuccess: refresh,
    onError: (exc) => onError(exc.message),
  });
  const remove = useMutation({
    mutationFn: async (rule: RuleOut) => unwrap(await deleteRule({ path: { rule_id: rule.id } })),
    onSuccess: refresh,
    onError: (exc) => onError(exc.message),
  });
  const apply = useMutation({
    mutationFn: async () =>
      (await applyRules({ body: { only_uncategorised: true }, throwOnError: true })).data.updated,
    onSuccess: async (updated) => {
      onNotice(`${updated} transaction${updated === 1 ? "" : "s"} categorised.`);
      await refresh();
    },
  });

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold">Rules</h2>
          <p className="text-sm text-muted">
            The first rule that matches sets the category of each import and manual entry. Create
            rules from a transaction's "Rule" button.
          </p>
        </div>
        <Button
          variant="ghost"
          disabled={apply.isPending || list.length === 0}
          onClick={() => apply.mutate()}
        >
          Apply the rules to past transactions
        </Button>
      </div>
      {list.length === 0 ? (
        <p className="text-sm text-muted">No rules yet.</p>
      ) : (
        <ol
          aria-label="Rules, in the order they run"
          className="divide-y divide-border rounded-lg border border-border bg-surface"
        >
          {list.map((rule, i) => (
            <li key={rule.id} className="flex flex-col gap-2 px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  <span className="text-sm">{ruleConditions(rule, names)}</span>
                  <span className="text-muted"> → </span>
                  <span className="font-medium">{rule.category_name}</span>
                </span>
                <span className="flex gap-2">
                  <Button
                    variant="ghost"
                    className="px-2 py-1 text-xs"
                    aria-label={`Run the rule "${ruleName(rule)}" earlier`}
                    disabled={i === 0 || swap.isPending}
                    onClick={() => list[i - 1] && swap.mutate([rule, list[i - 1] as RuleOut])}
                  >
                    ↑
                  </Button>
                  <Button
                    variant="ghost"
                    className="px-2 py-1 text-xs"
                    aria-label={`Run the rule "${ruleName(rule)}" later`}
                    disabled={i === list.length - 1 || swap.isPending}
                    onClick={() => list[i + 1] && swap.mutate([rule, list[i + 1] as RuleOut])}
                  >
                    ↓
                  </Button>
                  <Button
                    variant="ghost"
                    className="px-2 py-1 text-xs"
                    aria-label={`Edit the rule "${ruleName(rule)}"`}
                    onClick={() => setEditing(editing === rule.id ? null : rule.id)}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="ghost"
                    className="px-2 py-1 text-xs"
                    aria-label={`Delete the rule "${ruleName(rule)}"`}
                    disabled={remove.isPending}
                    onClick={() => remove.mutate(rule)}
                  >
                    Delete
                  </Button>
                </span>
              </div>
              {editing === rule.id && (
                <RuleEditForm
                  rule={rule}
                  categories={categories}
                  accounts={accounts.data ?? []}
                  onDone={() => setEditing(null)}
                  onError={onError}
                />
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function RuleEditForm({
  rule,
  categories,
  accounts,
  onDone,
  onError,
}: {
  rule: RuleOut;
  categories: CategoryOut[];
  accounts: { id: string; name: string }[];
  onDone: () => void;
  onError: (message: string | null) => void;
}) {
  const refresh = useRefresh();
  const ids = { category: useId(), account: useId() };
  const [categoryId, setCategoryId] = useState(rule.category_id);
  const [label, setLabel] = useState(rule.label_contains ?? "");
  const [min, setMin] = useState(rule.amount_min?.replace(".", ",") ?? "");
  const [max, setMax] = useState(rule.amount_max?.replace(".", ",") ?? "");
  const [accountId, setAccountId] = useState(rule.account_id ?? "");
  const [invalid, setInvalid] = useState(false);
  const save = useMutation({
    mutationFn: async (body: Parameters<typeof updateRule>[0]["body"]) =>
      unwrap(await updateRule({ path: { rule_id: rule.id }, body })),
    onSuccess: async () => {
      onError(null);
      onDone();
      await refresh();
    },
    onError: (exc) => onError(exc.message),
  });
  const amount = (text: string) => (text.trim() ? parseEurInput(text) : null);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const low = amount(min);
    const high = amount(max);
    const bad = (min.trim() && low === null) || (max.trim() && high === null);
    setInvalid(Boolean(bad));
    if (bad) return;
    save.mutate({
      category_id: categoryId,
      label_contains: label.trim() || null,
      amount_min: low,
      amount_max: high,
      account_id: accountId || null,
    });
  };
  return (
    <form
      aria-label={`Edit the rule "${ruleName(rule)}"`}
      onSubmit={submit}
      className="grid gap-3 rounded-md border border-accent p-3 sm:grid-cols-2"
    >
      <div className="flex flex-col gap-1">
        <label htmlFor={ids.category} className="text-sm font-medium">
          Category
        </label>
        <select
          id={ids.category}
          className={fieldClass}
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
        >
          <CategoryOptions categories={categories} />
        </select>
      </div>
      <TextField
        label="Label contains"
        maxLength={100}
        value={label}
        onChange={(e) => setLabel(e.target.value)}
      />
      <TextField
        label="From (€, absolute amount)"
        inputMode="decimal"
        value={min}
        onChange={(e) => setMin(e.target.value)}
      />
      <TextField
        label="To (€, absolute amount)"
        inputMode="decimal"
        value={max}
        onChange={(e) => setMax(e.target.value)}
      />
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
          <option value="">Any account</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
      </div>
      <div className="sm:col-span-2">
        <ErrorAlert message={invalid ? "Enter amounts in euros, e.g. 12,50." : null} />
      </div>
      <div className="flex gap-2 sm:col-span-2">
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
