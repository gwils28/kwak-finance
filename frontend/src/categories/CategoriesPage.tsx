import { useMutation, useQuery, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
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
  previewShift,
  type RuleOut,
  type ShiftPreviewOut,
  updateCategory,
  updateRule,
} from "../api/generated";
import { apiErrorMessage, detailSentence } from "../auth/errors";
import { meQuery } from "../auth/session";
import { usePeriodLabel } from "../budget/PlanPanel";
import { Button, ErrorAlert, TextField } from "../components/ui";
import { useI18n } from "../i18n";
import type { Messages } from "../i18n/en";
import { amountInput, formatEur, parseEurInput } from "../lib/money";
import { monthLabel } from "../lib/months";
import { CategoryOptions, categoriesQuery } from "../transactions/categories";
import { RestoreDefaults } from "./RestoreDefaults";

const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";

/** Raise a readable error from an SDK result, or return its data. */
function unwrap<T>(t: Messages, result: { data?: T; error?: unknown; response?: Response }): T {
  if (result.data === undefined && result.response?.status !== 204) {
    throw new Error(detailSentence(result.error) ?? apiErrorMessage(t, result.response));
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
  const { t } = useI18n();
  const { data: user } = useSuspenseQuery(meQuery);
  const categories = useQuery(categoriesQuery);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const all = categories.data ?? [];
  const report = { onError: setError, onNotice: setNotice };

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl font-black tracking-tight">{t.categories.title}</h1>
        <p className="text-sm text-muted">{t.categories.intro}</p>
      </div>
      <ErrorAlert message={error} />
      {notice && (
        <p className="rounded-md border border-accent px-3 py-2 text-sm" aria-live="polite">
          {notice}
        </p>
      )}
      <NewCategoryForm {...report} />
      {categories.isPending && <p className="text-sm text-muted">{t.common.loading}</p>}
      {categories.data && (
        <div className="grid gap-6 lg:grid-cols-2">
          <CategoryTree title={t.categories.spending} kind="expense" categories={all} {...report} />
          <div className="flex flex-col gap-6">
            <CategoryTree title={t.categories.income} kind="income" categories={all} {...report} />
            <CategoryTree
              title={t.categories.savings}
              help={t.categories.savingsHelp}
              kind="savings"
              categories={all}
              {...report}
            />
          </div>
        </div>
      )}
      <RulesSection categories={all} {...report} />
      {user.role === "owner" && <RestoreDefaults {...report} />}
    </div>
  );
}

type Report = { onError: (message: string | null) => void; onNotice: (message: string) => void };

