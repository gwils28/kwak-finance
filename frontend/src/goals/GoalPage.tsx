import { useMutation, useQuery, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { type FormEvent, useId, useState } from "react";
import {
  type ClosedAs,
  deleteGoal,
  type GoalDetailOut,
  type GoalOut,
  getGoal,
  updateGoal,
} from "../api/generated";
import { detailSentence } from "../auth/errors";
import { meQuery } from "../auth/session";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { formatEurSigned, formatEurWhole, formatPercent } from "../lib/money";
import { monthLabel, shiftMonth, thisMonth } from "../lib/months";
import { Envelopes } from "./Envelopes";
import { estimateText, paceSentence } from "./GoalCard";
import { GoalForm } from "./GoalForm";
import { GOALS_KEY, StatusChip } from "./shared";
import { Trajectory } from "./Trajectory";

type Panel = "edit" | "close" | "delete" | null;

/** One goal: its estimates, its trajectory and its months (F-GOAL-7, 8). */
export function GoalPage({ goalId }: { goalId: string }) {
  const { t } = useI18n();
  const g = t.goals;
  const [panel, setPanel] = useState<Panel>(null);
  const query = useQuery({
    queryKey: [...GOALS_KEY, "detail", goalId],
    queryFn: async () => (await getGoal({ path: { goal_id: goalId }, throwOnError: true })).data,
    retry: false,
  });
  const detail = query.data;
  return (
    <div className="flex flex-col gap-6">
      <Link to="/goals" className="text-sm text-accent hover:underline">
        ← {g.back}
      </Link>
      {query.isPending && <p className="text-sm text-muted">{t.common.loading}</p>}
      {query.isError && <ErrorAlert message={g.notFound} />}
      {detail && (
        <>
          <Header goal={detail.goal} onAction={setPanel} />
          {panel === "edit" && <GoalForm goal={detail.goal} onDone={() => setPanel(null)} />}
          {panel === "close" && <CloseGoal goal={detail.goal} onDone={() => setPanel(null)} />}
          {panel === "delete" && <DeleteGoal goal={detail.goal} onDone={() => setPanel(null)} />}
          <Tiles goal={detail.goal} />
          <section
            aria-labelledby="goal-trajectory"
            className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
          >
            <h2 id="goal-trajectory" className="text-lg font-bold">
              {g.trajectory}
            </h2>
            <Trajectory detail={detail} />
          </section>
          <Envelopes goal={detail.goal} />
          <Months detail={detail} />
        </>
      )}
    </div>
  );
}

function Header({ goal, onAction }: { goal: GoalOut; onAction: (panel: Panel) => void }) {
  const { t } = useI18n();
  const g = t.goals;
  const { data: user } = useSuspenseQuery(meQuery);
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const reopen = useMutation({
    mutationFn: async () => {
      const { error: failure } = await updateGoal({
        path: { goal_id: goal.id },
        body: { closed_from: null },
      });
      if (failure) throw failure;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: GOALS_KEY }),
    onError: (failure) => setError(detailSentence(failure) ?? t.errors.generic),
  });
  const sentence = paceSentence(goal, t);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-black tracking-tight">{goal.name}</h1>
            {goal.closed_as ? (
              <span className="text-sm text-muted">
                {g.closedOn(
                  g.closedAs[goal.closed_as],
                  goal.closed_from ? monthLabel(shiftMonth(goal.closed_from, -1)) : "",
                )}
              </span>
            ) : (
              <StatusChip status={goal.status} />
            )}
          </div>
          <p className="text-sm text-muted">
            {g.subtitle(
              g.tiers[goal.tier],
              goal.deadline ? g.deadlineOn(monthLabel(goal.deadline)) : g.noDeadline,
              formatEurWhole(goal.target),
            )}
          </p>
          {sentence && !goal.closed_as && <p className="text-sm">{sentence}</p>}
          <p className="text-sm text-muted">
            {g.fundedByList(
              goal.fundings.length === 0
                ? g.noFunding
                : goal.fundings
                    .map((f) => g.fundingHeld(f.line_name, formatEurWhole(f.held), f.share))
                    .join(", "),
            )}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="ghost" onClick={() => onAction("edit")}>
            {g.edit}
          </Button>
          {goal.closed_as ? (
            <Button variant="ghost" onClick={() => reopen.mutate()} disabled={reopen.isPending}>
              {g.reopen}
            </Button>
          ) : (
            <Button variant="ghost" onClick={() => onAction("close")}>
              {goal.permanent ? g.cancelGoal : g.close}
            </Button>
          )}
          {goal.owner_id === user.id && (
            <Button variant="ghost" onClick={() => onAction("delete")}>
              {g.delete}
            </Button>
          )}
        </div>
      </div>
      <ErrorAlert message={error} />
    </div>
  );
}

function Tile({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-border bg-surface p-4">
      <h2 className="text-sm text-muted">{label}</h2>
      <p className="text-2xl font-semibold tabular">{value}</p>
      <p className="text-xs text-muted">{note}</p>
    </div>
  );
}

