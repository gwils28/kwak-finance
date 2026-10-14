import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, Fragment, useId, useState } from "react";
import {
  type AccountOut,
  createRecurring,
  deleteRecurring,
  dismissSuggestion,
  type Frequency,
  listRecurring,
  type OccurrenceOut,
  type RecurringIn,
  type RecurringOut,
  recurringSuggestions,
  type SuggestionOut,
  updateRecurring,
} from "../api/generated";
import { apiErrorMessage, detailSentence } from "../auth/errors";
import { InView } from "../components/InView";
import { Button, ErrorAlert, TextField } from "../components/ui";
import { useI18n } from "../i18n";
import { formatDate, todayIso } from "../lib/dates";
import { amountInput, formatEur, parseEurInput } from "../lib/money";
import { CategoryOptions, categoriesQuery } from "../transactions/categories";
import { type EntryDraft, TransactionForm } from "../transactions/TransactionForm";
import {
  entryDraft,
  StatusBadge,
  useCashAccounts,
  useSchedule,
  useSkip,
  weekdayName,
} from "./shared";

const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";
const FREQUENCIES: Frequency[] = ["weekly", "monthly", "quarterly", "yearly"];

/** What the item form starts from: an item to edit, a suggestion to follow, or nothing. */
type Draft = { item: RecurringOut } | { suggestion: SuggestionOut } | { blank: true };

/** F-REC-4: the recurring items, their next and past occurrences, and the suggestions. */
export function RecurringPage() {
  const { t } = useI18n();
  const [form, setForm] = useState<Draft | null>(null);
  const [entry, setEntry] = useState<EntryDraft | null>(null);
  const accounts = useCashAccounts();
  const items = useQuery({
    queryKey: ["recurring", "items"],
    queryFn: async () => (await listRecurring({ throwOnError: true })).data,
  });
  const suggestions = useQuery({
    queryKey: ["recurring", "suggestions"],
    queryFn: async () => (await recurringSuggestions({ throwOnError: true })).data,
  });
  const enter = (item: RecurringOut, occurrence: OccurrenceOut) => {
    setForm(null);
    setEntry(entryDraft(item, occurrence));
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-3xl font-black tracking-tight">{t.recurring.title}</h1>
        <Button
          onClick={() => {
            setEntry(null);
            setForm({ blank: true });
          }}
        >
          {t.recurring.add}
        </Button>
      </div>
      <p className="max-w-3xl text-sm text-muted">{t.recurring.intro}</p>
      {form && accounts && (
        <InView key={JSON.stringify(form)}>
          <ItemForm draft={form} accounts={accounts} onDone={() => setForm(null)} />
        </InView>
      )}
      {entry && accounts && (
        <InView key={JSON.stringify(entry)}>
          <TransactionForm draft={entry} accounts={accounts} onDone={() => setEntry(null)} />
        </InView>
      )}
      {suggestions.data && suggestions.data.length > 0 && (
        <Suggestions
          suggestions={suggestions.data}
          onFollow={(suggestion) => {
            setEntry(null);
            setForm({ suggestion });
          }}
        />
      )}
      {items.isError && <ErrorAlert message={t.recurring.loadFailed} />}
      {items.data?.length === 0 && <p className="text-muted">{t.recurring.empty}</p>}
      {items.data && items.data.length > 0 && (
        <ItemTable
          items={items.data}
          onEdit={(item) => {
            setEntry(null);
            setForm({ item });
          }}
          onEnter={enter}
        />
      )}
    </div>
  );
}

