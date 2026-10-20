import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import {
  adjustEnvelope,
  type GoalFundingOut,
  type GoalOut,
  removeAdjustment,
} from "../api/generated";
import { detailSentence } from "../auth/errors";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { amountInputShort, formatEurWhole, parseEurInput } from "../lib/money";
import { monthLabel, thisMonth } from "../lib/months";
import { GOALS_KEY } from "./shared";

const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";

/** What the goal holds on each line, and the hand adjustments of those envelopes (F-GOAL-3). */
export function Envelopes({ goal }: { goal: GoalOut }) {
  const { t } = useI18n();
  const g = t.goals;
  const [adjusting, setAdjusting] = useState<string | null>(null);
  if (goal.fundings.length === 0) return null;
  const num = "whitespace-nowrap px-3 py-2 text-right tabular";
  return (
    <section
      aria-labelledby="goal-envelopes"
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
    >
      <div>
        <h2 id="goal-envelopes" className="text-lg font-bold">
          {g.envelopes}
        </h2>
        <p className="text-sm text-muted">{g.envelopesHint}</p>
      </div>
      <div className="overflow-x-auto">
        <table aria-label={g.envelopes} className="w-full text-sm">
          <thead className="text-muted">
            <tr>
              <th scope="col" className="px-3 py-2 text-left font-medium">
                {g.envelopeLine}
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                {g.envelopeOpening}
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                {g.envelopeShare}
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                {g.envelopeHeld}
              </th>
              <td />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {goal.fundings.map((f) => (
              <tr key={f.line_id}>
                <th scope="row" className="px-3 py-2 text-left align-top font-normal">
                  {f.line_name}
                  <Adjustments goal={goal} funding={f} />
                  {adjusting === f.line_id && (
                    <AdjustForm goal={goal} funding={f} onDone={() => setAdjusting(null)} />
                  )}
                </th>
                <td className={`${num} align-top`}>{formatEurWhole(f.opening)}</td>
                <td className={`${num} align-top`}>{`${f.share} %`}</td>
                <td className={`${num} align-top font-semibold`}>{formatEurWhole(f.held)}</td>
                <td className="px-3 py-2 text-right align-top">
                  {adjusting !== f.line_id && (
                    <Button
                      variant="ghost"
                      aria-label={g.adjustOf(f.line_name)}
                      onClick={() => setAdjusting(f.line_id)}
                    >
                      {g.adjust}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Adjustments({ goal, funding }: { goal: GoalOut; funding: GoalFundingOut }) {
  const { t } = useI18n();
  const g = t.goals;
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const remove = useMutation({
    mutationFn: async (month: string) => {
      const { error: failure } = await removeAdjustment({
        path: { goal_id: goal.id, line_id: funding.line_id, month },
      });
      if (failure) throw failure;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: GOALS_KEY }),
    onError: (failure) => setError(detailSentence(failure) ?? t.errors.generic),
  });
  if (funding.adjustments.length === 0) return null;
  return (
    <ul className="mt-1 flex flex-col gap-1 text-xs text-muted">
      {funding.adjustments.map((a) => (
        <li key={a.month} className="flex flex-wrap items-center gap-2">
          {g.adjustedTo(formatEurWhole(a.amount), monthLabel(a.month))}
          <button
            type="button"
            aria-label={g.removeAdjustmentOf(monthLabel(a.month))}
            className="text-accent hover:underline"
            disabled={remove.isPending}
            onClick={() => remove.mutate(a.month)}
          >
            {g.removeAdjustment}
          </button>
        </li>
      ))}
      <ErrorAlert message={error} />
    </ul>
  );
}

function AdjustForm({
  goal,
  funding,
  onDone,
}: {
  goal: GoalOut;
  funding: GoalFundingOut;
  onDone: () => void;
}) {
  const { t } = useI18n();
  const g = t.goals;
  const queryClient = useQueryClient();
  const ids = { amount: useId(), month: useId() };
  const [amount, setAmount] = useState(amountInputShort(funding.held));
  const [month, setMonth] = useState(thisMonth());
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: async (value: string) => {
      const { error: failure } = await adjustEnvelope({
        path: { goal_id: goal.id, line_id: funding.line_id, month },
        body: { amount: value },
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
    const value = parseEurInput(amount);
    if (value === null || value.startsWith("-")) return setError(g.targetInvalid);
    setError(null);
    save.mutate(value);
  };
  return (
    <form
      onSubmit={submit}
      aria-label={g.adjustOf(funding.line_name)}
      className="mt-2 flex flex-wrap items-end gap-3"
    >
      <label htmlFor={ids.amount} className="flex flex-col gap-1 font-medium">
        {g.adjustAmount}
        <input
          id={ids.amount}
          inputMode="decimal"
          required
          className={`${fieldClass} w-32 tabular`}
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
      </label>
      <label htmlFor={ids.month} className="flex flex-col gap-1 font-medium">
        {g.adjustFrom}
        <input
          id={ids.month}
          type="month"
          required
          min={goal.start}
          max={thisMonth()}
          className={fieldClass}
          value={month}
          onChange={(e) => setMonth(e.target.value)}
        />
      </label>
      <Button type="submit" disabled={save.isPending}>
        {g.save}
      </Button>
      <Button variant="ghost" onClick={onDone}>
        {g.cancel}
      </Button>
      <ErrorAlert message={error} />
    </form>
  );
}
