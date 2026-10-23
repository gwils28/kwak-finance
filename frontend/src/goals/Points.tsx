import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type ReactNode, useState } from "react";
import {
  type GoalAnalysisOut,
  hidePoint,
  type PointOut,
  type Scope,
  type Severity,
  showHidden,
} from "../api/generated";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { numberFormat } from "../lib/locale";
import { formatEurWhole } from "../lib/money";
import { monthLabel, shiftMonth } from "../lib/months";
import { GOALS_KEY } from "./shared";

const EDGE: Record<Severity, string> = {
  warning: "var(--color-progress-over)",
  info: "var(--color-chart-on)",
  good: "var(--color-chart-under)",
};

const ICON: Record<Severity, string> = { warning: "⚠", info: "ℹ", good: "✓" };

const text = (value: unknown) => (typeof value === "string" ? value : null);
const eur = (value: unknown) => formatEurWhole(text(value) ?? "0");

type Said = { fact: string; why?: string; options?: ReactNode[]; link?: ReactNode };

/** What a point says: the fact with its figures, why it matters and the options (F-ANA-8). */
function useSaid(point: PointOut, data: GoalAnalysisOut): Said {
  const { t } = useI18n();
  const a = t.goalAnalysis;
  const g = t.goals;
  const goal = point.goal_name ?? "";
  const f = point.figures;
  const amount = formatEurWhole(point.amount ?? "0");
  const goalLink = point.goal_id && (
    <Link
      to="/goals/$goalId"
      params={{ goalId: point.goal_id }}
      className="text-accent hover:underline"
    >
      {point.rule === "unfunded" ? a.unfundedAction : a.openGoal}
    </Link>
  );
  switch (point.rule) {
    case "data":
      return point.lines.length > 0
        ? {
            fact: a.data.lines(
              monthLabel(shiftMonth(data.month, -1)),
              point.lines.map((l) => l.name).join(", "),
            ),
            why: a.data.linesWhy,
            link: (
              <Link to="/wealth" className="text-accent hover:underline">
                {a.data.update}
              </Link>
            ),
          }
        : {
            fact: a.data.capacity(Number(f.capacity_months ?? 0)),
            why: a.data.capacityWhy,
            link: (
              <Link to="/spending" className="text-accent hover:underline">
                {a.data.spending}
              </Link>
            ),
          };
    case "precaution_none":
      return {
        fact: a.precautionNone,
        why: a.precautionNoneWhy,
        link: (
          <Link to="/goals" className="text-accent hover:underline">
            {a.precautionNoneAction}
          </Link>
        ),
      };
    case "precaution_low":
      return {
        fact: `${a.precautionLow(goal, numberFormat({ maximumFractionDigits: 1 }).format(Number(f.months ?? 0)), eur(f.monthly_fixed))} ${
          point.severity === "warning"
            ? a.precautionLowWarning(amount)
            : a.precautionLowInfo(amount)
        }`,
        why: a.precautionLowWhy,
        link: goalLink,
      };
    case "precaution_risky":
      return { fact: a.precautionRisky(goal, amount), why: a.precautionRiskyWhy, link: goalLink };
    case "precaution_current":
      return {
        fact: a.precautionCurrent(goal, amount),
        why: a.precautionCurrentWhy,
        link: goalLink,
      };
    case "unfunded":
      return { fact: a.unfunded(goal), link: goalLink };
    case "overcommitted": {
      const capacity = formatEurWhole(data.capacity);
      if (point.severity === "info") {
        return {
          fact: a.overcommitted(amount, capacity),
          why: a.overcommittedFilling(Number(f.months_to_fill ?? 0)),
        };
      }
      const [first, ...others] = point.postponements;
      if (!first) return { fact: a.overcommitted(amount, capacity), why: a.noPostponement(amount) };
      const current = data.timeline.find((x) => x.goal_id === first.goal_id)?.tier;
      return {
        fact: a.overcommitted(amount, capacity),
        options: [
          `${a.postpone(first.name, first.months, monthLabel(first.deadline))}${
            current && current !== first.tier ? a.movesTo(g.tiers[first.tier]) : ""
          }${a.orLower(formatEurWhole(first.lower_by))}`,
          ...(others.length > 0
            ? [
                `${a.otherOptions(others.map((p) => a.postponeOther(p.name, p.months)).join(" · "))}`,
              ]
            : []),
        ],
      };
    }
    case "behind": {
      const options = f.never
        ? [a.behindExtra(eur(f.extra)), a.behindNever]
        : [
            a.behindExtra(eur(f.extra)),
            ...(text(f.estimated) ? [a.behindDate(monthLabel(String(f.estimated)))] : []),
            ...(text(f.reachable) ? [a.behindTarget(eur(f.reachable))] : []),
          ];
      return {
        fact: a.behind(goal, amount),
        why: f.market ? a.behindMarket : undefined,
        options,
        link: goalLink,
      };
    }
    case "no_gain":
      return {
        fact: a.noGain(goal),
        options: [a.noGainOptions(text(f.required) ? eur(f.required) : null)],
        link: goalLink,
      };
    default:
      return { fact: goal };
  }
}

