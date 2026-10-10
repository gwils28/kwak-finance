import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useId, useState } from "react";
import { closePlan, createPlan, deletePlan, type PlanOut, updatePlan } from "../api/generated";
import { apiErrorMessage, detailSentence } from "../auth/errors";
import { Button } from "../components/ui";
import { useI18n } from "../i18n";
import { formatDate } from "../lib/dates";
import { amountInputShort, parseEurInput } from "../lib/money";
import { monthLabel, thisMonth } from "../lib/months";
import {
  covering,
  editableUntil,
  monthsBetween,
  type Period,
  parsePeriod,
  periodsPerYear,
  periodText,
  suggestedPeriod,
} from "../lib/plans";

export const PLANS_KEY = ["budget", "plans"];

const fieldClass = "rounded-md border border-border bg-surface px-3 py-2 disabled:opacity-60";
const labelClass = "flex flex-col gap-1 text-sm font-medium";

/** "Q4 2026" (en) or "T4 2026" (fr). */
export function usePeriodLabel() {
  const { t } = useI18n();
  return (period: string) => {
    const { kind, year, number } = parsePeriod(period);
    return t.budget.plan.periodLabel(kind, year, number);
  };
}

type Throws = { data?: unknown; error?: unknown; response?: Response };

/** A plan mutation: API refusals become the error shown above the matrix. */
function usePlanMutation<A, R>(
  call: (arg: A) => Promise<Throws & { data?: R }>,
  onError: (message: string | null) => void,
  onDone?: (result: R) => void,
) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (arg: A) => {
      const { data, error, response } = await call(arg);
      if (!response?.ok) throw new Error(detailSentence(error) ?? apiErrorMessage(t, response));
      return data as R;
    },
    onSuccess: (result) => {
      onError(null);
      onDone?.(result);
      return queryClient.invalidateQueries({ queryKey: ["budget"] });
    },
    onError: (exc) => onError(exc.message),
  });
}