function Suggestions({
  suggestions,
  onFollow,
}: {
  suggestions: SuggestionOut[];
  onFollow: (suggestion: SuggestionOut) => void;
}) {
  const { t } = useI18n();
  const schedule = useSchedule();
  const queryClient = useQueryClient();
  const dismiss = useMutation({
    mutationFn: async (s: SuggestionOut) =>
      dismissSuggestion({
        body: { account_id: s.account_id, label: s.label },
        throwOnError: true,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["recurring", "suggestions"] }),
  });
  return (
    <section
      aria-label={t.recurring.suggestions}
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
    >
      <h2 className="text-lg font-bold">{t.recurring.suggestions}</h2>
      <p className="text-sm text-muted">{t.recurring.suggestionsHelp}</p>
      <ul className="divide-y divide-border">
        {suggestions.map((s) => (
          <li
            key={`${s.account_id}|${s.label}`}
            className="flex flex-wrap items-center justify-between gap-3 py-2"
          >
            <div className="flex flex-col">
              <span className="font-medium">{s.label}</span>
              <span className="text-xs text-muted">
                {s.account_name} · {schedule(s)} · {t.recurring.seen(s.count)}{" "}
                {formatDate(s.start_on)}
              </span>
            </div>
            <span className="flex items-center gap-3">
              <span className="tabular">
                {s.estimated ? t.recurring.approx(formatEur(s.amount)) : formatEur(s.amount)}
              </span>
              <Button aria-label={t.recurring.followNamed(s.label)} onClick={() => onFollow(s)}>
                {t.recurring.follow}
              </Button>
              <Button
                variant="ghost"
                aria-label={t.recurring.dismissNamed(s.label)}
                disabled={dismiss.isPending}
                onClick={() => dismiss.mutate(s)}
              >
                {t.recurring.dismiss}
              </Button>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ItemTable({
  items,
  onEdit,
  onEnter,
}: {
  items: RecurringOut[];
  onEdit: (item: RecurringOut) => void;
  onEnter: (item: RecurringOut, occurrence: OccurrenceOut) => void;
}) {
  const { t } = useI18n();
  const schedule = useSchedule();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["recurring"] });
  const pause = useMutation({
    mutationFn: async ({ id, paused }: { id: string; paused: boolean }) =>
      updateRecurring({ path: { item_id: id }, body: { paused }, throwOnError: true }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: async (id: string) =>
      deleteRecurring({ path: { item_id: id }, throwOnError: true }),
    onSuccess: async () => {
      setConfirming(null);
      await refresh();
    },
  });

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table aria-label={t.recurring.title} className="w-full text-sm">
        <thead className="text-left text-muted">
          <tr>
            <th className="px-3 py-2 font-medium">{t.recurring.item}</th>
            <th className="px-3 py-2 font-medium">{t.recurring.schedule}</th>
            <th className="px-3 py-2 text-right font-medium">{t.recurring.amount}</th>
            <th className="px-3 py-2 font-medium">{t.recurring.next}</th>
            <th className="px-3 py-2">
              <span className="sr-only">{t.recurring.actions}</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((item) => {
            const late = item.recent.find((o) => o.status === "late");
            const amount = item.next?.expected ?? item.amount;
            return (
              <Fragment key={item.id}>
                <tr>
                  <td className="px-3 py-2">
                    <span className="font-medium">{item.label}</span>
                    {item.paused && (
                      <span className="ml-2 rounded-md border border-border px-2 py-0.5 text-xs text-muted">
                        {t.recurring.paused}
                      </span>
                    )}
                    <span className="block text-xs text-muted">
                      {item.account_name}
                      {item.category_name && ` · ${item.category_name}`}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    {schedule(item)}
                    {item.end_on && (
                      <span className="block text-xs text-muted">
                        {t.recurring.until(formatDate(item.end_on))}
                      </span>
                    )}
                  </td>
                  <td
                    className={`tabular whitespace-nowrap px-3 py-2 text-right ${
                      amount.startsWith("-") ? "" : "text-positive"
                    }`}
                  >
                    {item.estimated ? t.recurring.approx(formatEur(amount)) : formatEur(amount)}
                  </td>
                  <td className="px-3 py-2">
                    <span className="flex flex-col items-start gap-1">
                      {late && (
                        <span className="flex items-center gap-2 whitespace-nowrap">
                          {formatDate(late.due)} <StatusBadge status="late" />
                          <Button
                            variant="ghost"
                            aria-label={t.recurring.enterNamed(item.label, formatDate(late.due))}
                            onClick={() => onEnter(item, late)}
                          >
                            {t.recurring.enterIt}
                          </Button>
                        </span>
                      )}
                      {item.next ? (
                        <span className="whitespace-nowrap">
                          {formatDate(item.next.due)} <StatusBadge status={item.next.status} />
                        </span>
                      ) : (
                        !late && <span className="text-muted">{t.recurring.noNext}</span>
                      )}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-right">
                    <span className="flex items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        aria-label={t.recurring.historyOf(item.label)}
                        aria-expanded={open === item.id}
                        onClick={() => setOpen(open === item.id ? null : item.id)}
                      >
                        {t.recurring.history}
                      </Button>
                      <Button
                        variant="ghost"
                        aria-label={(item.paused
                          ? t.recurring.resumeNamed
                          : t.recurring.pauseNamed)(item.label)}
                        disabled={pause.isPending}
                        onClick={() => pause.mutate({ id: item.id, paused: !item.paused })}
                      >
                        {item.paused ? t.recurring.resume : t.recurring.pause}
                      </Button>
                      <Button
                        variant="ghost"
                        aria-label={t.recurring.editNamed(item.label)}
                        onClick={() => onEdit(item)}
                      >
                        {t.common.edit}
                      </Button>
                      {confirming === item.id ? (
                        <>
                          <Button
                            variant="ghost"
                            className="border-negative text-negative"
                            title={t.recurring.deleteHelp}
                            disabled={remove.isPending}
                            onClick={() => remove.mutate(item.id)}
                          >
                            {t.recurring.confirmDelete}
                          </Button>
                          <Button variant="ghost" onClick={() => setConfirming(null)}>
                            {t.common.cancel}
                          </Button>
                        </>
                      ) : (
                        <Button
                          variant="ghost"
                          aria-label={t.recurring.deleteNamed(item.label)}
                          onClick={() => setConfirming(item.id)}
                        >
                          {t.common.delete}
                        </Button>
                      )}
                    </span>
                  </td>
                </tr>
                {open === item.id && (
                  <tr>
                    <td colSpan={5} className="bg-bg px-3 py-2">
                      <History item={item} onEnter={(o) => onEnter(item, o)} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** The item's past occurrences, newest first: skip or enter a late one, restore a skipped one. */
function History({
  item,
  onEnter,
}: {
  item: RecurringOut;
  onEnter: (occurrence: OccurrenceOut) => void;
}) {
  const { t } = useI18n();
  const skip = useSkip();
  if (item.recent.length === 0) return <p className="text-muted">{t.recurring.noHistory}</p>;
  const row = (o: OccurrenceOut) => {
    const date = formatDate(o.due);
    return (
      <li key={o.due} className="flex flex-wrap items-center gap-3 py-1">
        <span className="w-28">{date}</span>
        <StatusBadge status={o.status} />
        <span className="tabular">{formatEur(o.expected)}</span>
        {o.status === "late" && (
          <>
            <Button
              variant="ghost"
              aria-label={t.recurring.enterNamed(item.label, date)}
              onClick={() => onEnter(o)}
            >
              {t.recurring.enterIt}
            </Button>
            <Button
              variant="ghost"
              aria-label={t.recurring.skipNamed(item.label, date)}
              disabled={skip.isPending}
              onClick={() => skip.mutate({ itemId: item.id, due: o.due, skip: true })}
            >
              {t.recurring.skip}
            </Button>
          </>
        )}
        {o.status === "skipped" && (
          <Button
            variant="ghost"
            aria-label={t.recurring.unskipNamed(item.label, date)}
            disabled={skip.isPending}
            onClick={() => skip.mutate({ itemId: item.id, due: o.due, skip: false })}
          >
            {t.recurring.unskip}
          </Button>
        )}
      </li>
    );
  };
  return (
    <ul aria-label={t.recurring.historyOf(item.label)} className="text-sm">
      {item.recent.map(row)}
    </ul>
  );
}

/** The form's starting values; amounts as the API sends them, signed strings. */
type Initial = Omit<RecurringIn, "amount"> & { amount: string };

function initial(draft: Draft, accounts: AccountOut[]): Initial {
  if ("item" in draft) return draft.item;
  if ("suggestion" in draft) {
    const s = draft.suggestion;
    return { ...s, start_on: s.start_on, end_on: null, paused: false };
  }
  return {
    account_id: accounts[0]?.id ?? "",
    category_id: null,
    label: "",
    amount: "",
    frequency: "monthly",
    day: Number(todayIso().slice(8, 10)),
    start_on: todayIso(),
    end_on: null,
    estimated: false,
    paused: false,
  };
}

function ItemForm({
  draft,
  accounts,
  onDone,
}: {
  draft: Draft;
  accounts: AccountOut[];
  onDone: () => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const categories = useQuery(categoriesQuery);
  const editing = "item" in draft ? draft.item : null;
  const start = initial(draft, accounts);
  const [accountId, setAccountId] = useState(start.account_id);
  const [label, setLabel] = useState(start.label);
  const [kind, setKind] = useState<"expense" | "income">(
    start.amount && !start.amount.startsWith("-") ? "income" : "expense",
  );
  const [amount, setAmount] = useState(
    start.amount ? amountInput(start.amount.replace("-", "")) : "",
  );
  const [estimated, setEstimated] = useState(start.estimated ?? false);
  const [frequency, setFrequency] = useState<Frequency>(start.frequency);
  const [day, setDay] = useState(String(start.day));
  const [startOn, setStartOn] = useState(start.start_on);
  const [endOn, setEndOn] = useState(start.end_on ?? "");
  const [categoryId, setCategoryId] = useState(start.category_id ?? "");
  const [invalid, setInvalid] = useState(false);
  const ids = {
    account: useId(),
    kind: useId(),
    frequency: useId(),
    day: useId(),
    category: useId(),
  };

  const save = useMutation({
    mutationFn: async (signed: string) => {
      const body = {
        account_id: accountId,
        category_id: categoryId || null,
        label,
        amount: signed,
        frequency,
        day: Number(day),
        start_on: startOn,
        end_on: endOn || null,
        estimated,
      };
      const { data, error, response } = editing
        ? await updateRecurring({ path: { item_id: editing.id }, body })
        : await createRecurring({ body: { ...body, paused: false } });
      if (!data) {
        throw new Error(
          response?.status === 422
            ? (detailSentence(error) ?? t.errors.checkForm)
            : apiErrorMessage(t, response),
        );
      }
      return data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["recurring"] });
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
  const changeFrequency = (next: Frequency) => {
    // A weekday (0-6) and a day of the month (1-31) do not carry over.
    if ((next === "weekly") !== (frequency === "weekly")) {
      setDay(next === "weekly" ? "0" : startOn.slice(8, 10).replace(/^0/, ""));
    }
    setFrequency(next);
  };

  const title = editing ? t.recurring.editTitle : t.recurring.newTitle;
  return (
    <form
      aria-label={title}
      onSubmit={submit}
      className="grid gap-4 rounded-lg border border-accent bg-surface p-4 sm:grid-cols-2"
    >
      <h2 className="text-lg font-bold sm:col-span-2">{title}</h2>
      <div className="flex flex-col gap-1">
        <label htmlFor={ids.account} className="text-sm font-medium">
          {t.recurring.account}
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
      <div className="flex flex-col gap-1">
        <TextField
          label={t.recurring.label}
          required
          maxLength={100}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
        />
        <p className="text-xs text-muted">{t.recurring.labelHelp}</p>
      </div>
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
        label={t.recurring.amountEur}
        inputMode="decimal"
        required
        className="tabular"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
      />
      <label className="flex items-center gap-2 text-sm sm:col-span-2">
        <input
          type="checkbox"
          checked={estimated}
          onChange={(e) => setEstimated(e.target.checked)}
        />
        {t.recurring.estimated}
      </label>
      <div className="flex flex-col gap-1">
        <label htmlFor={ids.frequency} className="text-sm font-medium">
          {t.recurring.frequency}
        </label>
        <select
          id={ids.frequency}
          className={fieldClass}
          value={frequency}
          onChange={(e) => changeFrequency(e.target.value as Frequency)}
        >
          {FREQUENCIES.map((f) => (
            <option key={f} value={f}>
              {t.recurring.frequencies[f]}
            </option>
          ))}
        </select>
      </div>
      {frequency === "weekly" ? (
        <div className="flex flex-col gap-1">
          <label htmlFor={ids.day} className="text-sm font-medium">
            {t.recurring.weekday}
          </label>
          <select
            id={ids.day}
            className={fieldClass}
            value={day}
            onChange={(e) => setDay(e.target.value)}
          >
            {[0, 1, 2, 3, 4, 5, 6].map((d) => (
              <option key={d} value={d}>
                {weekdayName(d)}
              </option>
            ))}
          </select>
        </div>
      ) : (
        <div className="flex flex-col gap-1">
          <TextField
            label={t.recurring.dayOfMonth}
            type="number"
            min={1}
            max={31}
            required
            value={day}
            onChange={(e) => setDay(e.target.value)}
          />
          <p className="text-xs text-muted">{t.recurring.dayHelp}</p>
        </div>
      )}
      <TextField
        label={t.recurring.start}
        type="date"
        required
        value={startOn}
        onChange={(e) => setStartOn(e.target.value)}
      />
      <TextField
        label={t.recurring.end}
        type="date"
        value={endOn}
        onChange={(e) => setEndOn(e.target.value)}
      />
      <div className="flex flex-col gap-1 sm:col-span-2">
        <label htmlFor={ids.category} className="text-sm font-medium">
          {t.recurring.category}
        </label>
        <select
          id={ids.category}
          className={fieldClass}
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
        >
          <option value="">{t.recurring.noCategory}</option>
          <CategoryOptions categories={categories.data ?? []} />
        </select>
      </div>
      <div className="sm:col-span-2">
        <ErrorAlert message={invalid ? t.recurring.invalidAmount : (save.error?.message ?? null)} />
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
