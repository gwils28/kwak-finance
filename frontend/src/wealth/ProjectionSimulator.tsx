/**
 * The projection simulator (F-SIM-3, F-SIM-5): the monthly contributions and the settings on
 * the left, the answer on the right, recomputed by the API as they change (nothing saved but
 * by "Save"); then reaching an amount, the what-ifs, the categories, and folded the advanced
 * assumptions and the method.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, type ReactNode, useEffect, useId, useMemo, useState } from "react";
import {
  type AssumptionsOut,
  type CategoryAssumptionOut,
  getAssumptions,
  type RunIn,
  type RunOut,
  runProjection,
  type Scope,
  setContributions,
  type WhatIfIn,
} from "../api/generated";
import { detailSentence } from "../auth/errors";
import { Button, ErrorAlert } from "../components/ui";
import { Card, DataTable } from "../dashboard/charts";
import { useI18n } from "../i18n";
import {
  amountInputShort,
  formatEurHundreds,
  formatEurWhole,
  formatPercent,
  formatRate,
  parseEurInput,
  parsePercentInput,
  percentInput,
} from "../lib/money";
import { monthLabel, shiftMonth, thisMonth } from "../lib/months";
import { ASSUMPTIONS_KEY, ProjectionAssumptions } from "./ProjectionAssumptions";
import { CategoriesChart, ProjectionChart, type View, WHAT_IF_COLOURS } from "./projectionCharts";

const RUN_KEY = ["projection", "run"];
const DEBOUNCE_MS = 350;
const DEFAULT_YEARS = 20;
const VOLATILE = 0.4;
const field = "w-full rounded-md border border-border bg-surface px-2 py-1 text-right tabular";

type Row = { key: number; categoryId: string; amount: string; indexed: boolean; ret: string };
type WhatIfDraft = {
  on: boolean;
  savings: string;
  inflation: string;
  categoryId: string;
  ret: string;
  volatility: string;
};
const NO_WHAT_IF: WhatIfDraft = {
  on: false,
  savings: "",
  inflation: "",
  categoryId: "",
  ret: "",
  volatility: "",
};

let nextKey = 1;

/** A return typed differently from the category's saved one ("0.07" is "0.070"). */
function changedReturn(ret: string | null, category: CategoryAssumptionOut | undefined): boolean {
  return ret !== null && category !== undefined && Number(ret) !== Number(category.ret);
}

function savedRows(a: AssumptionsOut): Row[] {
  return a.categories
    .filter((c) => c.contribution !== null)
    .map((c) => ({
      key: nextKey++,
      categoryId: c.id,
      amount: amountInputShort(c.contribution ?? "0"),
      indexed: c.contribution_indexed,
      ret: percentInput(c.ret),
    }));
}

/** `value` once it has stayed the same (by content) for `ms`. */
function useDebounced<T>(value: T, ms: number): T {
  const text = JSON.stringify(value);
  const [shown, setShown] = useState(text);
  useEffect(() => {
    const timer = setTimeout(() => setShown(text), ms);
    return () => clearTimeout(timer);
  }, [text, ms]);
  return useMemo(() => JSON.parse(shown) as T, [shown]);
}

async function unwrap<D>(request: Promise<{ data?: D; error?: unknown }>): Promise<D> {
  const { data, error } = await request;
  if (error || data === undefined) throw error;
  return data;
}

/** A chance to the whole percent, never 0 nor 100 (F-SIM-5). */
function useChance() {
  const { t } = useI18n();
  return (chance: string) => {
    const n = Number(chance);
    if (n < 0.01) return t.projection.chanceLow;
    if (n > 0.99) return t.projection.chanceHigh;
    return formatPercent(chance);
  };
}