export function PlanPanel({
  plans,
  selected,
  onSelect,
  onError,
}: {
  plans: PlanOut[];
  selected: PlanOut | undefined;
  onSelect: (id: string | null) => void;
  onError: (message: string | null) => void;
}) {
  const { t } = useI18n();
  const label = usePeriodLabel();
  const selectId = useId();
  const [open, setOpen] = useState<"new" | "close" | "delete" | null>(null);
  const month = thisMonth();
  const missing = plans.length > 0 && !covering(plans, month);

  return (
    <section
      aria-label={t.budget.plan.section}
      className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4"
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        {selected ? (
          <label htmlFor={selectId} className={labelClass}>
            {t.budget.plan.select}
            <select
              id={selectId}
              className={fieldClass}
              value={selected.id}
              onChange={(e) => {
                setOpen(null);
                onSelect(e.target.value);
              }}
            >
              {plans.map((p) => (
                <option key={p.id} value={p.id}>
                  {`${label(p.period)} · ${t.budget.plan.range(monthLabel(p.start), monthLabel(p.end))}`}
                  {p.closed_early ? ` · ${t.budget.plan.closedEarlyTag}` : ""}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <h2 className="text-lg font-bold">{t.budget.plan.section}</h2>
        )}
        <div className="flex flex-wrap gap-2">
          {selected && (
            <Link
              to="/budget/review"
              search={{ plan: selected.id }}
              className="rounded-md bg-accent px-3 py-2 text-sm font-semibold text-bg hover:opacity-90"
            >
              {t.review.link}
            </Link>
          )}
          <Button variant="ghost" onClick={() => setOpen(open === "new" ? null : "new")}>
            {t.budget.plan.newPlan}
          </Button>
          {selected &&
            monthsBetween(selected.start, selected.end).length > 1 &&
            selected.end >= month && (
              <Button variant="ghost" onClick={() => setOpen(open === "close" ? null : "close")}>
                {t.budget.plan.closeEarly}
              </Button>
            )}
          {selected?.editable && (
            <Button variant="ghost" onClick={() => setOpen(open === "delete" ? null : "delete")}>
              {t.budget.plan.delete}
            </Button>
          )}
        </div>
      </div>
      {plans.length === 0 && <p className="text-sm text-muted">{t.budget.plan.none}</p>}
      {missing && (
        <p className="text-sm text-muted">{t.budget.plan.noneCovering(monthLabel(month))}</p>
      )}
      {selected && <PlanStatus plan={selected} />}
      {selected && <PlanFields key={selected.id} plan={selected} onError={onError} />}
      {open === "new" && (
        <NewPlanForm
          plans={plans}
          onError={onError}
          onDone={(plan) => {
            setOpen(null);
            onSelect(plan.id);
          }}
          onCancel={() => setOpen(null)}
        />
      )}
      {open === "close" && selected && (
        <CloseForm
          plan={selected}
          onError={onError}
          onDone={(rest) => {
            setOpen(null);
            onSelect(rest.id);
          }}
          onCancel={() => setOpen(null)}
        />
      )}
      {open === "delete" && selected && (
        <DeleteConfirm
          plan={selected}
          onError={onError}
          onDone={() => {
            setOpen(null);
            onSelect(null);
          }}
          onCancel={() => setOpen(null)}
        />
      )}
    </section>
  );
}

function PlanStatus({ plan }: { plan: PlanOut }) {
  const { t } = useI18n();
  const until = formatDate(editableUntil(plan));
  let text: string;
  if (plan.closed_early) text = t.budget.plan.closedEarly(monthLabel(plan.end));
  else if (plan.editable) text = t.budget.plan.editableUntil(until);
  else if (plan.end < thisMonth()) text = t.budget.plan.over;
  else text = t.budget.plan.locked(until);
  return (
    <div className="text-sm">
      <p>{text}</p>
      {plan.closed_early && plan.close_reason && (
        <p className="text-muted">{t.budget.plan.reason(plan.close_reason)}</p>
      )}
    </div>
  );
}

function PlanFields({ plan, onError }: { plan: PlanOut; onError: (m: string | null) => void }) {
  const { t } = useI18n();
  const ids = { income: useId(), note: useId() };
  const initialIncome = plan.expected_income === null ? "" : amountInputShort(plan.expected_income);
  const [income, setIncome] = useState(initialIncome);
  const [note, setNote] = useState(plan.note ?? "");
  const save = usePlanMutation(
    (body: { expected_income?: string | null; note?: string | null }) =>
      updatePlan({ path: { plan_id: plan.id }, body }),
    onError,
  );

  const commitIncome = () => {
    if (income.trim() === initialIncome) return;
    if (income.trim() === "") {
      save.mutate({ expected_income: null });
      return;
    }
    const amount = parseEurInput(income);
    if (amount === null || amount.startsWith("-")) {
      onError(t.budget.plan.invalidIncome);
      return;
    }
    save.mutate({ expected_income: amount });
  };
  const commitNote = () => {
    if (note.trim() !== (plan.note ?? "")) save.mutate({ note: note.trim() || null });
  };

  return (
    <div className="grid gap-3 sm:grid-cols-[14rem_1fr]">
      <label htmlFor={ids.income} className={labelClass}>
        {t.budget.plan.expectedIncome}
        <input
          id={ids.income}
          inputMode="decimal"
          className={`tabular text-right ${fieldClass}`}
          value={income}
          disabled={!plan.editable}
          title={plan.editable ? undefined : t.budget.plan.lockedTarget}
          onChange={(e) => setIncome(e.target.value)}
          onBlur={commitIncome}
        />
      </label>
      <label htmlFor={ids.note} className={labelClass}>
        {t.budget.plan.note}
        <input
          id={ids.note}
          maxLength={500}
          className={fieldClass}
          placeholder={t.budget.plan.notePlaceholder}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          onBlur={commitNote}
        />
      </label>
    </div>
  );
}

const formClass = "flex flex-col gap-3 rounded-md border border-border p-3";

function NewPlanForm({
  plans,
  onError,
  onDone,
  onCancel,
}: {
  plans: PlanOut[];
  onError: (m: string | null) => void;
  onDone: (plan: PlanOut) => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  const ids = { kind: useId(), year: useId(), number: useId() };
  const [period, setPeriod] = useState<Period>(() => suggestedPeriod(plans, thisMonth()));
  const create = usePlanMutation(
    (p: Period) => createPlan({ body: { period: periodText(p) } }),
    onError,
    onDone,
  );
  const count = periodsPerYear(period.kind);
  const number = (n: number) => t.budget.plan.periodLabel(period.kind, period.year, n);

  return (
    <form
      className={formClass}
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate(period);
      }}
    >
      <div className="flex flex-wrap items-end gap-3">
        <label htmlFor={ids.kind} className={labelClass}>
          {t.budget.plan.kind}
          <select
            id={ids.kind}
            className={fieldClass}
            value={period.kind}
            onChange={(e) => {
              const kind = e.target.value as Period["kind"];
              setPeriod({ ...period, kind, number: Math.min(period.number, periodsPerYear(kind)) });
            }}
          >
            {(["quarter", "semester", "year"] as const).map((k) => (
              <option key={k} value={k}>
                {t.budget.plan.kinds[k]}
              </option>
            ))}
          </select>
        </label>
        {count > 1 && (
          <label htmlFor={ids.number} className={labelClass}>
            {t.budget.plan.number}
            <select
              id={ids.number}
              className={fieldClass}
              value={period.number}
              onChange={(e) => setPeriod({ ...period, number: Number(e.target.value) })}
            >
              {Array.from({ length: count }, (_, i) => i + 1).map((n) => (
                <option key={n} value={n}>
                  {number(n)}
                </option>
              ))}
            </select>
          </label>
        )}
        <label htmlFor={ids.year} className={labelClass}>
          {t.budget.plan.year}
          <input
            id={ids.year}
            type="number"
            min={2000}
            max={2100}
            className={`w-28 ${fieldClass}`}
            value={period.year}
            onChange={(e) => setPeriod({ ...period, year: Number(e.target.value) })}
          />
        </label>
      </div>
      <p className="text-sm text-muted">{t.budget.plan.prefilled}</p>
      <div className="flex gap-2">
        <Button type="submit" disabled={create.isPending}>
          {t.budget.plan.create}
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          {t.budget.plan.cancel}
        </Button>
      </div>
    </form>
  );
}

function CloseForm({
  plan,
  onError,
  onDone,
  onCancel,
}: {
  plan: PlanOut;
  onError: (m: string | null) => void;
  onDone: (rest: PlanOut) => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  const ids = { month: useId(), reason: useId() };
  const options = monthsBetween(plan.start, plan.end).slice(0, -1);
  const [last, setLast] = useState(options.includes(thisMonth()) ? thisMonth() : options[0]);
  const [reason, setReason] = useState("");
  const close = usePlanMutation(
    () =>
      closePlan({
        path: { plan_id: plan.id },
        body: { last_month: last as string, reason: reason.trim() || null },
      }),
    onError,
    onDone,
  );

  return (
    <form
      className={formClass}
      onSubmit={(e) => {
        e.preventDefault();
        close.mutate(undefined);
      }}
    >
      <p className="text-sm text-muted">{t.budget.plan.closeHelp}</p>
      <div className="flex flex-wrap items-end gap-3">
        <label htmlFor={ids.month} className={labelClass}>
          {t.budget.plan.lastMonth}
          <select
            id={ids.month}
            className={fieldClass}
            value={last}
            onChange={(e) => setLast(e.target.value)}
          >
            {options.map((m) => (
              <option key={m} value={m}>
                {monthLabel(m)}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor={ids.reason} className={`${labelClass} min-w-64 flex-1`}>
          {t.budget.plan.closeReason}
          <input
            id={ids.reason}
            maxLength={500}
            className={fieldClass}
            placeholder={t.budget.plan.closeReasonPlaceholder}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </label>
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={close.isPending}>
          {t.budget.plan.confirmClose}
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          {t.budget.plan.cancel}
        </Button>
      </div>
    </form>
  );
}

function DeleteConfirm({
  plan,
  onError,
  onDone,
  onCancel,
}: {
  plan: PlanOut;
  onError: (m: string | null) => void;
  onDone: () => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  const remove = usePlanMutation(() => deletePlan({ path: { plan_id: plan.id } }), onError, onDone);
  return (
    <div className="flex gap-2">
      <Button disabled={remove.isPending} onClick={() => remove.mutate(undefined)}>
        {t.budget.plan.confirmDelete}
      </Button>
      <Button variant="ghost" onClick={onCancel}>
        {t.budget.plan.cancel}
      </Button>
    </div>
  );
}
