import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type ReactNode, useState } from "react";
import { type ClosedAs, type GoalOut, type GoalPlanOut, updateGoal } from "../api/generated";
import { detailSentence } from "../auth/errors";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { formatEurWhole, formatProgress } from "../lib/money";
import { monthLabel, shiftMonth } from "../lib/months";
import { GoalForm } from "./GoalForm";
import {
  costSentence,
  fillsFirst,
  Gauge,
  GOALS_KEY,
  ProBadge,
  StatusChip,
  tierColour,
} from "./shared";

/** The sentence under a goal with a deadline: early, on time or late at its actual pace. */
export function paceSentence(goal: GoalOut, t: ReturnType<typeof useI18n>["t"]): string | null {
  if (goal.months_early === null || goal.status === "reached") return null;
  if (goal.months_early >= 0) return t.goals.early(goal.months_early);
  return t.goals.late(-goal.months_early, goal.extra ? formatEurWhole(goal.extra) : null);
}

/** What the estimated date says: a month, never, or not enough history yet. */
export function estimateText(goal: GoalOut, t: ReturnType<typeof useI18n>["t"]): string {
  if (goal.estimated) return monthLabel(goal.estimated);
  return goal.never ? t.goals.never : t.goals.notEnoughHistory;
}

function Fact({ term, children }: { term: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted">{term}</dt>
      <dd>{children}</dd>
    </>
  );
}

/** One goal on the Goals page: its gauge and estimates, edited, archived or cancelled in place;
 * it opens the goal's page. */
