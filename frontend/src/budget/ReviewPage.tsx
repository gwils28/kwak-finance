import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { type ReactNode, useId, useState } from "react";
import {
  type BudgetStatus,
  listPlans,
  type PlanOut,
  planComparison,
  planCumulative,
  type ReviewOut,
  type ReviewRowOut,
  reviewPlan,
  type Scope,
} from "../api/generated";
import { ErrorAlert } from "../components/ui";
import { Card } from "../dashboard/charts";
import { useI18n } from "../i18n";
import { formatEurSigned, formatEurWhole, formatPercent, formatPercentSigned } from "../lib/money";
import { monthBounds, monthLabel, thisMonth } from "../lib/months";
import { defaultPlan } from "../lib/plans";
import { PLANS_KEY, usePeriodLabel } from "./PlanPanel";
import { CumulativeChart, GapChart } from "./reviewCharts";

const STATUS_CLASS: Record<BudgetStatus, string> = {
  under: "bg-budget-under-bg text-budget-under-fg",
  on: "bg-budget-on-bg text-budget-on-fg",
  over: "bg-budget-over-bg text-budget-over-fg",
  none: "",
};
const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";
const labelClass = "flex flex-col gap-1 text-sm font-medium";

export function ReviewPage({ planId }: { planId: string | undefined }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const label = usePeriodLabel();
  const ids = { plan: useId(), scope: useId(), band: useId() };
  const [scope, setScope] = useState<Scope>("household");
  const [band, setBand] = useState("0.05");

  const plans = useQuery({
    queryKey: PLANS_KEY,
    queryFn: async () => (await listPlans({ throwOnError: true })).data,
  });
  const plan =
    plans.data?.find((p) => p.id === planId) ?? defaultPlan(plans.data ?? [], thisMonth());

  const review = useQuery({
    queryKey: ["budget", "review", plan?.id, { scope, band }],
    queryFn: async () =>
      (
        await reviewPlan({
          path: { plan_id: plan?.id as string },
          query: { scope, band },
          throwOnError: true,
        })
      ).data,
    enabled: plan !== undefined,
    placeholderData: keepPreviousData,
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight">{t.review.title}</h1>
          <p className="text-sm text-muted">{t.review.intro}</p>
          <Link to="/budget" className="text-sm text-accent hover:underline">
            {t.review.backToBudget}
          </Link>
        </div>
        {plan && plans.data && (
          <div className="flex flex-wrap gap-3">
            <label htmlFor={ids.plan} className={labelClass}>
              {t.budget.plan.select}
              <select
                id={ids.plan}
                className={fieldClass}
                value={plan.id}
                onChange={(e) =>
                  navigate({ to: "/budget/review", search: { plan: e.target.value } })
                }
              >
                {plans.data.map((p) => (
                  <option key={p.id} value={p.id}>
                    {`${label(p.period)} · ${t.budget.plan.range(monthLabel(p.start), monthLabel(p.end))}`}
                    {p.closed_early ? ` · ${t.budget.plan.closedEarlyTag}` : ""}
                  </option>
                ))}
              </select>
            </label>
            <label htmlFor={ids.scope} className={labelClass}>
              {t.dashboard.scope}
              <select
                id={ids.scope}
                className={fieldClass}
                value={scope}
                onChange={(e) => setScope(e.target.value as Scope)}
              >
                <option value="household">{t.dashboard.household}</option>
                <option value="mine">{t.dashboard.mine}</option>
              </select>
            </label>
            <label htmlFor={ids.band} className={labelClass}>
              {t.budget.margin}
              <select
                id={ids.band}
                className={fieldClass}
                value={band}
                onChange={(e) => setBand(e.target.value)}
              >
                {["0.05", "0.10", "0.15"].map((value) => (
                  <option key={value} value={value}>
                    ± {formatPercent(value)}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}
      </div>
      {(plans.isError || review.isError) && <ErrorAlert message={t.review.loadFailed} />}
      {plans.data?.length === 0 && (
        <p className="text-sm">
          {t.review.noPlan}{" "}
          <Link to="/budget" className="text-accent hover:underline">
            {t.review.goToBudget}
          </Link>
        </p>
      )}
      {(plans.isPending || review.isPending) && plans.data?.length !== 0 && (
        <p className="text-sm text-muted">{t.common.loading}</p>
      )}
      {plan && plans.data && review.data && (
        <Review review={review.data} plan={plan} plans={plans.data} scope={scope} />
      )}
    </div>
  );
}

function Review({
  review,
  plan,
  plans,
  scope,
}: {
  review: ReviewOut;
  plan: PlanOut;
  plans: PlanOut[];
  scope: Scope;
}) {
  const { t } = useI18n();
  return (
    <>
      {plan.closed_early && (
        <div className="text-sm">
          <p>{t.budget.plan.closedEarly(monthLabel(plan.end))}</p>
          {plan.close_reason && (
            <p className="text-muted">{t.budget.plan.reason(plan.close_reason)}</p>
          )}
        </div>
      )}
      {review.provisional && (
        <p className="rounded-md border border-warning px-3 py-2 text-sm">
          {t.review.provisional(formatEurWhole(review.uncategorised))}{" "}
          <Link
            to="/transactions"
            search={{
              category: "none",
              from: monthBounds(plan.start).from,
              to: monthBounds(plan.end).to,
            }}
            className="font-medium text-accent hover:underline"
          >
            {t.review.categorise}
          </Link>
        </p>
      )}
      <Summary review={review} />
      {!review.finished && <DriftList review={review} />}
      <CategoryTable review={review} />
      <div className="grid gap-6 lg:grid-cols-2">
        <GapChart rows={review.rows} />
        <Cumulative plan={plan} rows={review.rows} scope={scope} />
      </div>
      <Comparison plan={plan} plans={plans} scope={scope} />
    </>
  );
}

function Figure({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="tabular text-xl font-bold">{children}</dd>
    </div>
  );
}

function Summary({ review }: { review: ReviewOut }) {
  const { t } = useI18n();
  const id = useId();
  const total = review.total;
  return (
    <section
      aria-labelledby={id}
      className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id={id} className="text-lg font-bold">
          {t.review.summary}
        </h2>
        <p className="text-sm text-muted">
          {review.finished ? t.review.finalResult : t.review.elapsed(formatPercent(review.elapsed))}
        </p>
      </div>
      {!review.finished && (
        <div className="h-2 overflow-hidden rounded-full bg-budget-on-bg" role="presentation">
          <div
            className="h-full bg-chart-accent"
            style={{ width: `${Math.min(100, Number(review.elapsed) * 100)}%` }}
          />
        </div>
      )}
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {total.envelope !== null && (
          <Figure label={t.review.envelope}>{formatEurWhole(total.envelope)}</Figure>
        )}
        <Figure label={t.review.spent}>{formatEurWhole(total.spent)}</Figure>
        {total.gap !== null && total.gap_ratio !== null && (
          <Figure label={t.review.gap}>
            {`${formatEurSigned(total.gap)} · ${formatPercentSigned(total.gap_ratio)}`}
          </Figure>
        )}
        {!review.finished && total.pace !== null && (
          <Figure label={t.review.expectedByNow}>{formatEurWhole(total.pace)}</Figure>
        )}
        {!review.finished && total.projection !== null && (
          <Figure label={t.review.projected}>{formatEurWhole(total.projection)}</Figure>
        )}
        <Figure label={t.review.income}>{formatEurWhole(review.income)}</Figure>
        <Figure label={t.review.savings}>{formatEurWhole(review.savings)}</Figure>
        {review.savings_rate !== null && (
          <Figure label={t.review.savingsRate}>{formatPercent(review.savings_rate)}</Figure>
        )}
        {review.planned_savings !== null && (
          <Figure label={t.review.plannedSavings}>{formatEurWhole(review.planned_savings)}</Figure>
        )}
      </dl>
    </section>
  );
}

function DriftList({ review }: { review: ReviewOut }) {
  const { t } = useI18n();
  const rows = review.drifting
    .map((id) => review.rows.find((r) => r.category_id === id))
    .filter((r): r is ReviewRowOut => r !== undefined);
  return (
    <Card title={t.review.drifting} subtitle={t.review.driftingHelp}>
      {rows.length === 0 ? (
        <p className="text-sm text-muted">{t.review.noDrift}</p>
      ) : (
        <ol className="flex flex-col gap-2 text-sm">
          {rows.map((r) => (
            <li
              key={r.category_id}
              className="rounded-md bg-budget-over-bg px-3 py-2 text-budget-over-fg"
            >
              {t.review.driftItem(
                r.name,
                formatEurSigned(r.drift as string),
                formatEurWhole(r.projection as string),
                formatEurWhole(r.envelope as string),
              )}
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

function CategoryTable({ review }: { review: ReviewOut }) {
  const { t } = useI18n();
  const running = !review.finished;
  const cell = "whitespace-nowrap px-3 py-2 text-right tabular";
  const line = (r: ReviewRowOut, total = false) => (
    <tr key={r.category_id ?? r.name} className={total ? "border-t-2 border-border font-bold" : ""}>
      <th
        scope="row"
        className={`whitespace-nowrap px-3 py-2 text-left ${
          r.level === 1 ? "pl-8 font-normal" : "font-semibold"
        }`}
      >
        {r.name}
      </th>
      <td className={cell}>{r.monthly_target === null ? "" : formatEurWhole(r.monthly_target)}</td>
      <td className={cell}>{r.envelope === null ? "" : formatEurWhole(r.envelope)}</td>
      <td className={cell}>{formatEurWhole(r.spent)}</td>
      <td className={cell}>
        {r.gap === null || r.gap_ratio === null
          ? ""
          : `${formatEurSigned(r.gap)} · ${formatPercentSigned(r.gap_ratio)}`}
      </td>
      {running && <td className={cell}>{r.pace === null ? "" : formatEurWhole(r.pace)}</td>}
      <td
        data-status={r.status}
        className={`whitespace-nowrap px-3 py-2 text-center ${STATUS_CLASS[r.status]}`}
      >
        {t.review.statusName[r.status]}
      </td>
      <td className={cell}>
        {r.envelope === null ? "" : `${r.months_over} · ${r.months_on} · ${r.months_under}`}
      </td>
    </tr>
  );
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table aria-label={t.review.byCategory} className="w-full text-sm">
        <thead className="text-left text-muted">
          <tr>
            {[
              t.review.category,
              t.review.monthlyTarget,
              t.review.envelope,
              t.review.spent,
              t.review.gap,
              ...(running ? [t.review.pace] : []),
              t.review.status,
              t.review.months,
            ].map((h, i) => (
              <th
                key={h}
                className={`whitespace-nowrap px-3 py-2 font-medium ${i > 0 ? "text-right" : ""}`}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {review.rows
            .filter((r) => r.envelope !== null || Number(r.spent) !== 0)
            .map((r) => line(r))}
          {line(review.total, true)}
        </tbody>
      </table>
    </div>
  );
}

function Cumulative({ plan, rows, scope }: { plan: PlanOut; rows: ReviewRowOut[]; scope: Scope }) {
  const { t } = useI18n();
  const id = useId();
  const [category, setCategory] = useState("");
  const chart = useQuery({
    queryKey: ["budget", "cumulative", plan.id, { category, scope }],
    queryFn: async () =>
      (
        await planCumulative({
          path: { plan_id: plan.id },
          query: { scope, ...(category ? { category_id: category } : {}) },
          throwOnError: true,
        })
      ).data,
    placeholderData: keepPreviousData,
  });
  const select = (
    <label htmlFor={id} className={labelClass}>
      {t.review.category}
      <select
        id={id}
        className={fieldClass}
        value={category}
        onChange={(e) => setCategory(e.target.value)}
      >
        <option value="">{t.review.allCategories}</option>
        {rows
          .filter((r) => r.category_id && (r.envelope !== null || Number(r.spent) !== 0))
          .map((r) => (
            <option key={r.category_id} value={r.category_id as string}>
              {r.level === 1 ? `— ${r.name}` : r.name}
            </option>
          ))}
      </select>
    </label>
  );
  if (!chart.data) return null;
  return <CumulativeChart chart={chart.data} aside={select} />;
}

function Comparison({ plan, plans, scope }: { plan: PlanOut; plans: PlanOut[]; scope: Scope }) {
  const { t } = useI18n();
  const label = usePeriodLabel();
  const id = useId();
  const [against, setAgainst] = useState<string | null>(null);
  const others = plans.filter((p) => p.id !== plan.id);
  const comparison = useQuery({
    queryKey: ["budget", "comparison", plan.id, { against, scope }],
    queryFn: async () => {
      const { data, response } = await planComparison({
        path: { plan_id: plan.id },
        query: { scope, ...(against ? { against } : {}) },
      });
      // The first plan has no previous one: nothing to compare until another is picked.
      if (response?.status === 404) return null;
      if (!data) throw new Error(String(response?.status));
      return data;
    },
    enabled: others.length > 0,
    placeholderData: keepPreviousData,
  });
  const data = comparison.data;
  const reference = data?.a;
  // A plan closed early and its replacement share a period: tell them apart by their months.
  const name = (p: PlanOut) =>
    reference && reference.period === plan.period
      ? `${label(p.period)} (${t.budget.plan.range(monthLabel(p.start), monthLabel(p.end))})`
      : label(p.period);
  const nameA = reference ? name(reference) : "";
  const nameB = name(plan);
  const cell = "whitespace-nowrap px-3 py-2 text-right tabular";
  const eur = (amount: string | null) => (amount === null ? "" : formatEurWhole(amount));

  return (
    <Card
      title={t.review.comparison}
      subtitle={t.review.comparisonHelp}
      aside={
        others.length > 0 && (
          <label htmlFor={id} className={labelClass}>
            {t.review.compareWith}
            <select
              id={id}
              className={fieldClass}
              value={against ?? reference?.id ?? ""}
              onChange={(e) => setAgainst(e.target.value)}
            >
              {!reference && <option value="">—</option>}
              {others.map((p) => (
                <option key={p.id} value={p.id}>
                  {`${label(p.period)} · ${t.budget.plan.range(monthLabel(p.start), monthLabel(p.end))}`}
                </option>
              ))}
            </select>
          </label>
        )
      }
    >
      {others.length === 0 || (comparison.isSuccess && !data) ? (
        <p className="text-sm text-muted">{t.review.noComparison}</p>
      ) : (
        data &&
        reference && (
          <div className="overflow-x-auto">
            <table aria-label={t.review.comparison} className="w-full text-sm">
              <thead className="text-left text-muted">
                <tr>
                  {[
                    ["category", t.review.category],
                    ["target-a", t.review.targetOf(nameA)],
                    ["target-b", t.review.targetOf(nameB)],
                    ["average-a", t.review.averageOf(nameA)],
                    ["average-b", t.review.averageOf(nameB)],
                    ["change", t.review.change],
                  ].map(([key, h], i) => (
                    <th
                      key={key}
                      className={`whitespace-nowrap px-3 py-2 font-medium ${i > 0 ? "text-right" : ""}`}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.rows
                  .filter(
                    (r) =>
                      r.target_a !== null ||
                      r.target_b !== null ||
                      Number(r.average_a ?? 0) !== 0 ||
                      Number(r.average_b ?? 0) !== 0,
                  )
                  .map((r) => (
                    <tr
                      key={r.category_id ?? r.name}
                      className={r.category_id === null ? "border-t-2 border-border font-bold" : ""}
                    >
                      <th
                        scope="row"
                        className={`whitespace-nowrap px-3 py-2 text-left ${
                          r.level === 1 ? "pl-8 font-normal" : "font-semibold"
                        }`}
                      >
                        {r.name}
                      </th>
                      <td className={cell}>{eur(r.target_a)}</td>
                      <td className={cell}>{eur(r.target_b)}</td>
                      <td className={cell}>{eur(r.average_a)}</td>
                      <td className={cell}>{eur(r.average_b)}</td>
                      <td className={cell}>
                        {r.change === null
                          ? ""
                          : r.change_ratio === null
                            ? formatEurSigned(r.change)
                            : `${formatEurSigned(r.change)} · ${formatPercentSigned(r.change_ratio)}`}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </Card>
  );
}
