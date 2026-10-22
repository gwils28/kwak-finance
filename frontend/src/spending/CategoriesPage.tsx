import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, type KeyboardEvent, useId, useState } from "react";
import {
  type CategoryKind,
  createSpendingCategory,
  deleteSpendingCategory,
  restoreSpendingCategories,
  type SpendingCategoryOut,
  updateSpendingCategory,
} from "../api/generated";
import { detailSentence } from "../auth/errors";
import { meQuery } from "../auth/session";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { byKind, refreshSpending, spendingCategoriesQuery } from "./queries";

type Kind = Extract<CategoryKind, "expense" | "savings">;
const field = "rounded-md border border-border bg-surface px-3 py-2";

/** The spending categories (F-CAT-1, 4, 6): one level, expense or savings. */
export function CategoriesPage() {
  const { t } = useI18n();
  const c = t.spending.categoriesPage;
  const queryClient = useQueryClient();
  const me = useQuery(meQuery);
  const categories = useQuery(spendingCategoriesQuery);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState<string | null>(null);
  const id = useId();

  const run = async (action: () => Promise<string>) => {
    setError(null);
    try {
      setNotice(await action());
      await refreshSpending(queryClient);
    } catch (exc) {
      setNotice("");
      setError(detailSentence(exc) ?? t.errors.generic);
    }
  };

  if (!categories.data) return <p>{t.common.loading}</p>;
  const { expense, savings } = byKind(categories.data);

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <h1 className="text-3xl font-black tracking-tight">{c.title}</h1>
      <p className="text-muted">{c.intro}</p>
      {notice && (
        <p className="rounded-md border border-accent px-3 py-2 text-sm" aria-live="polite">
          {notice}
        </p>
      )}
      <ErrorAlert message={error} />
      {(
        [
          ["expense", c.expenses, expense],
          ["savings", c.savings, savings],
        ] as const
      ).map(([kind, title, list]) => (
        <section key={kind} aria-labelledby={`${id}-${kind}`} className="flex flex-col gap-2">
          <h2 id={`${id}-${kind}`} className="text-xl font-bold">
            {title}
          </h2>
          <ul className="flex flex-col divide-y divide-border rounded-lg border border-border bg-surface">
            {list.map((category) => (
              <CategoryRow
                key={category.id}
                category={category}
                others={list.filter((o) => o.id !== category.id)}
                run={run}
              />
            ))}
          </ul>
        </section>
      ))}
      <AddCategory run={run} />
      {me.data?.role === "owner" && (
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="ghost"
            onClick={() =>
              void run(async () =>
                c.restored((await restoreSpendingCategories({ throwOnError: true })).data.added),
              )
            }
          >
            {c.restore}
          </Button>
          <span className="text-sm text-muted">{c.restoreHint}</span>
        </div>
      )}
    </div>
  );
}

function CategoryRow({
  category,
  others,
  run,
}: {
  category: SpendingCategoryOut;
  others: SpendingCategoryOut[];
  run: (action: () => Promise<string>) => Promise<void>;
}) {
  const { t } = useI18n();
  const c = t.spending.categoriesPage;
  const [name, setName] = useState(category.name);
  const [deleting, setDeleting] = useState(false);
  const [moveTo, setMoveTo] = useState("");
  const path = { category_id: category.id };

  const rename = () => {
    if (!name.trim() || name.trim() === category.name) return;
    void run(async () => {
      await updateSpendingCategory({ path, body: { name }, throwOnError: true });
      return c.saved;
    });
  };
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    // The blur saves: Enter then blur would rename twice.
    if (event.key === "Enter") event.currentTarget.blur();
    if (event.key === "Escape") setName(category.name);
  };

  return (
    <li className="flex flex-col gap-2 px-3 py-2">
      <div className="flex flex-wrap items-center gap-3">
        <input
          aria-label={c.rename(category.name)}
          value={name}
          maxLength={60}
          onChange={(e) => setName(e.target.value)}
          onBlur={rename}
          onKeyDown={onKeyDown}
          className="min-w-0 flex-1 rounded border border-transparent bg-transparent px-2 py-1 hover:border-border focus:border-accent"
        />
        {category.kind === "expense" && (
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={category.one_off}
              onChange={(e) =>
                void run(async () => {
                  await updateSpendingCategory({
                    path,
                    body: { one_off: e.target.checked },
                    throwOnError: true,
                  });
                  return c.saved;
                })
              }
            />
            {c.oneOff}
          </label>
        )}
        <Button
          variant="ghost"
          className="py-1"
          aria-label={c.delete(category.name)}
          onClick={() => setDeleting((d) => !d)}
        >
          {t.common.delete}
        </Button>
      </div>
      {deleting && (
        <div className="flex flex-wrap items-end gap-3 pb-1 text-sm">
          <label className="flex flex-col gap-1">
            {c.moveTo}
            <select value={moveTo} onChange={(e) => setMoveTo(e.target.value)} className={field}>
              <option value="">{c.noMove}</option>
              {others.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </select>
          </label>
          <Button
            onClick={() =>
              void run(async () => {
                await deleteSpendingCategory({
                  path,
                  query: moveTo ? { move_to: moveTo } : undefined,
                  throwOnError: true,
                });
                return c.deleted;
              })
            }
          >
            {c.deleteConfirm}
          </Button>
          <Button variant="ghost" onClick={() => setDeleting(false)}>
            {t.common.cancel}
          </Button>
        </div>
      )}
    </li>
  );
}

function AddCategory({ run }: { run: (action: () => Promise<string>) => Promise<void> }) {
  const { t } = useI18n();
  const c = t.spending.categoriesPage;
  const id = useId();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<Kind>("expense");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    void run(async () => {
      await createSpendingCategory({ body: { name, kind }, throwOnError: true });
      setName("");
      return c.saved;
    });
  };

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-name`} className="text-sm font-medium">
          {c.name}
        </label>
        <input
          id={`${id}-name`}
          required
          maxLength={60}
          value={name}
          onChange={(e) => setName(e.target.value)}
          className={field}
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-kind`} className="text-sm font-medium">
          {c.kind}
        </label>
        <select
          id={`${id}-kind`}
          value={kind}
          onChange={(e) => setKind(e.target.value as Kind)}
          className={field}
        >
          <option value="expense">{c.kinds.expense}</option>
          <option value="savings">{c.kinds.savings}</option>
        </select>
      </div>
      <Button type="submit">{c.add}</Button>
    </form>
  );
}