export function GoalCard({
  goal,
  plan,
  month,
}: {
  goal: GoalOut;
  plan: GoalPlanOut;
  month: string;
}) {
  const { t } = useI18n();
  const g = t.goals;
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // A goal to renew archived short of its target asks about its next cycle (F-GOAL-11).
  const [asking, setAsking] = useState(false);
  // The goal leaves the pyramid and the page at once (F-GOAL-8).
  const close = useMutation({
    mutationFn: async ({ as, nextCycle = true }: { as: ClosedAs; nextCycle?: boolean }) => {
      const { error: failure } = await updateGoal({
        path: { goal_id: goal.id },
        // From next month: this month still counts.
        body: {
          closed_from: shiftMonth(month, 1),
          closed_as: as,
          ...(nextCycle ? {} : { next_cycle: false }),
        },
      });
      if (failure) throw failure;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: GOALS_KEY }),
    onError: (failure) => setError(detailSentence(failure) ?? t.errors.generic),
  });
  const sentence = paceSentence(goal, t);
  const cost = costSentence(goal, t);
  const received = goal.aids.some((a) => a.received) && goal.status !== "reached";
  const toRenew = goal.renew_years !== null;
  // A precaution goal not to fill first reads as a permanent goal (F-GOAL-1).
  const precaution = fillsFirst(goal);
  const fillBy =
    precaution && plan.months_to_fill !== null ? shiftMonth(month, plan.months_to_fill) : null;
  if (editing) {
    return (
      <div className="md:col-span-2 xl:col-span-3">
        <GoalForm goal={goal} onDone={() => setEditing(false)} />
      </div>
    );
  }
  return (
    <article
      aria-label={goal.name}
      className="flex flex-col gap-2 rounded-lg border border-l-4 border-border bg-surface p-4"
      style={{
        borderLeftColor:
          goal.pro_type === null ? tierColour(goal.tier) : "var(--color-goal-pro-mark)",
      }}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-bold">
          <Link
            to="/goals/$goalId"
            params={{ goalId: goal.id }}
            className="hover:text-accent hover:underline"
          >
            {goal.name}
          </Link>
        </h3>
        <StatusChip status={goal.status} />
      </div>
      {goal.permanent && <p className="-mt-1 text-xs text-muted">{g.permanent}</p>}
      <ProBadge goal={goal} />
      <Gauge goal={goal} />
      <p className="flex justify-between text-sm">
        <span className="tabular">
          <strong>{formatEurWhole(goal.value)}</strong>{" "}
          <span className="text-muted">/ {formatEurWhole(goal.target)}</span>
        </span>
        <strong className="tabular">{formatProgress(goal.progress)}</strong>
      </p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        {precaution ? (
          <>
            {goal.actual !== null && (
              <Fact term={g.actualEffort}>{g.perMonthShort(formatEurWhole(goal.actual))}</Fact>
            )}
            {goal.effort !== null && (
              <Fact term={g.reservedEffort}>{g.perMonthShort(formatEurWhole(goal.effort))}</Fact>
            )}
            {fillBy && goal.status !== "reached" && (
              <Fact term={g.filledBy}>{monthLabel(fillBy)}</Fact>
            )}
          </>
        ) : (
          <>
            <Fact term={g.deadline}>
              {goal.deadline ? monthLabel(goal.deadline) : g.noDeadline}
              {goal.months_left !== null && (
                <span className="text-muted"> · {g.monthsLeft(goal.months_left)}</span>
              )}
            </Fact>
            <Fact term={g.estimated}>{estimateText(goal, t)}</Fact>
            {goal.required !== null && goal.status !== "reached" && (
              <Fact term={g.requiredEffort}>{g.perMonthShort(formatEurWhole(goal.required))}</Fact>
            )}
            {goal.actual !== null && (
              <Fact term={g.actualEffort}>{g.perMonthShort(formatEurWhole(goal.actual))}</Fact>
            )}
          </>
        )}
        {cost && <Fact term={g.cost}>{cost}</Fact>}
        {goal.renew_years !== null && goal.renewal_monthly !== null && (
          <Fact term={g.renewed}>
            {g.renewEvery(goal.renew_years, formatEurWhole(goal.renewal_monthly))}
          </Fact>
        )}
        <Fact term={g.fundedBy}>
          {goal.fundings.length === 0
            ? g.noFunding
            : goal.fundings.map((f) => `${f.line_name} (${formatEurWhole(f.held)})`).join(", ")}
        </Fact>
      </dl>
      {sentence && <p className="text-xs text-muted">{sentence}</p>}
      {toRenew && <p className="text-xs text-muted">{g.renewCostNote}</p>}
      {received && <p className="text-xs">{g.receivedNote}</p>}
      <div className="mt-auto flex flex-wrap gap-2 border-t border-border pt-2">
        <Button variant="ghost" aria-label={g.editOf(goal.name)} onClick={() => setEditing(true)}>
          {g.edit}
        </Button>
        {/* A permanent goal stays in view: it can be cancelled, not archived. */}
        {(goal.permanent ? (["cancelled"] as const) : (["archived", "cancelled"] as const)).map(
          (as) =>
            as === "cancelled" ? (
              // Abandoning is the quiet action, set apart at the end of the row.
              <button
                key={as}
                type="button"
                aria-label={g.cancelOf(goal.name)}
                disabled={close.isPending}
                onClick={() => close.mutate({ as })}
                className="ml-auto rounded-md px-2 py-2 text-sm text-muted underline-offset-2 hover:text-negative hover:underline disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-accent"
              >
                {g.cancelGoal}
              </button>
            ) : (
              <Button
                key={as}
                variant="ghost"
                aria-label={g.archiveOf(goal.name)}
                disabled={close.isPending}
                onClick={() =>
                  as === "archived" && toRenew && goal.status !== "reached"
                    ? setAsking(true)
                    : close.mutate({ as })
                }
              >
                {g.archive}
              </Button>
            ),
        )}
      </div>
      {asking && (
        <fieldset className="flex flex-col gap-2 text-sm">
          <legend>{g.nextCycleQuestion}</legend>
          <div className="flex flex-wrap gap-2">
            <Button disabled={close.isPending} onClick={() => close.mutate({ as: "archived" })}>
              {g.archiveWithNext}
            </Button>
            <Button
              variant="ghost"
              disabled={close.isPending}
              onClick={() => close.mutate({ as: "archived", nextCycle: false })}
            >
              {g.archiveWithoutNext}
            </Button>
            <Button variant="ghost" onClick={() => setAsking(false)}>
              {g.cancel}
            </Button>
          </div>
        </fieldset>
      )}
      <ErrorAlert message={error} />
    </article>
  );
}
