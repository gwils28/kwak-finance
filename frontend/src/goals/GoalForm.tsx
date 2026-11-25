import { useMutation, useQuery, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type FormEvent, useId, useState } from "react";
import {
  type AidSource,
  createGoal,
  type GoalAidIn,
  type GoalFundingIn,
  type GoalOut,
  listWealthCategories,
  listWealthLines,
  type PrecautionProposalOut,
  type ProType,
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
import { Briefcase, GOALS_KEY, goalLinesQuery, tierOf } from "./shared";

type Envelope = { share: number; opening: string };
type Aid = { source: AidSource; amount: string; received: boolean };

const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";
const labelClass = "flex flex-col gap-1 text-sm font-medium";
const hintClass = "font-normal text-muted";
const VISIBILITIES: Visibility[] = ["shared", "private", "joint"];

type Kind = "precaution" | "project" | "pleasure" | "professional";
const KINDS: Kind[] = ["precaution", "project", "pleasure", "professional"];
const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1);
const PRO_TYPES: ProType[] = ["equipment", "training", "business", "career_change", "move"];
const SOURCES: AidSource[] = ["cpf", "employer", "france_travail", "honour_loan", "other"];
/** The CPF never pays for equipment nor a move (F-GOAL-11). */
const CPF_TYPES: ProType[] = ["training", "business", "career_change"];
const RENEW_YEARS = Array.from({ length: 10 }, (_, i) => i + 1);

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
    kind: useId(),
    fillFirst: useId(),
    permanent: useId(),
    proType: useId(),
    cost: useId(),
    renew: useId(),
    renewYears: useId(),
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
  // One type per goal (F-GOAL-1, 10, 11): permanent is an option of a dated project.
  const [kind, setKind] = useState<Kind>(() =>
    (goal?.pro_type ?? null) !== null
      ? "professional"
      : goal?.pleasure
        ? "pleasure"
        : goal?.precaution
          ? "precaution"
          : "project",
  );
  const precaution = kind === "precaution";
  // Only a precaution goal can wait its turn, a survival kitty say (F-GOAL-1).
  const [fillFirst, setFillFirst] = useState(goal?.fill_first ?? true);
  const [isPermanent, setPermanent] = useState(goal?.permanent ?? false);
  const pleasure = kind === "pleasure";
  const professional = kind === "professional";
  const [proType, setProType] = useState<ProType>(goal?.pro_type ?? "equipment");
  const [cost, setCost] = useState(goal?.cost ? amountInputShort(goal.cost) : "");
  const [aids, setAids] = useState<Aid[]>(
    () =>
      goal?.aids.map((a) => ({
        source: a.source,
        amount: amountInputShort(a.amount),
        received: a.received,
      })) ?? [],
  );
  const [renew, setRenew] = useState((goal?.renew_years ?? null) !== null);
  const [renewYears, setRenewYears] = useState(goal?.renew_years ?? 4);
  // The emergency fund is always permanent; a pleasure goal never, and has no deadline.
  const permanent = precaution || (kind === "project" && isPermanent);
  const isPrecaution = precaution;
  const sources = SOURCES.filter((s) => s !== "cpf" || CPF_TYPES.includes(proType));
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
    mutationFn: async ({
      amount,
      fundings,
      paid,
    }: {
      amount: string;
      fundings: GoalFundingIn[];
      paid: { cost: string; aids: GoalAidIn[] } | null;
    }) => {
      const body = {
        name,
        precaution: isPrecaution,
        fill_first: !isPrecaution || fillFirst,
        permanent,
        pleasure,
        pro_type: paid ? proType : null,
        ...(paid
          ? {
              cost: paid.cost,
              aids: paid.aids,
              renew_years: proType === "equipment" && renew ? renewYears : null,
            }
          : { target: amount }),
        deadline: pleasure ? null : deadline || null,
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
    let paid: { cost: string; aids: GoalAidIn[] } | null = null;
    if (professional) {
      const total = parseEurInput(cost);
      if (total === null || Number(total) <= 0) return setError(g.targetInvalid);
      const given: GoalAidIn[] = [];
      for (const aid of aids) {
        const parsed = parseEurInput(aid.amount);
        if (parsed === null || Number(parsed) <= 0) return setError(g.targetInvalid);
        given.push({ source: aid.source, amount: parsed, received: aid.received });
      }
      paid = { cost: total, aids: given };
    }
    const amount = paid ? paid.cost : parseEurInput(target);
    if (amount === null || Number(amount) <= 0) return setError(g.targetInvalid);
    const fundings: GoalFundingIn[] = [];
    for (const [line_id, { share, opening }] of shares) {
      const parsed = opening.trim() ? parseEurInput(opening) : "0.00";
      if (parsed === null || parsed.startsWith("-")) return setError(g.targetInvalid);
      fundings.push({ line_id, share, opening: parsed });
    }
    setError(null);
    save.mutate({ amount, fundings, paid });
  };

  // In cents, so a preview never rounds a few cents to nothing.
  const cents = (text: string) => Math.round(Number(parseEurInput(text) ?? 0) * 100);
  const parsedCost = cents(cost);
  const gather = parsedCost - aids.reduce((sum, a) => sum + cents(a.amount), 0);
  const changeAid = (index: number, fields: Partial<Aid>) =>
    setAids((current) => current.map((a, i) => (i === index ? { ...a, ...fields } : a)));

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
      <fieldset className="flex flex-col gap-2 text-sm">
        <legend id={ids.kind} className="mb-1 font-medium">
          {g.typeLegend}
        </legend>
        <div role="radiogroup" aria-labelledby={ids.kind} className="grid gap-2 sm:grid-cols-2">
          {KINDS.map((k) => (
            <label
              key={k}
              className={`flex cursor-pointer flex-col gap-0.5 rounded-md border p-3 ${
                kind === k ? "border-accent bg-accent/10" : "border-border hover:border-accent"
              }`}
            >
              <span className="flex items-center gap-2 font-medium">
                <input
                  type="radio"
                  name={ids.kind}
                  value={k}
                  aria-label={g.types[k]}
                  aria-describedby={`${ids.kind}-${k}`}
                  checked={kind === k}
                  onChange={() => setKind(k)}
                />
                {k === "professional" && <Briefcase />}
                {g.types[k]}
              </span>
              <span id={`${ids.kind}-${k}`} className="text-xs text-muted">
                {g.typeHints[k]}
              </span>
            </label>
          ))}
        </div>
        <p className={hintClass}>
          {
            {
              precaution: g.isPrecautionHint,
              project: null,
              pleasure: g.isPleasureHint,
              professional: g.isProfessionalHint,
            }[kind]
          }
        </p>
      </fieldset>
      {isPrecaution && (
        <div className="ml-6 flex flex-col gap-1 text-sm">
          <label htmlFor={ids.fillFirst} className="flex items-center gap-2 font-medium">
            <input
              id={ids.fillFirst}
              type="checkbox"
              aria-describedby={`${ids.fillFirst}-hint`}
              checked={fillFirst}
              onChange={(e) => setFillFirst(e.target.checked)}
            />
            {g.fillFirst}
          </label>
          <p id={`${ids.fillFirst}-hint`} className={hintClass}>
            {fillFirst ? g.fillFirstHint : g.notFillFirstHint}
          </p>
        </div>
      )}
      {kind === "project" && (
        <div className="ml-6 flex flex-col gap-1 text-sm">
          <label htmlFor={ids.permanent} className="flex items-center gap-2 font-medium">
            <input
              id={ids.permanent}
              type="checkbox"
              checked={isPermanent}
              aria-describedby={`${ids.permanent}-hint`}
              onChange={(e) => setPermanent(e.target.checked)}
            />
            {g.isPermanent}
          </label>
          <p id={`${ids.permanent}-hint`} className={hintClass}>
            {g.isPermanentHint}
          </p>
        </div>
      )}
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
      {professional ? (
        <ProfessionalFields
          ids={ids}
          proType={proType}
          setProType={setProType}
          cost={cost}
          setCost={setCost}
          aids={aids}
          setAids={setAids}
          changeAid={changeAid}
          sources={sources}
          gather={parsedCost > 0 ? gather : null}
          renew={renew}
          setRenew={setRenew}
          renewYears={renewYears}
          setRenewYears={setRenewYears}
        />
      ) : (
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
      )}
      {isPrecaution && fillFirst && (
        <Proposal onUse={(amount) => setTarget(amountInputShort(amount))} />
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {!pleasure && (
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
        )}
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
          <Link to="/spending/fixed" className="text-accent hover:underline">
            {g.openFixed}
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

/** A professional goal's kind, cost, what others pay and renewal (F-GOAL-11). */
function ProfessionalFields({
  ids,
  proType,
  setProType,
  cost,
  setCost,
  aids,
  setAids,
  changeAid,
  sources,
  gather,
  renew,
  setRenew,
  renewYears,
  setRenewYears,
}: {
  ids: { proType: string; cost: string; renew: string; renewYears: string };
  proType: ProType;
  setProType: (value: ProType) => void;
  cost: string;
  setCost: (value: string) => void;
  aids: Aid[];
  setAids: (update: (current: Aid[]) => Aid[]) => void;
  changeAid: (index: number, fields: Partial<Aid>) => void;
  sources: AidSource[];
  gather: number | null;
  renew: boolean;
  setRenew: (value: boolean) => void;
  renewYears: number;
  setRenewYears: (value: number) => void;
}) {
  const { t } = useI18n();
  const g = t.goals;
  const notes = [...new Set(aids.map((a) => g.aidNotes[a.source]).filter(Boolean))];
  return (
    <div className="flex min-w-0 flex-col gap-3 rounded-md border border-border p-3">
      <div className="grid gap-4 sm:grid-cols-2">
        <label htmlFor={ids.proType} className={labelClass}>
          {g.proType}
          <select
            id={ids.proType}
            className={fieldClass}
            value={proType}
            onChange={(e) => setProType(e.target.value as ProType)}
          >
            {PRO_TYPES.map((type) => (
              <option key={type} value={type}>
                {g.proTypes[type]}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor={ids.cost} className={labelClass}>
          {g.cost}
          <input
            id={ids.cost}
            required
            inputMode="decimal"
            className={`${fieldClass} tabular`}
            value={cost}
            onChange={(e) => setCost(e.target.value)}
          />
        </label>
      </div>
      <fieldset className="flex min-w-0 flex-col gap-2 text-sm">
        <legend className="mb-1 font-medium">{g.aids}</legend>
        <p className="text-muted">{g.aidsHint}</p>
        {aids.map((aid, index) => {
          const n = index + 1;
          return (
            <div
              // biome-ignore lint/suspicious/noArrayIndexKey: rows have no id of their own
              key={index}
              className="flex flex-wrap items-center gap-2 rounded-md border border-border px-3 py-2"
            >
              <select
                aria-label={g.aidSourceOf(n)}
                className={`${fieldClass} w-full min-w-0 py-1 sm:w-auto`}
                value={aid.source}
                onChange={(e) => changeAid(index, { source: e.target.value as AidSource })}
              >
                {[...new Set([...sources, aid.source])].map((source) => (
                  <option key={source} value={source}>
                    {g.aidSources[source]}
                  </option>
                ))}
              </select>
              <input
                aria-label={g.aidAmountOf(n)}
                inputMode="decimal"
                required
                className={`${fieldClass} w-28 py-1 text-right tabular`}
                value={aid.amount}
                onChange={(e) => changeAid(index, { amount: e.target.value })}
              />
              <span aria-hidden="true">€</span>
              <label className="flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={aid.received}
                  onChange={(e) => changeAid(index, { received: e.target.checked })}
                />
                {g.aidReceived}
              </label>
              <Button
                variant="ghost"
                aria-label={g.removeAidOf(n)}
                onClick={() => setAids((current) => current.filter((_, i) => i !== index))}
              >
                ×
              </Button>
            </div>
          );
        })}
        <div>
          <Button
            variant="ghost"
            onClick={() =>
              setAids((current) => [
                ...current,
                { source: sources[0] ?? "employer", amount: "", received: false },
              ])
            }
          >
            {g.addAid}
          </Button>
        </div>
        {notes.map((note) => (
          <p key={note} className={hintClass}>
            {note}
          </p>
        ))}
        {aids.some((a) => a.received) && <p className={hintClass}>{g.receivedNote}</p>}
        {gather !== null && (
          <p className="font-semibold tabular">
            {gather > 0 ? g.toGather(formatEurWhole((gather / 100).toFixed(2))) : g.noTarget}
          </p>
        )}
      </fieldset>
      {proType === "equipment" && (
        <div className="flex flex-col gap-1 text-sm">
          <div className="flex flex-wrap items-center gap-2 font-medium">
            <input
              id={ids.renew}
              type="checkbox"
              aria-describedby={`${ids.renew}-hint`}
              checked={renew}
              onChange={(e) => setRenew(e.target.checked)}
            />
            <label htmlFor={ids.renew}>{g.renew}</label>
            <select
              id={ids.renewYears}
              aria-label={`${g.renew} (${g.renewYears})`}
              disabled={!renew}
              className={`${fieldClass} py-1`}
              value={renewYears}
              onChange={(e) => setRenewYears(Number(e.target.value))}
            >
              {RENEW_YEARS.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
            <span>{g.renewYears}</span>
          </div>
          <p id={`${ids.renew}-hint`} className={hintClass}>
            {g.renewHint}
          </p>
        </div>
      )}
    </div>
  );
}