function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: [T, string][];
  onChange: (value: T) => void;
}) {
  return (
    <fieldset className="flex flex-col gap-1">
      <legend className="mb-1 text-xs font-medium text-muted">{label}</legend>
      <div className="flex overflow-hidden rounded-md border border-border">
        {options.map(([v, text]) => (
          <button
            key={v}
            type="button"
            aria-pressed={value === v}
            onClick={() => onChange(v)}
            className={`flex-1 px-2 py-1 text-sm ${
              value === v ? "bg-accent font-semibold text-surface" : "text-muted hover:text-fg"
            }`}
          >
            {text}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

export function ProjectionSimulator() {
  const { t } = useI18n();
  const p = t.projection;
  const queryClient = useQueryClient();
  const chanceText = useChance();
  const assumptions = useQuery({
    queryKey: ASSUMPTIONS_KEY,
    queryFn: async () => (await getAssumptions({ throwOnError: true })).data,
  });

  const [rows, setRows] = useState<Row[] | null>(null);
  const [years, setYears] = useState(DEFAULT_YEARS);
  const [scope, setScope] = useState<Scope>("household");
  const [euros, setEuros] = useState<"today" | "current">("today");
  const [view, setView] = useState<View>("parts");
  const [rate, setRate] = useState("4");
  const [amount, setAmount] = useState<string | null>(null);
  const [reachMonth, setReachMonth] = useState(shiftMonth(thisMonth(), DEFAULT_YEARS * 12));
  const [whatIfs, setWhatIfs] = useState<WhatIfDraft[]>([NO_WHAT_IF, NO_WHAT_IF]);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedNote, setSavedNote] = useState(false);

  const categories = assumptions.data?.categories ?? [];
  const byId = useMemo(() => new Map(categories.map((c) => [c.id, c])), [categories]);
  useEffect(() => {
    if (assumptions.data && rows === null) setRows(savedRows(assumptions.data));
  }, [assumptions.data, rows]);
  const draft = rows ?? [];

  // Each row's validity: an amount from 1 to 100,000 and a return to 0.1 %.
  const parsed = draft.map((r) => {
    const amountValue = parseEurInput(r.amount);
    const ret = parsePercentInput(r.ret);
    return {
      row: r,
      amount:
        amountValue !== null && Number(amountValue) >= 1 && Number(amountValue) <= 100_000
          ? amountValue
          : null,
      ret: ret !== null && Number(ret) > -1 && Number(ret) <= 1 ? ret : null,
    };
  });
  const valid = parsed.every((x) => x.amount !== null && x.ret !== null);
  const saved = assumptions.data ? savedRows(assumptions.data) : [];
  const dirty =
    rows !== null &&
    JSON.stringify(draft.map(({ key: _, ...r }) => r)) !==
      JSON.stringify(saved.map(({ key: _, ...r }) => r));
  const total = parsed.reduce((sum, x) => sum + Number(x.amount ?? 0), 0);

  const rateShare = parsePercentInput(rate);
  const rateValid = rateShare !== null && Number(rateShare) >= 0.02 && Number(rateShare) <= 0.05;

  const whatIfBodies: (WhatIfIn | null)[] = whatIfs.map((w) => {
    if (!w.on) return null;
    const savings = w.savings ? parseEurInput(w.savings) : null;
    const inflation = w.inflation ? parsePercentInput(w.inflation) : null;
    const ret = w.ret ? parsePercentInput(w.ret) : null;
    const volatility = w.volatility ? parsePercentInput(w.volatility) : null;
    if (
      (w.savings && !savings) ||
      (w.inflation && !inflation) ||
      (w.ret && !ret) ||
      (w.volatility && !volatility)
    ) {
      return null;
    }
    return {
      savings,
      inflation,
      category_id: w.categoryId || null,
      ret,
      volatility,
    };
  });
  const whatIfInvalid = whatIfs.map((w, k) => w.on && whatIfBodies[k] === null);
  const sentWhatIfs = whatIfBodies.filter((w): w is WhatIfIn => w !== null);

  const amountValue = amount === null ? null : parseEurInput(amount);
  const body: RunIn | null =
    rows === null || !valid || !rateValid
      ? null
      : {
          scope,
          years,
          today: euros === "today",
          contributions: parsed.map((x) => ({
            category_id: x.row.categoryId,
            amount: x.amount ?? "0",
            indexed: x.row.indexed,
          })),
          returns: parsed
            .filter((x) => changedReturn(x.ret, byId.get(x.row.categoryId)))
            .map((x) => ({ category_id: x.row.categoryId, ret: x.ret ?? "0" })),
          amount: amountValue,
          reach_month: amountValue ? reachMonth : null,
          withdrawal_rate: rateShare ?? "0.04",
          what_ifs: sentWhatIfs,
        };
  const debounced = useDebounced(body, DEBOUNCE_MS);
  const run = useQuery({
    queryKey: [...RUN_KEY, debounced],
    enabled: debounced !== null,
    placeholderData: keepPreviousData,
    retry: false,
    queryFn: async (): Promise<RunOut | "no-wealth"> => {
      const { data, error, response } = await runProjection({ body: debounced as RunIn });
      if (response?.status === 404) return "no-wealth";
      if (error || data === undefined) throw error;
      return data;
    },
  });
  const noWealth = run.data === "no-wealth";
  const result: RunOut | undefined = run.data === "no-wealth" ? undefined : run.data;

  // The amount to reach starts at twice today's net worth, to the €10,000 above.
  useEffect(() => {
    if (amount === null && result) {
      const net = Number(result.months[0]?.p50 ?? 0);
      setAmount(String(net > 0 ? Math.ceil((net * 2) / 10_000) * 10_000 : 100_000));
    }
  }, [amount, result]);

  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        setContributions({
          body: {
            contributions: parsed.map((x) => ({
              category_id: x.row.categoryId,
              amount: x.amount ?? "0",
              indexed: x.row.indexed,
              ret: changedReturn(x.ret, byId.get(x.row.categoryId)) ? x.ret : null,
            })),
          },
        }),
      ),
    onSuccess: (next) => {
      queryClient.setQueryData(ASSUMPTIONS_KEY, next);
      setRows(savedRows(next));
      setSaveError(null);
      setSavedNote(true);
    },
    onError: (failure) => setSaveError(detailSentence(failure) ?? t.errors.generic),
  });

  const update = (key: number, change: Partial<Row>) => {
    setSavedNote(false);
    setRows(draft.map((r) => (r.key === key ? { ...r, ...change } : r)));
  };
  const used = new Set(draft.map((r) => r.categoryId));
  const free = categories.filter((c) => !used.has(c.id));
  const add = () => {
    const next = free[0];
    if (!next) return;
    setSavedNote(false);
    setRows([
      ...draft,
      {
        key: nextKey++,
        categoryId: next.id,
        amount: "100",
        indexed: true,
        ret: percentInput(next.ret),
      },
    ]);
  };

  const months = result?.months ?? [];
  const last = months.at(-1);
  const whatIfNames = [p.whatIf(1), p.whatIf(2)];
  const shownWhatIfs = whatIfs.map((w, k) => {
    if (!w.on || !whatIfBodies[k] || !result) return null;
    const index = whatIfBodies.slice(0, k + 1).filter((b) => b !== null).length - 1;
    return result.what_ifs[index] ?? null;
  });

  return (
    <div className="flex flex-col gap-6">
      <p className="max-w-3xl text-muted">{p.intro}</p>

      <section
        aria-label={p.settings}
        className="grid overflow-hidden rounded-lg border border-border bg-surface lg:grid-cols-[minmax(25rem,27rem)_1fr]"
      >
        <div className="flex flex-col gap-5 border-border p-4 max-lg:border-b lg:border-r">
          <Contributions
            parsed={parsed}
            categories={categories}
            byId={byId}
            free={free.length > 0}
            total={total}
            result={result}
            scope={scope}
            onUpdate={update}
            onRemove={(key) => {
              setSavedNote(false);
              setRows(draft.filter((r) => r.key !== key));
            }}
            onAdd={add}
          />
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-muted">{p.horizon}</span>
            <span className="flex items-center gap-3">
              <input
                type="range"
                min={1}
                max={40}
                value={years}
                onChange={(e) => setYears(Number(e.target.value))}
                className="flex-1 accent-accent"
              />
              <output className="w-16 text-right font-semibold">{p.years(years)}</output>
            </span>
          </label>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
            <Segmented
              label={p.scope}
              value={scope}
              onChange={setScope}
              options={[
                ["household", p.scopeHousehold],
                ["mine", p.scopeMine],
                ["joint", p.scopeJoint],
              ]}
            />
            <Segmented
              label={p.euros}
              value={euros}
              onChange={setEuros}
              options={[
                ["today", p.eurosToday],
                ["current", p.eurosCurrent],
              ]}
            />
          </div>
          <div className="flex flex-wrap items-center justify-end gap-3">
            {savedNote && !dirty && (
              <span className="mr-auto text-sm text-positive">{p.savedOk}</span>
            )}
            {dirty && <span className="mr-auto text-sm font-medium text-warning">{p.unsaved}</span>}
            {dirty && (
              <Button
                variant="ghost"
                onClick={() => assumptions.data && setRows(savedRows(assumptions.data))}
              >
                {p.cancel}
              </Button>
            )}
            <Button disabled={!dirty || !valid || save.isPending} onClick={() => save.mutate()}>
              {p.save}
            </Button>
          </div>
          {dirty && parsed.some((x) => changedReturn(x.ret, byId.get(x.row.categoryId))) && (
            <p className="text-xs text-muted">{p.sharedReturn}</p>
          )}
          <ErrorAlert message={saveError} />
        </div>

        <div className="flex min-w-0 flex-col gap-3 p-4" aria-live="polite">
          {noWealth ? (
            <p className="text-muted">{p.noWealth}</p>
          ) : run.isError ? (
            <ErrorAlert message={detailSentence(run.error) ?? p.failed} />
          ) : !result || !last ? (
            <p className="text-muted">{p.computing}</p>
          ) : (
            <Answer
              result={result}
              years={years}
              view={view}
              setView={setView}
              today={euros === "today"}
              rate={rate}
              setRate={setRate}
              rateValid={rateValid}
              whatIfs={shownWhatIfs}
              whatIfNames={whatIfNames}
              amount={amountValue ? Number(amountValue) : null}
              stale={run.isFetching}
            />
          )}
        </div>
      </section>

      {result && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card title={p.reachTitle}>
            <div className="grid grid-cols-[1fr_auto] gap-3">
              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-muted">{p.amount}</span>
                <input
                  inputMode="decimal"
                  value={amount ?? ""}
                  onChange={(e) => setAmount(e.target.value)}
                  className={field}
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-muted">{p.by}</span>
                <input
                  type="month"
                  value={reachMonth}
                  min={result.start_month}
                  onChange={(e) => e.target.value && setReachMonth(e.target.value)}
                  className="rounded-md border border-border bg-surface px-2 py-1"
                />
              </label>
            </div>
            <Reach
              result={result}
              amount={amountValue}
              month={reachMonth}
              chanceText={chanceText}
            />
          </Card>

          <Card title={p.whatIfsTitle} subtitle={p.whatIfsIntro}>
            {whatIfs.map((w, k) => (
              <WhatIfCard
                // biome-ignore lint/suspicious/noArrayIndexKey: two fixed what-ifs
                key={k}
                n={k + 1}
                draft={w}
                invalid={whatIfInvalid[k] ?? false}
                categories={categories}
                onChange={(next) => setWhatIfs(whatIfs.map((x, i) => (i === k ? next : x)))}
              />
            ))}
            <Compare
              result={result}
              whatIfs={shownWhatIfs}
              names={whatIfNames}
              chanceText={chanceText}
            />
          </Card>

          <div className="lg:col-span-2">
            <Card title={p.categoriesTitle} subtitle={p.categoriesHint}>
              <CategoriesChart
                categories={result.categories}
                debts={[Number(months[0]?.debts ?? 0), Number(last?.debts ?? 0)]}
                shortfall={[0, Number(last?.shortfall ?? 0)]}
              />
              <DataTable
                label={p.categoriesTitle}
                head={[p.colCategory, p.categoryToday, p.categoryHorizon]}
                rows={result.categories.map((c) => [
                  c.name,
                  formatEurHundreds(c.medians[0] ?? "0"),
                  formatEurHundreds(c.medians.at(-1) ?? "0"),
                ])}
              />
            </Card>
          </div>
        </div>
      )}

      <Fold title={p.advancedTitle}>
        <ProjectionAssumptions
          onSaved={() => {
            setRows(null);
            void queryClient.invalidateQueries({ queryKey: RUN_KEY });
          }}
        />
      </Fold>
      <Fold title={p.methodTitle}>
        <div className="flex flex-col gap-2 text-sm text-muted">
          <p>{p.caption}</p>
          {result && (
            <p>
              {p.engine(
                new Intl.NumberFormat().format(result.paths),
                String(result.seed),
                String(result.engine_version),
              )}
            </p>
          )}
          <ul className="list-disc pl-5">
            {p.limits.map((limit) => (
              <li key={limit}>{limit}</li>
            ))}
          </ul>
        </div>
      </Fold>
    </div>
  );
}

