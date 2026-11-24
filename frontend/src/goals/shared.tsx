import { type GoalOut, type GoalStatus, goalLines, type Tier } from "../api/generated";
import { useI18n } from "../i18n";
import { formatEurWhole, formatProgress } from "../lib/money";

/** The tiers by priority: the foundation, then the nearest deadlines first, pleasure last. */
export const TIERS: Tier[] = ["precaution", "short", "medium", "long", "pleasure"];

/** The order of the pyramid, from its foundation up: the long term at the base, the short term
 * at the top, under the golden capstone. */
export const PYRAMID: Tier[] = ["precaution", "long", "medium", "short", "pleasure"];

export const GOALS_KEY = ["goals"];

/** A precaution goal to fill first: the emergency fund the effort plan serves before the other
 * goals (F-GOAL-1). Another precaution goal, a survival kitty say, is a permanent goal otherwise. */
export const fillsFirst = (goal: Pick<GoalOut, "precaution" | "fill_first">) =>
  goal.precaution && goal.fill_first;

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
export function tierOf(
  deadline: string | null,
  month: string,
  precaution: boolean,
  pleasure = false,
): Tier {
  if (precaution) return "precaution";
  if (pleasure) return "pleasure";
  if (!deadline) return "short";
  const months = monthIndex(deadline) - monthIndex(month);
  if (months <= 12) return "short";
  return months <= 60 ? "medium" : "long";
}

/** A tier's colour: `goal-foundation` for the precaution, `goal-gold` for the capstone, then
 * its `goal-tier-*` token, darkest at the base (§7). */
export const tierColour = (tier: Tier) =>
  tier === "precaution"
    ? "var(--color-goal-foundation)"
    : tier === "pleasure"
      ? "var(--color-goal-gold)"
      : `var(--color-goal-tier-${PYRAMID.indexOf(tier)})`;

const STATUS_CLASS: Record<GoalStatus, string> = {
  reached: "bg-budget-under-bg text-budget-under-fg",
  ahead: "bg-budget-under-bg text-budget-under-fg",
  on: "bg-budget-on-bg text-budget-on-fg",
  behind: "bg-budget-over-bg text-budget-over-fg",
  fill_first: "border border-[var(--color-goal-priority)] text-fg",
  open: "bg-budget-on-bg text-budget-on-fg",
  locked: "bg-budget-on-bg text-muted",
};

const STATUS_ICON: Record<GoalStatus, string> = {
  reached: "✓",
  ahead: "▲",
  on: "●",
  behind: "▼",
  fill_first: "!",
  open: "○",
  locked: "🔒",
};

const BAR_COLOUR: Record<GoalStatus, string> = {
  reached: "var(--color-chart-under)",
  ahead: "var(--color-chart-under)",
  on: "var(--color-chart-on)",
  behind: "var(--color-progress-over)",
  fill_first: "var(--color-goal-priority)",
  open: "var(--color-chart-on)",
  locked: "var(--color-chart-on)",
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
    formatProgress(goal.progress),
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

/** A professional goal's mark (F-GOAL-11): a briefcase in `goal-pro-mark`. */
export function Briefcase({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 16 14"
      aria-hidden="true"
      className={`inline-block h-3.5 w-4 ${className}`}
      fill="none"
      stroke="var(--color-goal-pro-mark)"
      strokeWidth={1.5}
    >
      <rect
        x={1}
        y={3.5}
        width={14}
        height={9.5}
        rx={1.5}
        fill="var(--color-goal-pro-mark)"
        fillOpacity={0.18}
      />
      <path d="M5.5 3.5V1.5h5v2M1 8h14" />
    </svg>
  );
}

/** A professional goal's cost and what others pay: "€2,400, of which €1,500 from the CPF: €900
 * to gather" (F-GOAL-11). */
export function costSentence(goal: GoalOut, t: ReturnType<typeof useI18n>["t"]): string | null {
  if (goal.pro_type === null || goal.cost === null) return null;
  const aids = goal.aids.map((a) => t.goals.aidFrom[a.source](formatEurWhole(a.amount)));
  return t.goals.costOf(formatEurWhole(goal.cost), aids, formatEurWhole(goal.target));
}

/** The professional goal's type with its briefcase. */
export function ProBadge({ goal }: { goal: GoalOut }) {
  const { t } = useI18n();
  if (goal.pro_type === null) return null;
  return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold text-fg">
      <Briefcase />
      {t.goals.professional} · {t.goals.proTypes[goal.pro_type]}
    </span>
  );
}