function Tiles({ goal }: { goal: GoalOut }) {
  const { t } = useI18n();
  const g = t.goals;
  const early = goal.months_early;
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <Tile
        label={g.tiles.value}
        value={formatEurWhole(goal.value)}
        note={g.ofTheTarget(formatPercent(goal.progress))}
      />
      <Tile
        label={g.tiles.remaining}
        value={formatEurWhole(goal.remaining)}
        note={goal.months_left !== null ? g.monthsLeft(goal.months_left) : g.asSoonAsPossible}
      />
      <Tile
        label={g.tiles.required}
        value={goal.required !== null ? g.perMonthShort(formatEurWhole(goal.required)) : "—"}
        note={goal.required !== null ? g.toKeepDeadline : ""}
      />
      <Tile
        label={g.tiles.actual}
        value={goal.actual !== null ? g.perMonthShort(formatEurWhole(goal.actual)) : "—"}
        note={g.lastSixMonths}
      />
      <Tile
        label={g.tiles.estimated}
        value={estimateText(goal, t)}
        note={early === null ? "" : early >= 0 ? g.monthsEarly(early) : g.monthsLate(-early)}
      />
    </div>
  );
}

function Months({ detail }: { detail: GoalDetailOut }) {
  const { t } = useI18n();
  const g = t.goals;
  const num = "whitespace-nowrap px-3 py-2 text-right tabular";
  const signed = (amount: string | null) => (amount === null ? "—" : formatEurSigned(amount));
  return (
    <section
      aria-labelledby="goal-months"
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
    >
      <h2 id="goal-months" className="text-lg font-bold">
        {g.months}
      </h2>
      <div className="overflow-x-auto">
        <table aria-label={g.months} className="w-full text-sm">
          <thead className="text-muted">
            <tr>
              <th scope="col" className="px-3 py-2 text-left font-medium">
                {g.month}
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                {g.value}
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                {g.gained}
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                {g.expected}
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                {g.gap}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {[...detail.months].reverse().map((m) => (
              <tr key={m.month}>
                <th scope="row" className="px-3 py-2 text-left font-normal">
                  {monthLabel(m.month)}
                </th>
                <td className={num}>{formatEurWhole(m.value)}</td>
                <td className={num}>{signed(m.gained)}</td>
                <td className={num}>{m.expected === null ? "—" : formatEurWhole(m.expected)}</td>
                <td className={num}>{signed(m.gap)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted">{g.fundingNote}</p>
    </section>
  );
}

function CloseGoal({ goal, onDone }: { goal: GoalOut; onDone: () => void }) {
  const { t } = useI18n();
  const g = t.goals;
  const queryClient = useQueryClient();
  const id = useId();
  const [month, setMonth] = useState(thisMonth());
  const [as, setAs] = useState<ClosedAs>(goal.permanent ? "cancelled" : "archived");
  const [error, setError] = useState<string | null>(null);
  const close = useMutation({
    mutationFn: async () => {
      const { error: failure } = await updateGoal({
        path: { goal_id: goal.id },
        body: { closed_from: month, closed_as: as },
      });
      if (failure) throw failure;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: GOALS_KEY });
      onDone();
    },
    onError: (failure) => setError(detailSentence(failure) ?? t.errors.generic),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    close.mutate();
  };
  return (
    <form
      onSubmit={submit}
      aria-label={g.closeTitle}
      className="flex max-w-xl flex-col gap-3 rounded-lg border border-border bg-surface p-4 text-sm"
    >
      <h2 className="text-lg font-bold">{g.closeTitle}</h2>
      <p className="text-muted">{g.closeHint}</p>
      <label htmlFor={id} className="flex flex-col gap-1 font-medium">
        {g.closeFrom}
        <input
          id={id}
          type="month"
          required
          min={goal.start}
          max={thisMonth()}
          className="rounded-md border border-border bg-surface px-3 py-2"
          value={month}
          onChange={(e) => setMonth(e.target.value)}
        />
      </label>
      <fieldset className="flex flex-col gap-1">
        <legend className="mb-1 font-medium">{g.closeAs}</legend>
        {(goal.permanent ? (["cancelled"] as const) : (["archived", "cancelled"] as const)).map(
          (value) => (
            <label key={value} className="flex items-center gap-2">
              <input type="radio" checked={as === value} onChange={() => setAs(value)} />
              {g.closedAs[value]}
            </label>
          ),
        )}
      </fieldset>
      <ErrorAlert message={error} />
      <div className="flex gap-3">
        <Button type="submit" disabled={close.isPending}>
          {g.close}
        </Button>
        <Button variant="ghost" onClick={onDone}>
          {g.cancel}
        </Button>
      </div>
    </form>
  );
}

function DeleteGoal({ goal, onDone }: { goal: GoalOut; onDone: () => void }) {
  const { t } = useI18n();
  const g = t.goals;
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const remove = useMutation({
    mutationFn: async () => {
      const { error: failure } = await deleteGoal({ path: { goal_id: goal.id } });
      if (failure) throw failure;
    },
    onSuccess: async () => {
      queryClient.removeQueries({ queryKey: [...GOALS_KEY, "detail", goal.id] });
      await queryClient.invalidateQueries({ queryKey: GOALS_KEY });
      await navigate({ to: "/goals" });
    },
    onError: (failure) => setError(detailSentence(failure) ?? t.errors.generic),
  });
  return (
    <div
      role="alertdialog"
      aria-label={g.delete}
      className="flex max-w-xl flex-col gap-3 rounded-lg border border-negative bg-surface p-4 text-sm"
    >
      <p>{g.confirmDelete}</p>
      <ErrorAlert message={error} />
      <div className="flex gap-3">
        <Button onClick={() => remove.mutate()} disabled={remove.isPending}>
          {g.confirm}
        </Button>
        <Button variant="ghost" onClick={onDone}>
          {g.cancel}
        </Button>
      </div>
    </div>
  );
}