function Fold({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details className="group rounded-lg border border-border bg-surface">
      <summary className="cursor-pointer list-none px-4 py-3 font-semibold">
        <span aria-hidden="true" className="mr-2 inline-block text-muted group-open:rotate-90">
          ▸
        </span>
        {title}
      </summary>
      <div className="border-t border-border p-4">{children}</div>
    </details>
  );
}

function Contributions({
  parsed,
  categories,
  byId,
  free,
  total,
  result,
  scope,
  onUpdate,
  onRemove,
  onAdd,
}: {
  parsed: { row: Row; amount: string | null; ret: string | null }[];
  categories: CategoryAssumptionOut[];
  byId: Map<string, CategoryAssumptionOut>;
  free: boolean;
  total: number;
  result: RunOut | undefined;
  scope: Scope;
  onUpdate: (key: number, change: Partial<Row>) => void;
  onRemove: (key: number) => void;
  onAdd: () => void;
}) {
  const { t } = useI18n();
  const p = t.projection;
  const titleId = useId();
  const savings = result?.savings;
  const share = savings?.share_of_capacity;
  return (
    <div className="flex flex-col gap-2">
      <h2 id={titleId} className="text-xs font-semibold tracking-wide text-muted uppercase">
        {p.contributionsTitle}
      </h2>
      {parsed.length === 0 ? (
        <p className="text-sm text-muted">{p.noContributions}</p>
      ) : (
        <table aria-labelledby={titleId} className="w-full text-sm">
          <thead className="text-xs text-muted">
            <tr>
              <th className="pb-1 text-left font-medium">{p.colCategory}</th>
              <th className="pr-2 pb-1 text-right font-medium">{p.colAmount}</th>
              <th className="pr-2 pb-1 text-right font-medium">{p.colReturn}</th>
              <th className="pb-1 text-center font-medium" title={p.indexedHint}>
                {p.colIndexed}
              </th>
              <th />
            </tr>
          </thead>
          <tbody>
            {parsed.map(({ row, amount, ret }, i) => {
              const category = byId.get(row.categoryId);
              const name = category?.name ?? "";
              const volatile = category && Number(category.volatility) >= VOLATILE;
              return (
                <Fragment key={row.key}>
                  <tr>
                    <td className="py-1 pr-1">
                      <select
                        aria-label={p.categoryOf(i + 1)}
                        value={row.categoryId}
                        onChange={(e) => {
                          const next = byId.get(e.target.value);
                          onUpdate(row.key, {
                            categoryId: e.target.value,
                            ret: next ? percentInput(next.ret) : row.ret,
                          });
                        }}
                        className="w-full rounded-md border border-border bg-surface px-1 py-1"
                      >
                        {categories
                          .filter(
                            (c) =>
                              c.id === row.categoryId ||
                              !parsed.some((x) => x.row.categoryId === c.id),
                          )
                          .map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                      </select>
                    </td>
                    <td className="w-20 py-1 pr-1">
                      <input
                        aria-label={p.amountOf(name)}
                        aria-invalid={amount === null}
                        inputMode="decimal"
                        value={row.amount}
                        onChange={(e) => onUpdate(row.key, { amount: e.target.value })}
                        className={`${field} ${amount === null ? "border-negative" : ""}`}
                      />
                    </td>
                    <td className="w-16 py-1 pr-1">
                      <input
                        aria-label={p.returnOf(name)}
                        aria-invalid={ret === null}
                        inputMode="decimal"
                        value={row.ret}
                        onChange={(e) => onUpdate(row.key, { ret: e.target.value })}
                        className={`${field} ${ret === null ? "border-negative" : ""}`}
                      />
                    </td>
                    <td className="py-1 text-center">
                      <input
                        type="checkbox"
                        aria-label={p.indexedOf(name)}
                        checked={row.indexed}
                        onChange={(e) => onUpdate(row.key, { indexed: e.target.checked })}
                        className="accent-accent"
                      />
                    </td>
                    <td className="py-1 text-right">
                      <button
                        type="button"
                        aria-label={p.remove(name)}
                        onClick={() => onRemove(row.key)}
                        className="rounded px-1.5 text-muted hover:bg-border hover:text-fg"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                  {volatile && category && (
                    <tr>
                      <td colSpan={5} className="pb-1 text-xs text-warning">
                        △ {p.volatile(name, formatRate(category.median_growth))}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      )}
      {parsed.some((x) => x.amount === null) && (
        <p className="text-xs text-negative">{p.invalidAmount}</p>
      )}
      {parsed.some((x) => x.ret === null) && (
        <p className="text-xs text-negative">{p.invalidReturn}</p>
      )}
      {free && (
        <button
          type="button"
          onClick={onAdd}
          className="self-start text-sm text-accent hover:underline"
        >
          + {p.add}
        </button>
      )}
      {parsed.length > 0 && (
        <p className="flex items-baseline justify-between border-t border-border pt-2 text-sm">
          <span>{p.total}</span>
          <span className="tabular font-semibold">{p.perMonth(formatEurWhole(total))}</span>
        </p>
      )}
      {savings && savings.mode === "contributions" && share && (
        <div className="text-xs text-muted">
          <p className={Number(share) > 1 ? "text-warning" : ""}>
            {Number(share) > 1 ? "△ " : ""}
            {(Number(share) > 1 ? p.overCapacity : p.ofCapacity)(
              formatPercent(share),
              formatEurWhole(savings.capacity),
            )}
          </p>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-border">
            <div
              className="h-full rounded-full bg-accent"
              style={{ width: `${Math.min(100, Number(share) * 100)}%` }}
            />
          </div>
        </div>
      )}
      {savings && savings.mode === "capacity" && (
        <p className="text-xs text-muted">
          {savings.capacity_set
            ? p.capacitySetByHand(formatEurWhole(savings.capacity))
            : p.capacityMeasured(formatEurWhole(savings.capacity), savings.capacity_months)}
        </p>
      )}
      {savings && !savings.capacity_set && savings.capacity_months < 12 && (
        <p className="text-xs text-muted">{p.capacityShort(savings.capacity_months)}</p>
      )}
      {parsed.length > 0 && <p className="text-xs text-muted">{p.indexedHint}</p>}
      {scope !== "household" && parsed.length > 0 && (
        <p className="text-xs text-muted">{p.householdScope}</p>
      )}
      {result?.ceiling_note && <p className="text-xs text-warning">△ {p.ceilings}</p>}
    </div>
  );
}

function Answer({
  result,
  years,
  view,
  setView,
  today,
  rate,
  setRate,
  rateValid,
  whatIfs,
  whatIfNames,
  amount,
  stale,
}: {
  result: RunOut;
  years: number;
  view: View;
  setView: (view: View) => void;
  today: boolean;
  rate: string;
  setRate: (rate: string) => void;
  rateValid: boolean;
  whatIfs: (RunOut["what_ifs"][number] | null)[];
  whatIfNames: string[];
  amount: number | null;
  stale: boolean;
}) {
  const { t } = useI18n();
  const p = t.projection;
  const h = result.horizon;
  const months = result.months;
  const last = months.at(-1);
  const first = months[0];
  if (!last || !first) return null;
  const gains = Number(last.gains);
  const chips: [string, string, string][] = [
    ["var(--color-projection-today)", p.partToday, last.today],
    ["var(--color-projection-contributed)", p.partContributed, last.contributed],
    ...(Number(last.repaid)
      ? ([["var(--color-projection-repaid)", p.partRepaid, last.repaid]] as [
          string,
          string,
          string,
        ][])
      : []),
    [
      gains < 0 ? "var(--color-projection-losses)" : "var(--color-projection-gains)",
      gains < 0 ? p.partLosses : today ? p.partGainsAfterInflation : p.partGains,
      last.gains,
    ],
  ];
  const yearly = months.filter((_, i) => i % 12 === 0 || i === months.length - 1);
  return (
    <div className={`flex flex-col gap-3 transition-opacity ${stale ? "opacity-70" : ""}`}>
      <div className="text-center">
        <p className="text-sm text-muted">{p.medianIn(p.years(years))}</p>
        <p className="font-display text-4xl font-black tracking-tight tabular sm:text-5xl">
          {formatEurHundreds(h.median)}
        </p>
        <p className="text-sm text-muted">
          {p.range(formatEurHundreds(h.p10), formatEurHundreds(h.p90))}
        </p>
        <p className="mt-1 text-sm">
          {p.income(
            formatEurWhole(Math.round(Number(h.income_median) / 10) * 10),
            formatEurWhole(Math.round(Number(h.income_low) / 10) * 10),
            formatPercent(String(Number(parsePercentInput(rate) ?? "0.04"))),
          )}
        </p>
        <details className="mx-auto mt-1 max-w-xl text-xs text-muted">
          <summary className="cursor-pointer">{p.withdrawalRate}</summary>
          <div className="mt-1 flex flex-col items-center gap-1">
            <input
              aria-label={p.withdrawalRate}
              aria-invalid={!rateValid}
              inputMode="decimal"
              value={rate}
              onChange={(e) => setRate(e.target.value)}
              className="w-20 rounded-md border border-border bg-surface px-2 py-1 text-right tabular"
            />
            {!rateValid && <span className="text-negative">{p.invalidRate}</span>}
            <span>{p.incomeCaveat}</span>
          </div>
        </details>
      </div>
      <ul className="flex flex-wrap justify-center gap-2" aria-label={p.viewParts}>
        {chips.map(([colour, name, value]) => (
          <li
            key={name}
            className="flex items-center gap-1.5 rounded-full border border-border bg-bg px-2.5 py-0.5 text-xs"
          >
            <span
              aria-hidden="true"
              className="h-2 w-2 rounded-full"
              style={{ background: colour }}
            />
            {name} <span className="tabular font-semibold">{formatEurHundreds(value)}</span>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="w-80 max-w-full">
          <Segmented
            label={p.viewChoice}
            value={view}
            onChange={setView}
            options={[
              ["parts", p.viewParts],
              ["fan", p.viewFan],
            ]}
          />
        </div>
        <p className="text-xs text-muted">{view === "parts" ? p.partsHint : p.fanHint}</p>
      </div>
      <ProjectionChart
        months={months}
        view={view}
        today={today}
        whatIfs={whatIfs}
        whatIfNames={whatIfNames}
        amount={amount}
      />
      {view === "parts" && today && <p className="text-xs text-muted">{p.partsTodayHint}</p>}
      <dl className="grid grid-cols-2 gap-2 border-t border-border pt-3 text-center sm:grid-cols-4">
        {(
          [
            [p.footToday, first.p50],
            [p.footContributed, last.contributed],
            [today ? p.partGainsAfterInflation : p.footGains, last.gains],
            [p.footRepaid, last.repaid],
          ] as [string, string][]
        ).map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-muted">{label}</dt>
            <dd className="tabular font-semibold">{formatEurHundreds(value)}</dd>
          </div>
        ))}
      </dl>
      {Number(result.shortfall_share) > 0 && (
        <p className="text-sm text-warning">
          △ {p.shortfall(formatPercent(result.shortfall_share))}
        </p>
      )}
      <DataTable
        label={p.chartLabel}
        head={[
          p.colMonth,
          p.p10,
          p.median,
          p.p90,
          p.partToday,
          p.partContributed,
          p.partRepaid,
          today ? p.partGainsAfterInflation : p.partGains,
        ]}
        rows={yearly.map((m) => [
          monthLabel(m.month),
          formatEurHundreds(m.p10),
          formatEurHundreds(m.p50),
          formatEurHundreds(m.p90),
          formatEurHundreds(m.today),
          formatEurHundreds(m.contributed),
          formatEurHundreds(m.repaid),
          formatEurHundreds(m.gains),
        ])}
      />
    </div>
  );
}

function Reach({
  result,
  amount,
  month,
  chanceText,
}: {
  result: RunOut;
  amount: string | null;
  month: string;
  chanceText: (chance: string) => string;
}) {
  const { t } = useI18n();
  const p = t.projection;
  const reach = result.reach;
  if (!amount || !reach) return null;
  const chance = reach.chance;
  const n = chance === null ? null : Number(chance);
  const status =
    n === null
      ? null
      : n >= 0.5
        ? ["✓", p.likely]
        : n >= 0.2
          ? ["△", p.possible]
          : ["▲", p.unlikely];
  return (
    <div className="flex flex-col gap-2">
      {chance === null ? (
        <p className="text-sm text-muted">{p.afterHorizon}</p>
      ) : (
        <>
          <p className="flex items-baseline gap-3">
            <span className="font-display text-4xl font-black tabular">{chanceText(chance)}</span>
            {status && (
              <span
                className={`text-sm font-semibold ${n !== null && n >= 0.5 ? "text-positive" : "text-warning"}`}
              >
                <span aria-hidden="true">{status[0]} </span>
                {status[1]}
              </span>
            )}
          </p>
          <div className="h-2 overflow-hidden rounded-full bg-border">
            <div
              className="h-full rounded-full bg-accent"
              style={{ width: `${(n ?? 0) * 100}%` }}
            />
          </div>
          <p className="text-sm text-muted">
            {p.reachChance(chanceText(chance), formatEurHundreds(amount), monthLabel(month))}
          </p>
        </>
      )}
      <dl className="text-sm">
        {(
          [
            [p.reachHalf, reach.half],
            [p.reachNinety, reach.ninety],
          ] as [string, string | null][]
        ).map(([label, value]) => (
          <div key={label} className="flex justify-between border-t border-border py-1.5">
            <dt>{label}</dt>
            <dd className="font-semibold">{value ? monthLabel(value) : p.notWithin}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function WhatIfCard({
  n,
  draft,
  invalid,
  categories,
  onChange,
}: {
  n: number;
  draft: WhatIfDraft;
  invalid: boolean;
  categories: CategoryAssumptionOut[];
  onChange: (next: WhatIfDraft) => void;
}) {
  const { t } = useI18n();
  const p = t.projection;
  const set = (change: Partial<WhatIfDraft>) => onChange({ ...draft, ...change });
  const input = (label: string, value: string, key: keyof WhatIfDraft) => (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-muted">{label}</span>
      <input
        inputMode="decimal"
        value={value}
        disabled={!draft.on}
        onChange={(e) => set({ [key]: e.target.value } as Partial<WhatIfDraft>)}
        className={field}
      />
    </label>
  );
  return (
    <div className="rounded-md border border-dashed border-border p-3">
      <label className="flex items-center gap-2 font-semibold">
        <input
          type="checkbox"
          checked={draft.on}
          onChange={(e) => set({ on: e.target.checked })}
          className="accent-accent"
        />
        <span
          aria-hidden="true"
          className="inline-block h-0.5 w-5"
          style={{ background: WHAT_IF_COLOURS[n - 1] }}
        />
        {p.compare(n)}
      </label>
      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
        {input(p.wiSavings, draft.savings, "savings")}
        {input(p.wiInflation, draft.inflation, "inflation")}
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted">{p.wiCategory}</span>
          <select
            value={draft.categoryId}
            disabled={!draft.on}
            onChange={(e) => set({ categoryId: e.target.value })}
            className="rounded-md border border-border bg-surface px-1 py-1"
          >
            <option value="">{p.wiNone}</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        {input(p.wiReturn, draft.ret, "ret")}
        {input(p.wiVolatility, draft.volatility, "volatility")}
      </div>
      {invalid && <p className="mt-1 text-xs text-negative">{p.wiInvalid(n)}</p>}
    </div>
  );
}

function Compare({
  result,
  whatIfs,
  names,
  chanceText,
}: {
  result: RunOut;
  whatIfs: (RunOut["what_ifs"][number] | null)[];
  names: string[];
  chanceText: (chance: string) => string;
}) {
  const { t } = useI18n();
  const p = t.projection;
  if (!whatIfs.some(Boolean)) return null;
  const rows: [string, string, string | null][] = [
    [p.base, result.horizon.median, result.reach?.chance ?? null],
    ...whatIfs.flatMap((w, k) =>
      w ? ([[names[k] ?? "", w.median, w.chance]] as [string, string, string | null][]) : [],
    ),
  ];
  return (
    <table className="w-full text-sm">
      <thead className="text-left text-xs text-muted">
        <tr>
          <th className="py-1 font-medium">{p.colScenario}</th>
          <th className="py-1 text-right font-medium">{p.colMedian}</th>
          <th className="py-1 text-right font-medium">{p.colChance}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([name, median, chance]) => (
          <tr key={name} className="border-t border-border">
            <td className="py-1">{name}</td>
            <td className="tabular py-1 text-right">{formatEurHundreds(median)}</td>
            <td className="tabular py-1 text-right">
              {chance === null ? "—" : chanceText(chance)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
