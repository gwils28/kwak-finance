import { type GoalOut, type GoalStatus, goalLines, type Tier } from "../api/generated";
import { useI18n } from "../i18n";
import { formatEurWhole, formatPercent } from "../lib/money";

/** The tiers by priority: the foundation, then the nearest deadlines first. */
export const TIERS: Tier[] = ["precaution", "short", "medium", "long"];

/** The order of the pyramid, from its foundation up: the long term at the base, the short term at the top. */
export const PYRAMID: Tier[] = ["precaution", "long", "medium", "short"];

export const GOALS_KEY = ["goals"];

/** Each visible asset line this month, and what the viewer's goals set aside on it. */
export const goalLinesQuery = {
  queryKey: [...GOALS_KEY, "lines"],
  queryFn: async () => (await goalLines({ throwOnError: true })).data,
};

const monthIndex = (month: string) => {
  const [y, m] = month.split("-").map(Number) as [number, number];
  return y * 12 + m - 1;
};

/** The tier a deadline gives, as the API computes it (F-GOAL-1): a preview in the form. */
export function tierOf(deadline: string | null, month: string, precaution: boolean): Tier {
  if (precaution) return "precaution";
  if (!deadline) return "short";
  const months = monthIndex(deadline) - monthIndex(month);
  if (months <= 12) return "short";
  return months <= 60 ? "medium" : "long";
}

/** A tier's colour: `goal-foundation` for the precaution, then its `goal-tier-*` token, darkest at the base (§7). */
export const tierColour = (tier: Tier) =>
  tier === "precaution"
    ? "var(--color-goal-foundation)"
    : `var(--color-goal-tier-${PYRAMID.indexOf(tier)})`;

const STATUS_CLASS: Record<GoalStatus, string> = {
  reached: "bg-budget-under-bg text-budget-under-fg",
  ahead: "bg-budget-under-bg text-budget-under-fg",
  on: "bg-budget-on-bg text-budget-on-fg",
  behind: "bg-budget-over-bg text-budget-over-fg",
  fill_first: "border border-[var(--color-goal-priority)] text-fg",
  open: "bg-budget-on-bg text-budget-on-fg",
};

const STATUS_ICON: Record<GoalStatus, string> = {
  reached: "✓",
  ahead: "▲",
  on: "●",
  behind: "▼",
  fill_first: "!",
  open: "○",
};

const BAR_COLOUR: Record<GoalStatus, string> = {
  reached: "var(--color-chart-under)",
  ahead: "var(--color-chart-under)",
  on: "var(--color-chart-on)",
  behind: "var(--color-progress-over)",
  fill_first: "var(--color-goal-priority)",
  open: "var(--color-chart-on)",
};

/** The status with its icon and word: colour is never the only cue. */
export function StatusChip({ status }: { status: GoalStatus }) {
  const { t } = useI18n();
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_CLASS[status]}`}
    >
      <span aria-hidden="true">{STATUS_ICON[status]}</span>
      {t.goals.status[status]}
    </span>
  );
}

/** Progress towards the target, with a marker where the goal should stand by now. */
export function Gauge({ goal }: { goal: GoalOut }) {
  const { t } = useI18n();
  const target = Number(goal.target);
  const share = (amount: string) => Math.min(100, (100 * Number(amount)) / target);
  const label = t.goals.gauge(
    formatEurWhole(goal.value),
    formatEurWhole(goal.target),
    formatPercent(goal.progress),
  );
  return (
    <>
      <span className="sr-only">{label}</span>
      <div aria-hidden="true" className="relative mt-2 h-3 rounded-full bg-budget-on-bg">
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ width: `${share(goal.value)}%`, background: BAR_COLOUR[goal.status] }}
        />
        {goal.expected !== null && goal.status !== "reached" && (
          <div
            title={t.goals.paceMarker(formatEurWhole(goal.expected))}
            className="absolute -inset-y-1 w-0.5 bg-fg"
            style={{ left: `${share(goal.expected)}%` }}
          />
        )}
      </div>
    </>
  );
}