function NewCategoryForm({ onError }: Report) {
  const { t } = useI18n();
  const refresh = useRefresh();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<CategoryKind>("expense");
  const kindId = useId();
  const create = useMutation({
    mutationFn: async () =>
      unwrap(t, await createCategory({ body: { name, kind, parent_id: null } })),
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
      aria-label={t.categories.newCategory}
      onSubmit={submit}
      className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-surface p-4"
    >
      <TextField
        label={t.categories.name}
        required
        maxLength={60}
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <div className="flex flex-col gap-1">
        <label htmlFor={kindId} className="text-sm font-medium">
          {t.categories.kind}
        </label>
        <select
          id={kindId}
          className={fieldClass}
          value={kind}
          onChange={(e) => setKind(e.target.value as CategoryKind)}
        >
          <option value="expense">{t.categories.spending}</option>
          <option value="income">{t.categories.income}</option>
          <option value="savings">{t.categories.savings}</option>
        </select>
      </div>
      <Button type="submit" disabled={create.isPending}>
        {t.common.add}
      </Button>
    </form>
  );
}

function CategoryTree({
  title,
  help,
  kind,
  categories,
  ...report
}: { title: string; help?: string; kind: CategoryKind; categories: CategoryOut[] } & Report) {
  const { t } = useI18n();
  const parents = categories.filter((c) => c.kind === kind && c.parent_id === null);
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-xl font-bold">{title}</h2>
      {help && <p className="text-sm text-muted">{help}</p>}
      <ul
        aria-label={t.categories.treeLabel(title)}
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
  const { t } = useI18n();
  const refresh = useRefresh();
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const children = categories.filter((c) => c.parent_id === parent.id);
  const add = useMutation({
    mutationFn: async () =>
      unwrap(t, await createCategory({ body: { name, kind: parent.kind, parent_id: parent.id } })),
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
        <ul aria-label={t.categories.subcategoriesOf(parent.name)} className="flex flex-col gap-1">
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
            aria-label={t.categories.newSubcategoryOf(parent.name)}
            className="rounded-md border border-border bg-surface px-2 py-1 text-sm"
            maxLength={60}
            // biome-ignore lint/a11y/noAutofocus: the field appears because the user asked for it.
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Escape" && setAdding(false)}
          />
          <Button type="submit" variant="ghost">
            {t.common.add}
          </Button>
        </form>
      ) : (
        <button
          type="button"
          className="mt-1 text-sm text-muted hover:text-accent"
          aria-label={t.categories.addSubcategoryTo(parent.name)}
          onClick={() => setAdding(true)}
        >
          {t.categories.subcategory}
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
  const { t } = useI18n();
  const refresh = useRefresh();
  const [renaming, setRenaming] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [shifting, setShifting] = useState(false);
  const [name, setName] = useState(category.name);
  const patch = useMutation({
    mutationFn: async (body: { name?: string; parent_id?: string }) =>
      unwrap(t, await updateCategory({ path: { category_id: category.id }, body })),
    onSuccess: async () => {
      setRenaming(false);
      onError(null);
      await refresh();
    },
    onError: (exc) => onError(exc.message),
  });
  const remove = useMutation({
    mutationFn: async () => unwrap(t, await deleteCategory({ path: { category_id: category.id } })),
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
  const parent = parents.find((p) => p.id === category.parent_id);
  const shift = shiftSummary(t, category, parent);

  return (
    <div>
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
              aria-label={t.categories.newNameFor(category.name)}
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
          <span>
            <span className={isChild ? "" : "font-semibold"}>{category.name}</span>
            {shift && <span className="ml-2 text-xs text-muted">{shift}</span>}
          </span>
        )}
        <span className="flex flex-wrap items-center gap-2">
          {isChild && (
            <select
              aria-label={t.categories.moveTo(category.name)}
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
            aria-label={t.categories.shift.open(category.name)}
            aria-expanded={shifting}
            title={t.categories.shift.help}
            onClick={() => setShifting(!shifting)}
          >
            {t.categories.shift.button}
          </Button>
          <Button
            variant="ghost"
            className="px-2 py-1 text-xs"
            aria-label={t.categories.renameNamed(category.name)}
            onClick={() => setRenaming(true)}
          >
            {t.categories.rename}
          </Button>
          {confirming ? (
            <>
              <Button
                variant="ghost"
                className="border-negative px-2 py-1 text-xs text-negative"
                aria-label={t.categories.confirmDeleteNamed(category.name)}
                disabled={remove.isPending}
                onClick={() => remove.mutate()}
              >
                {t.categories.deleteIt}
              </Button>
              <Button
                variant="ghost"
                className="px-2 py-1 text-xs"
                onClick={() => setConfirming(false)}
              >
                {t.common.cancel}
              </Button>
            </>
          ) : (
            <Button
              variant="ghost"
              className="px-2 py-1 text-xs"
              aria-label={t.categories.deleteNamed(category.name)}
              onClick={() => setConfirming(true)}
            >
              {t.common.delete}
            </Button>
          )}
        </span>
      </div>
      {shifting && (
        <ShiftForm
          category={category}
          parent={parent}
          onError={onError}
          onDone={() => setShifting(false)}
        />
      )}
    </div>
  );
}

/** What the category's next-month shift says (F-CAT-5), or nothing when it has none. */
function shiftSummary(t: Messages, category: CategoryOut, parent?: CategoryOut): string | null {
  const own = category.shift_day ?? null;
  if (own !== null && own > 0) return t.categories.shift.from(own);
  if (own === 0) return parent ? t.categories.shift.never : null;
  const inherited = parent?.shift_day ?? 0;
  return parent && inherited > 0 ? t.categories.shift.like(parent.name, inherited) : null;
}

type ShiftMode = "inherit" | "never" | "day";

function ShiftForm({
  category,
  parent,
  onError,
  onDone,
}: {
  category: CategoryOut;
  parent?: CategoryOut;
  onError: (message: string | null) => void;
  onDone: () => void;
}) {
  const { t } = useI18n();
  const refresh = useRefresh();
  const periodLabel = usePeriodLabel();
  const ids = { mode: useId(), day: useId() };
  const own = category.shift_day ?? null;
  const [mode, setMode] = useState<ShiftMode>(
    own !== null && own > 0 ? "day" : own === 0 && parent ? "never" : "inherit",
  );
  const [day, setDay] = useState(String(own !== null && own > 0 ? own : 15));
  const [invalid, setInvalid] = useState(false);
  const [preview, setPreview] = useState<ShiftPreviewOut | null>(null);

  // A top-level category has no parent to follow: "no" stores no setting at all.
  const value = (): number | null | undefined => {
    if (mode === "inherit") return null;
    if (mode === "never") return 0;
    const n = Number(day);
    return Number.isInteger(n) && n >= 1 && n <= 31 ? n : undefined;
  };
  const check = () => {
    const v = value();
    setInvalid(v === undefined);
    return v;
  };

  const ask = useMutation({
    mutationFn: async (v: number | null) =>
      unwrap(
        t,
        await previewShift({
          path: { category_id: category.id },
          query: v === null ? {} : { day: v },
        }),
      ),
    onSuccess: setPreview,
    onError: (exc) => onError(exc.message),
  });
  const save = useMutation({
    mutationFn: async (v: number | null) =>
      unwrap(
        t,
        await updateCategory({ path: { category_id: category.id }, body: { shift_day: v } }),
      ),
    onSuccess: async () => {
      onError(null);
      onDone();
      await refresh();
    },
    onError: (exc) => onError(exc.message),
  });

  return (
    <form
      className="mt-2 flex flex-wrap items-end gap-3 rounded-md border border-border p-3 text-sm"
      onSubmit={(e) => {
        e.preventDefault();
        const v = check();
        if (v !== undefined) save.mutate(v);
      }}
    >
      <p className="w-full text-xs text-muted">{t.categories.shift.help}</p>
      <label htmlFor={ids.mode} className="flex flex-col gap-1 font-medium">
        {t.categories.shift.mode}
        <select
          id={ids.mode}
          className={fieldClass}
          value={mode}
          onChange={(e) => {
            setMode(e.target.value as ShiftMode);
            setPreview(null);
          }}
        >
          <option value="inherit">
            {parent ? t.categories.shift.inherit(parent.name) : t.categories.shift.no}
          </option>
          {parent && <option value="never">{t.categories.shift.neverOption}</option>}
          <option value="day">{t.categories.shift.day}</option>
        </select>
      </label>
      {mode === "day" && (
        <label htmlFor={ids.day} className="flex flex-col gap-1 font-medium">
          {t.categories.shift.dayLabel}
          <input
            id={ids.day}
            inputMode="numeric"
            className={`${fieldClass} w-20`}
            value={day}
            onChange={(e) => {
              setDay(e.target.value);
              setPreview(null);
            }}
          />
        </label>
      )}
      <Button
        variant="ghost"
        disabled={ask.isPending}
        onClick={() => {
          const v = check();
          if (v !== undefined) ask.mutate(v);
        }}
      >
        {t.categories.shift.preview}
      </Button>
      <Button type="submit" disabled={save.isPending}>
        {t.categories.shift.save}
      </Button>
      <Button variant="ghost" onClick={onDone}>
        {t.common.cancel}
      </Button>
      {invalid && <p className="w-full text-negative">{t.categories.shift.invalidDay}</p>}
      {preview && (
        <div role="status" className="w-full rounded-md bg-bg px-3 py-2">
          <p>
            {t.categories.shift.moved(preview.moved, preview.months.map(monthLabel).join(", "))}
          </p>
          {preview.locked_plans.length > 0 && (
            <p className="text-warning">
              {t.categories.shift.locked(preview.locked_plans.map(periodLabel).join(", "))}
            </p>
          )}
        </div>
      )}
    </form>
  );
}

function ruleName(rule: RuleOut): string {
  return rule.label_contains ?? rule.category_name;
}

function ruleConditions(t: Messages, rule: RuleOut, accounts: Map<string, string>): string {
  const parts = [];
  if (rule.label_contains) parts.push(t.categories.labelContainsQuoted(rule.label_contains));
  if (rule.amount_min && rule.amount_max) {
    parts.push(t.categories.between(formatEur(rule.amount_min), formatEur(rule.amount_max)));
  } else if (rule.amount_min) {
    parts.push(t.categories.atLeast(formatEur(rule.amount_min)));
  } else if (rule.amount_max) {
    parts.push(t.categories.atMost(formatEur(rule.amount_max)));
  }
  if (rule.account_id)
    parts.push(t.categories.onAccount(accounts.get(rule.account_id) ?? t.categories.anAccount));
  return parts.join(" · ");
}

function RulesSection({ categories, onError, onNotice }: { categories: CategoryOut[] } & Report) {
  const { t } = useI18n();
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
      unwrap(t, await updateRule({ path: { rule_id: a.id }, body: { priority: target } }));
      unwrap(t, await updateRule({ path: { rule_id: b.id }, body: { priority: a.priority } }));
    },
    onSuccess: refresh,
    onError: (exc) => onError(exc.message),
  });
  const remove = useMutation({
    mutationFn: async (rule: RuleOut) =>
      unwrap(t, await deleteRule({ path: { rule_id: rule.id } })),
    onSuccess: refresh,
    onError: (exc) => onError(exc.message),
  });
  const apply = useMutation({
    mutationFn: async () =>
      (await applyRules({ body: { only_uncategorised: true }, throwOnError: true })).data.updated,
    onSuccess: async (updated) => {
      onNotice(t.categories.categorised(updated));
      await refresh();
    },
  });

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold">{t.categories.rules}</h2>
          <p className="text-sm text-muted">{t.categories.rulesIntro}</p>
        </div>
        <Button
          variant="ghost"
          disabled={apply.isPending || list.length === 0}
          onClick={() => apply.mutate()}
        >
          {t.categories.applyRules}
        </Button>
      </div>
      {list.length === 0 ? (
        <p className="text-sm text-muted">{t.categories.noRules}</p>
      ) : (
        <ol
          aria-label={t.categories.rulesOrder}
          className="divide-y divide-border rounded-lg border border-border bg-surface"
        >
          {list.map((rule, i) => (
            <li key={rule.id} className="flex flex-col gap-2 px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  <span className="text-sm">{ruleConditions(t, rule, names)}</span>
                  <span className="text-muted"> → </span>
                  <span className="font-medium">{rule.category_name}</span>
                </span>
                <span className="flex gap-2">
                  <Button
                    variant="ghost"
                    className="px-2 py-1 text-xs"
                    aria-label={t.categories.earlier(ruleName(rule))}
                    disabled={i === 0 || swap.isPending}
                    onClick={() => list[i - 1] && swap.mutate([rule, list[i - 1] as RuleOut])}
                  >
                    ↑
                  </Button>
                  <Button
                    variant="ghost"
                    className="px-2 py-1 text-xs"
                    aria-label={t.categories.later(ruleName(rule))}
                    disabled={i === list.length - 1 || swap.isPending}
                    onClick={() => list[i + 1] && swap.mutate([rule, list[i + 1] as RuleOut])}
                  >
                    ↓
                  </Button>
                  <Button
                    variant="ghost"
                    className="px-2 py-1 text-xs"
                    aria-label={t.categories.editRule(ruleName(rule))}
                    onClick={() => setEditing(editing === rule.id ? null : rule.id)}
                  >
                    {t.common.edit}
                  </Button>
                  <Button
                    variant="ghost"
                    className="px-2 py-1 text-xs"
                    aria-label={t.categories.deleteRule(ruleName(rule))}
                    disabled={remove.isPending}
                    onClick={() => remove.mutate(rule)}
                  >
                    {t.common.delete}
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
  const { t } = useI18n();
  const refresh = useRefresh();
  const ids = { category: useId(), account: useId() };
  const [categoryId, setCategoryId] = useState(rule.category_id);
  const [label, setLabel] = useState(rule.label_contains ?? "");
  const [min, setMin] = useState(rule.amount_min ? amountInput(rule.amount_min) : "");
  const [max, setMax] = useState(rule.amount_max ? amountInput(rule.amount_max) : "");
  const [accountId, setAccountId] = useState(rule.account_id ?? "");
  const [invalid, setInvalid] = useState(false);
  const save = useMutation({
    mutationFn: async (body: Parameters<typeof updateRule>[0]["body"]) =>
      unwrap(t, await updateRule({ path: { rule_id: rule.id }, body })),
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
      aria-label={t.categories.editRule(ruleName(rule))}
      onSubmit={submit}
      className="grid gap-3 rounded-md border border-accent p-3 sm:grid-cols-2"
    >
      <div className="flex flex-col gap-1">
        <label htmlFor={ids.category} className="text-sm font-medium">
          {t.categories.category}
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
        label={t.categories.labelContains}
        maxLength={100}
        value={label}
        onChange={(e) => setLabel(e.target.value)}
      />
      <TextField
        label={t.categories.amountFrom}
        inputMode="decimal"
        value={min}
        onChange={(e) => setMin(e.target.value)}
      />
      <TextField
        label={t.categories.amountTo}
        inputMode="decimal"
        value={max}
        onChange={(e) => setMax(e.target.value)}
      />
      <div className="flex flex-col gap-1">
        <label htmlFor={ids.account} className="text-sm font-medium">
          {t.categories.account}
        </label>
        <select
          id={ids.account}
          className={fieldClass}
          value={accountId}
          onChange={(e) => setAccountId(e.target.value)}
        >
          <option value="">{t.categories.anyAccount}</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
      </div>
      <div className="sm:col-span-2">
        <ErrorAlert message={invalid ? t.categories.invalidAmounts : null} />
      </div>
      <div className="flex gap-2 sm:col-span-2">
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