function PointCard({
  point,
  data,
  scope,
}: {
  point: PointOut;
  data: GoalAnalysisOut;
  scope: Scope;
}) {
  const { t } = useI18n();
  const a = t.goalAnalysis;
  const said = useSaid(point, data);
  const queryClient = useQueryClient();
  const hide = useMutation({
    mutationFn: async (action: "snooze" | "dismiss") =>
      hidePoint({
        query: { scope },
        body: { rule: point.rule, goal_id: point.goal_id, line_id: point.line_id, action },
        throwOnError: true,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...GOALS_KEY, "analysis"] }),
  });
  return (
    <li
      className="flex flex-col gap-2 rounded-lg border border-l-4 border-border bg-surface p-4 text-sm"
      style={{ borderLeftColor: EDGE[point.severity] }}
    >
      <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted">
        <span aria-hidden="true">{ICON[point.severity]}</span>
        {a.severity[point.severity]}
      </p>
      <p className="font-medium">{said.fact}</p>
      {said.why && <p className="text-muted">{said.why}</p>}
      {said.options && said.options.length > 0 && (
        <ul className="list-disc pl-5">
          {said.options.map((option) => (
            <li key={String(option)}>{option}</li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {said.link}
        {point.hideable && (
          <>
            <Button variant="ghost" onClick={() => hide.mutate("snooze")} disabled={hide.isPending}>
              {a.snooze}
            </Button>
            <Button
              variant="ghost"
              onClick={() => hide.mutate("dismiss")}
              disabled={hide.isPending}
            >
              {a.dismiss}
            </Button>
          </>
        )}
      </div>
      {hide.isError && <ErrorAlert message={a.hideFailed} />}
    </li>
  );
}

/** The points to look at: three shown, the rest on demand, and the disclaimer (F-ANA-8). */
export function Points({ data, scope }: { data: GoalAnalysisOut; scope: Scope }) {
  const { t } = useI18n();
  const a = t.goalAnalysis;
  const [all, setAll] = useState(false);
  const queryClient = useQueryClient();
  const restore = useMutation({
    mutationFn: async () => showHidden({ throwOnError: true }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...GOALS_KEY, "analysis"] }),
  });
  const { shown, more } = data.points;
  const points = all ? [...shown, ...more] : shown;
  const key = (p: PointOut) => `${p.rule}-${p.goal_id ?? ""}-${p.line_id ?? ""}`;
  return (
    <section aria-labelledby="points" className="flex flex-col gap-3">
      <h2 id="points" className="text-xl font-bold">
        {a.points}
      </h2>
      {points.length === 0 ? (
        <p className="text-sm text-muted">{a.noPoint}</p>
      ) : (
        <ul className="grid gap-3 lg:grid-cols-3">
          {points.map((p) => (
            <PointCard key={key(p)} point={p} data={data} scope={scope} />
          ))}
        </ul>
      )}
      <div className="flex flex-wrap gap-2">
        {more.length > 0 && (
          <Button variant="ghost" aria-expanded={all} onClick={() => setAll((x) => !x)}>
            {all ? a.fewer : a.more(more.length)}
          </Button>
        )}
        <Button variant="ghost" onClick={() => restore.mutate()} disabled={restore.isPending}>
          {a.showHidden}
        </Button>
      </div>
      <p className="max-w-3xl text-xs text-muted">{a.disclaimer}</p>
    </section>
  );
}
