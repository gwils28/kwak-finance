import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type FormEvent, useId, useState } from "react";
import {
  createFixed,
  deleteFixed,
  type FixedFrequency,
  type FixedIn,
  type FixedOut,
  replaceFixed,
  type SpendingCategoryOut,
} from "../api/generated";
import { detailSentence } from "../auth/errors";
import { InView } from "../components/InView";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { amountInputShort, formatEur, parseEurInput } from "../lib/money";
import { monthLabel, thisMonth } from "../lib/months";
import { negate } from "./draft";
import { CategoryOptions } from "./LineRow";
import { fixedQuery, refreshSpending, spendingCategoriesQuery } from "./queries";

const FREQUENCIES: FixedFrequency[] = ["monthly", "quarterly", "yearly"];
const field = "rounded-md border border-border bg-surface px-3 py-2";

/** The fixed expenses (F-FIX-1), listed, added and changed here; confirmed in the grid. */
export function FixedPage() {
  const { t } = useI18n();
  const f = t.spending.fixedPage;
  const queryClient = useQueryClient();
  const items = useQuery(fixedQuery);
  const categories = useQuery(spendingCategoriesQuery);
  const [editing, setEditing] = useState<FixedOut | "new" | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [notice, setNotice] = useState("");

  const [failure, setFailure] = useState<string | null>(null);

  const remove = async (item: FixedOut) => {
    setFailure(null);
    try {
      await deleteFixed({ path: { fixed_id: item.id }, throwOnError: true });
      setNotice(f.deleted);
      await refreshSpending(queryClient);
    } catch (exc) {
      setFailure(detailSentence(exc) ?? t.errors.generic);
    } finally {
      setDeleting(null);
    }
  };

  if (!items.data || !categories.data) return <p>{t.common.loading}</p>;
  const nameOf = (id: string) => categories.data.find((c) => c.id === id)?.name ?? "";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-3xl font-black tracking-tight">{f.title}</h1>
        <div className="flex flex-wrap gap-3">
          <Link
            to="/spending"
            className="rounded-md border border-border bg-surface px-3 py-2 text-sm hover:border-accent"
          >
            {f.back}
          </Link>
          <Button onClick={() => setEditing("new")}>{f.add}</Button>
        </div>
      </div>
      <p className="max-w-3xl text-muted">{f.intro}</p>
      {editing && (
        <InView key={editing === "new" ? "new" : editing.id}>
          <FixedForm
            item={editing === "new" ? null : editing}
            categories={categories.data}
            onDone={(saved) => {
              setEditing(null);
              if (saved) setNotice(f.saved);
            }}
          />
        </InView>
      )}
      <ErrorAlert message={failure} />
      {notice && (
        <p className="rounded-md border border-accent px-3 py-2 text-sm" aria-live="polite">
          {notice}
        </p>
      )}
      {items.data.length === 0 ? (
        <p className="text-muted">{f.empty}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-sm" aria-label={f.caption}>
            <thead>
              <tr className="text-left text-muted">
                <th className="px-2 py-2 font-medium">{f.label}</th>
                <th className="px-2 py-2 font-medium">{f.category}</th>
                <th className="px-2 py-2 text-right font-medium">{f.amount}</th>
                <th className="px-2 py-2 font-medium">{f.frequency}</th>
                <th className="px-2 py-2 font-medium">{f.status}</th>
                <th className="px-2 py-2">
                  <span className="sr-only">{f.actions}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {items.data.map((item) => (
                <tr
                  key={item.id}
                  className={`border-t border-border ${item.paused ? "text-muted" : ""}`}
                >
                  <td className="px-2 py-2">{item.label}</td>
                  <td className="px-2 py-2">{nameOf(item.category_id)}</td>
                  <td className="px-2 py-2 text-right font-mono tabular-nums">
                    {formatEur(negate(item.amount))}
                  </td>
                  <td className="px-2 py-2">
                    {f.frequencies[item.frequency]} {f.dayOf(item.day)} ·{" "}
                    {f.since(monthLabel(item.first_month))}
                    {item.last_month && ` · ${f.until(monthLabel(item.last_month))}`}
                  </td>
                  <td className="px-2 py-2">{item.paused ? f.paused : f.active}</td>
                  <td className="px-2 py-2">
                    <div className="flex justify-end gap-2">
                      {deleting === item.id ? (
                        <>
                          <span className="self-center text-xs">{f.deleteAsk}</span>
                          <Button className="py-1" onClick={() => void remove(item)}>
                            {f.deleteConfirm}
                          </Button>
                          <Button
                            variant="ghost"
                            className="py-1"
                            onClick={() => setDeleting(null)}
                          >
                            {t.common.cancel}
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button
                            variant="ghost"
                            className="py-1"
                            aria-label={`${f.edit} ${item.label}`}
                            onClick={() => setEditing(item)}
                          >
                            {f.edit}
                          </Button>
                          <Button
                            variant="ghost"
                            className="py-1"
                            aria-label={`${t.common.delete} ${item.label}`}
                            onClick={() => setDeleting(item.id)}
                          >
                            {t.common.delete}
                          </Button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function FixedForm({
  item,
  categories,
  onDone,
}: {
  item: FixedOut | null;
  categories: SpendingCategoryOut[];
  onDone: (saved: boolean) => void;
}) {
  const { t } = useI18n();
  const f = t.spending.fixedPage;
  const queryClient = useQueryClient();
  const id = useId();
  const [label, setLabel] = useState(item?.label ?? "");
  const [category, setCategory] = useState(item?.category_id ?? "");
  const [amount, setAmount] = useState(item ? amountInputShort(negate(item.amount)) : "");
  const [frequency, setFrequency] = useState<FixedFrequency>(item?.frequency ?? "monthly");
  const [day, setDay] = useState(String(item?.day ?? 1));
  const [first, setFirst] = useState(item?.first_month ?? thisMonth());
  const [last, setLast] = useState(item?.last_month ?? "");
  const [paused, setPaused] = useState(item?.paused ?? false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const typed = parseEurInput(amount);
    if (typed === null || typed.startsWith("-") || !category || !label.trim()) {
      setError(t.errors.checkForm);
      return;
    }
    const body: FixedIn = {
      label: label.trim(),
      category_id: category,
      amount: negate(typed),
      frequency,
      day: Number(day),
      first_month: first,
      last_month: last || null,
      paused,
    };
    try {
      if (item) await replaceFixed({ path: { fixed_id: item.id }, body, throwOnError: true });
      else await createFixed({ body, throwOnError: true });
      await refreshSpending(queryClient);
      onDone(true);
    } catch (exc) {
      setError(detailSentence(exc) ?? t.errors.generic);
    }
  };

  const labelled = (key: string, text: string) => (
    <label htmlFor={`${id}-${key}`} className="text-sm font-medium">
      {text}
    </label>
  );

  return (
    <form
      onSubmit={(e) => void submit(e)}
      className="grid gap-4 rounded-lg border border-border bg-surface p-4 sm:grid-cols-2 lg:grid-cols-4"
    >
      <div className="flex flex-col gap-1">
        {labelled("label", f.label)}
        <input
          id={`${id}-label`}
          required
          maxLength={100}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className={field}
        />
      </div>
      <div className="flex flex-col gap-1">
        {labelled("category", f.category)}
        <select
          id={`${id}-category`}
          required
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className={field}
        >
          <option value="" disabled>
            {t.spending.grid.chooseCategory}
          </option>
          {/* A fixed expense is spent or put aside, never an income (F-FIX-1). */}
          <CategoryOptions categories={categories.filter((c) => c.kind !== "income")} />
        </select>
      </div>
      <div className="flex flex-col gap-1">
        {labelled("amount", f.amount)}
        <input
          id={`${id}-amount`}
          required
          inputMode="decimal"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className={`${field} text-right font-mono`}
        />
      </div>
      <div className="flex flex-col gap-1">
        {labelled("frequency", f.frequency)}
        <select
          id={`${id}-frequency`}
          value={frequency}
          onChange={(e) => setFrequency(e.target.value as FixedFrequency)}
          className={field}
        >
          {FREQUENCIES.map((value) => (
            <option key={value} value={value}>
              {f.frequencies[value]}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-1">
        {labelled("day", f.day)}
        <input
          id={`${id}-day`}
          type="number"
          min={1}
          max={31}
          required
          value={day}
          aria-describedby={`${id}-day-hint`}
          onChange={(e) => setDay(e.target.value)}
          className={field}
        />
        <span id={`${id}-day-hint`} className="text-xs text-muted">
          {f.dayHint}
        </span>
      </div>
      <div className="flex flex-col gap-1">
        {labelled("first", f.firstMonth)}
        <input
          id={`${id}-first`}
          type="month"
          required
          value={first}
          onChange={(e) => setFirst(e.target.value)}
          className={field}
        />
      </div>
      <div className="flex flex-col gap-1">
        {labelled("last", f.lastMonth)}
        <input
          id={`${id}-last`}
          type="month"
          value={last}
          onChange={(e) => setLast(e.target.value)}
          className={field}
        />
      </div>
      <label className="flex items-center gap-2 self-center text-sm">
        <input type="checkbox" checked={paused} onChange={(e) => setPaused(e.target.checked)} />
        {f.paused}
      </label>
      <div className="flex flex-col gap-3 sm:col-span-2 lg:col-span-4">
        <ErrorAlert message={error} />
        <div className="flex gap-3">
          <Button type="submit">{t.common.save}</Button>
          <Button variant="ghost" onClick={() => onDone(false)}>
            {t.common.cancel}
          </Button>
        </div>
      </div>
    </form>
  );
}
