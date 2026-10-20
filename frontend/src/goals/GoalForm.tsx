import { useMutation, useQuery, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type FormEvent, useId, useState } from "react";
import {
  createGoal,
  type GoalFundingIn,
  type GoalOut,
  listWealthCategories,
  listWealthLines,
  type PrecautionProposalOut,
  precautionProposal,
  updateGoal,
  type Visibility,
} from "../api/generated";
import { detailSentence } from "../auth/errors";
import { meQuery } from "../auth/session";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { amountInputShort, formatEurWhole, parseEurInput } from "../lib/money";
import { thisMonth } from "../lib/months";
import { GOALS_KEY, goalLinesQuery, tierOf } from "./shared";

type Envelope = { share: number; opening: string };

const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";
const labelClass = "flex flex-col gap-1 text-sm font-medium";
const hintClass = "font-normal text-muted";
const VISIBILITIES: Visibility[] = ["shared", "private", "joint"];
const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1);

/** Create a goal, or edit one (F-GOAL-1 to 3). */
export function GoalForm({ goal, onDone }: { goal?: GoalOut; onDone: () => void }) {
  const { t } = useI18n();
  const g = t.goals;
  const queryClient = useQueryClient();
  const { data: user } = useSuspenseQuery(meQuery);
  const ids = {
    name: useId(),
    target: useId(),
    deadline: useId(),
    start: useId(),
    who: useId(),
    precaution: useId(),
    permanent: useId(),
  };
  const lines = useQuery({
    queryKey: ["wealth", "lines"],
    queryFn: async () => (await listWealthLines({ throwOnError: true })).data,
  });
  const categories = useQuery({
    queryKey: ["wealth", "categories"],
    queryFn: async () => (await listWealthCategories({ throwOnError: true })).data,
  });
  const free = useQuery({
    ...goalLinesQuery,
    select: (rows) => new Map(rows.map((row) => [row.line_id, row.free])),
  });
  const [precaution, setPrecaution] = useState(goal?.precaution ?? false);
  const [isPermanent, setPermanent] = useState(goal?.permanent ?? false);
  // The emergency fund is always permanent.
  const permanent = precaution || isPermanent;
  const [name, setName] = useState(goal?.name ?? "");
  const [target, setTarget] = useState(goal ? amountInputShort(goal.target) : "");
  const [deadline, setDeadline] = useState(goal?.deadline ?? "");
  const [start, setStart] = useState(goal?.start ?? thisMonth());
  const [visibility, setVisibility] = useState<Visibility>(goal?.visibility ?? "shared");
  const [shares, setShares] = useState<Map<string, Envelope>>(
    () =>
      new Map(
        goal?.fundings.map((f) => [
          f.line_id,
          { share: f.share, opening: Number(f.opening) ? amountInputShort(f.opening) : "" },
        ]) ?? [],
      ),
  );
  const [error, setError] = useState<string | null>(null);
  const canChangeWho = !goal || goal.owner_id === user.id;

  const assets = new Set(categories.data?.filter((c) => c.kind === "asset").map((c) => c.id));
  const options = (lines.data ?? []).filter(
    (line) => assets.has(line.category_id) && (line.closed_from === null || shares.has(line.id)),
  );

  const save = useMutation({
    mutationFn: async ({ amount, fundings }: { amount: string; fundings: GoalFundingIn[] }) => {
      const body = {
        name,
        precaution,
        permanent,
        target: amount,
        deadline: deadline || null,
        start,
        fundings,
        ...(canChangeWho ? { visibility } : {}),
      };
      const { error: failure } = goal
        ? await updateGoal({ path: { goal_id: goal.id }, body })
        : await createGoal({ body: { ...body, visibility } });
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
    const amount = parseEurInput(target);
    if (amount === null || Number(amount) <= 0) return setError(g.targetInvalid);
    const fundings: GoalFundingIn[] = [];
    for (const [line_id, { share, opening }] of shares) {
      const parsed = opening.trim() ? parseEurInput(opening) : "0.00";
      if (parsed === null || parsed.startsWith("-")) return setError(g.targetInvalid);
      fundings.push({ line_id, share, opening: parsed });
    }
    setError(null);
    save.mutate({ amount, fundings });
  };

  const toggle = (lineId: string, on: boolean) =>
    setShares((current) => {
      const next = new Map(current);
      if (on) next.set(lineId, { share: 100, opening: "" });
      else next.delete(lineId);
      return next;
    });
  const change = (lineId: string, fields: Partial<Envelope>) =>
    setShares((current) => {
      const before = current.get(lineId);
      return before ? new Map(current).set(lineId, { ...before, ...fields }) : current;
    });

  return (
    <form
      onSubmit={submit}
      aria-label={goal ? g.formEdit : g.formNew}
      className="flex max-w-2xl flex-col gap-4 rounded-lg border border-border bg-surface p-4"
    >
      <h2 className="text-lg font-bold">{goal ? g.formEdit : g.formNew}</h2>
      <div className="flex flex-col gap-1 text-sm">
        <label htmlFor={ids.precaution} className="flex items-center gap-2 font-medium">
          <input
            id={ids.precaution}
            type="checkbox"
            aria-describedby={`${ids.precaution}-hint`}
            checked={precaution}
            onChange={(e) => setPrecaution(e.target.checked)}
          />
          {g.isPrecaution}
        </label>
        <p id={`${ids.precaution}-hint`} className={hintClass}>
          {g.isPrecautionHint}
        </p>
      </div>
      <div className="flex flex-col gap-1 text-sm">
        <label htmlFor={ids.permanent} className="flex items-center gap-2 font-medium">
          <input
            id={ids.permanent}
            type="checkbox"
            aria-describedby={`${ids.permanent}-hint`}
            checked={permanent}
            disabled={precaution}
            onChange={(e) => setPermanent(e.target.checked)}
          />
          {g.isPermanent}
        </label>
        <p id={`${ids.permanent}-hint`} className={hintClass}>
          {g.isPermanentHint}
        </p>
      </div>
      <label htmlFor={ids.name} className={labelClass}>
        {g.name}
        <input
          id={ids.name}
          required
          maxLength={100}
          className={fieldClass}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      <label htmlFor={ids.target} className={labelClass}>
        {g.target}
        <input
          id={ids.target}
          required
          inputMode="decimal"
          className={`${fieldClass} tabular`}
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        />
      </label>
      {precaution && <Proposal onUse={(amount) => setTarget(amountInputShort(amount))} />}
      <div className="grid gap-4 sm:grid-cols-2">
        <div className={labelClass}>
          <label htmlFor={ids.deadline}>{g.deadlineField}</label>
          <input
            id={ids.deadline}
            type="month"
            required={!permanent}
            aria-describedby={`${ids.deadline}-hint`}
            className={fieldClass}
            value={deadline}
            onChange={(e) => setDeadline(e.target.value)}
          />
          <p id={`${ids.deadline}-hint`} className={hintClass}>
            {permanent && !deadline
              ? g.deadlineOptional
              : g.tierOf(g.tiers[tierOf(deadline || null, thisMonth(), precaution)])}
          </p>
        </div>
        <div className={labelClass}>
          <label htmlFor={ids.start}>{g.start}</label>
          <input
            id={ids.start}
            type="month"
            required
            max={thisMonth()}
            aria-describedby={`${ids.start}-hint`}
            className={fieldClass}
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
          <p id={`${ids.start}-hint`} className={hintClass}>
            {g.startHint}
          </p>
        </div>
      </div>
      {canChangeWho && (
        <label htmlFor={ids.who} className={labelClass}>
          {g.visibility}
          <select
            id={ids.who}
            className={fieldClass}
            value={visibility}
            onChange={(e) => setVisibility(e.target.value as Visibility)}
          >
            {VISIBILITIES.map((v) => (
              <option key={v} value={v}>
                {g.visibilities[v]}
              </option>
            ))}
          </select>
        </label>
      )}
      <fieldset className="flex flex-col gap-2 text-sm">
        <legend className="mb-1 font-medium">{g.fundings}</legend>
        <p className="text-muted">{g.fundingsHint}</p>
        {lines.data && options.length === 0 && <p>{g.noLines}</p>}
        {options.map((line) => {
          const envelope = shares.get(line.id);
          const lineFree = free.data?.get(line.id);
          return (
            <div
              key={line.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border px-3 py-2"
            >
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={envelope !== undefined}
                  onChange={(e) => toggle(line.id, e.target.checked)}
                />
                {line.name}
                <span className="text-muted">· {t.wealth.visibilities[line.visibility]}</span>
                {lineFree !== undefined && (
                  <span className="text-muted tabular">· {g.free(formatEurWhole(lineFree))}</span>
                )}
              </label>
              {envelope !== undefined && (
                <span className="flex flex-wrap items-center gap-2">
                  <input
                    aria-label={g.openingOf(line.name)}
                    inputMode="decimal"
                    placeholder="0"
                    className={`${fieldClass} w-28 py-1 text-right tabular`}
                    value={envelope.opening}
                    onChange={(e) => change(line.id, { opening: e.target.value })}
                  />
                  <span aria-hidden="true">€ {g.openingLabel}</span>
                  <input
                    aria-label={g.shareOf(line.name)}
                    type="number"
                    min={1}
                    max={100}
                    required
                    className={`${fieldClass} w-20 py-1 text-right tabular`}
                    value={envelope.share}
                    onChange={(e) => change(line.id, { share: Number(e.target.value) })}
                  />
                  <span aria-hidden="true">{g.sharePercent}</span>
                </span>
              )}
            </div>
          );
        })}
      </fieldset>
      <ErrorAlert message={error} />
      <div className="flex gap-3">
        <Button type="submit" disabled={save.isPending}>
          {goal ? g.save : g.create}
        </Button>
        <Button variant="ghost" onClick={onDone}>
          {g.cancel}
        </Button>
      </div>
    </form>
  );
}

/** A target for the emergency fund: months of fixed expenses (F-GOAL-2). */
function Proposal({ onUse }: { onUse: (amount: string) => void }) {
  const { t } = useI18n();
  const g = t.goals;
  const id = useId();
  const [months, setMonths] = useState(6);
  const [result, setResult] = useState<PrecautionProposalOut | null>(null);
  const ask = useMutation({
    mutationFn: async (count: number) =>
      (await precautionProposal({ query: { months: count }, throwOnError: true })).data,
    onSuccess: setResult,
  });
  return (
    <div className="flex flex-col gap-2 rounded-md border border-dashed border-border p-3 text-sm">
      <div className="flex flex-wrap items-end gap-3">
        <label htmlFor={id} className={labelClass}>
          {g.proposalMonths}
          <select
            id={id}
            className={fieldClass}
            value={months}
            onChange={(e) => setMonths(Number(e.target.value))}
          >
            {MONTHS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <Button variant="ghost" onClick={() => ask.mutate(months)} disabled={ask.isPending}>
          {g.proposal}
        </Button>
      </div>
      {ask.isError && <ErrorAlert message={t.errors.generic} />}
      {result && result.items.length === 0 && (
        <p>
          {g.proposalNone}{" "}
          <Link to="/recurring" className="text-accent hover:underline">
            {g.openRecurring}
          </Link>
        </p>
      )}
      {result && result.items.length > 0 && (
        <>
          <p className="font-semibold">
            {g.proposalOf(
              result.months,
              formatEurWhole(result.monthly_fixed),
              formatEurWhole(result.amount),
            )}
          </p>
          <details>
            <summary className="cursor-pointer text-muted">{g.proposalItems}</summary>
            <ul className="mt-1 flex flex-col gap-0.5">
              {result.items.map((item) => (
                <li key={`${item.label}-${item.frequency}`} className="flex justify-between gap-2">
                  <span>{item.label}</span>
                  <span className="tabular">{g.perMonthShort(formatEurWhole(item.monthly))}</span>
                </li>
              ))}
            </ul>
          </details>
          <div>
            <Button variant="ghost" onClick={() => onUse(result.amount)}>
              {g.useProposal}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
