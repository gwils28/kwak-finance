import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import {
  deleteMyRetirement,
  getRetirement,
  type MyRetirementIn,
  type RetirementMemberOut,
  type RetirementOut,
  type RetirementSettingsPatch,
  setMyRetirement,
  updateRetirementSettings,
} from "../api/generated";
import { detailSentence } from "../auth/errors";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import {
  amountInputShort,
  formatEurWhole,
  parseEurInput,
  parsePercentInput,
  percentInput,
} from "../lib/money";
import { isMonth, monthLabel } from "../lib/months";

export const RETIREMENT_KEY = ["retirement"];
const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";
const labelClass = "flex flex-col gap-1 text-sm font-medium";
const hintClass = "font-normal text-muted";

type Saved = (next: RetirementOut) => void;

function useSave<T>(call: (input: T) => Promise<RetirementOut | undefined>, onSaved: Saved) {
  const { t } = useI18n();
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: call,
    onSuccess: async (next) => {
      setError(null);
      if (next) onSaved(next);
      else await queryClient.invalidateQueries({ queryKey: RETIREMENT_KEY });
    },
    onError: (failure) => setError(detailSentence(failure) ?? t.errors.generic),
  });
  return { mutation, error, setError };
}

async function unwrap<D>(request: Promise<{ data?: D; error?: unknown }>): Promise<D> {
  const { data, error } = await request;
  if (error) throw error;
  return data as D;
}

/**
 * Retirement's inputs (F-RET-1, 2): the member's own retirement, the other members' (seen,
 * not changed), and the household's settings. Saving one runs the plan again.
 */
export function RetirementForm({ onSaved }: { onSaved: () => void }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: RETIREMENT_KEY,
    queryFn: async () => (await getRetirement({ throwOnError: true })).data,
  });
  const saved: Saved = (next) => {
    queryClient.setQueryData(RETIREMENT_KEY, next);
    onSaved();
  };
  if (query.isError) return <ErrorAlert message={t.wealth.loadFailed} />;
  if (!query.data) return null;
  const me = query.data.members.find((m) => m.me);
  const others = query.data.members.filter((m) => !m.me);
  return (
    <div className="flex flex-col gap-4">
      {me && (
        <MineForm
          key={`${me.birth}-${me.retirement}-${me.pension}`}
          me={me}
          onSaved={saved}
          onRemoved={onSaved}
        />
      )}
      {others.length > 0 && <Others members={others} />}
      <SettingsForm key={JSON.stringify(query.data.settings)} data={query.data} onSaved={saved} />
    </div>
  );
}

function Section({
  id,
  title,
  intro,
  children,
}: {
  id: string;
  title: string;
  intro?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      aria-labelledby={id}
      className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4"
    >
      <div>
        <h2 id={id} className="text-lg font-bold">
          {title}
        </h2>
        {intro && <p className="max-w-3xl text-sm text-muted">{intro}</p>}
      </div>
      {children}
    </section>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: (id: string, describedBy: string | undefined) => React.ReactNode;
}) {
  const id = useId();
  return (
    <div className={labelClass}>
      <label htmlFor={id}>{label}</label>
      {children(id, hint ? `${id}-hint` : undefined)}
      {hint && (
        <p id={`${id}-hint`} className={hintClass}>
          {hint}
        </p>
      )}
    </div>
  );
}

function MineForm({
  me,
  onSaved,
  onRemoved,
}: {
  me: RetirementMemberOut;
  onSaved: Saved;
  onRemoved: () => void;
}) {
  const { t } = useI18n();
  const w = t.wealth;
  const [birth, setBirth] = useState(me.birth ?? "");
  const [retirement, setRetirement] = useState(me.retirement ?? "");
  const [earnings, setEarnings] = useState(me.earnings ? amountInputShort(me.earnings) : "");
  const [pensionMonth, setPensionMonth] = useState(
    me.pension_month && me.pension_month !== me.retirement ? me.pension_month : "",
  );
  const [pension, setPension] = useState(me.pension ? amountInputShort(me.pension) : "");
  const save = useSave((body: MyRetirementIn) => unwrap(setMyRetirement({ body })), onSaved);
  const remove = useSave(async () => {
    await unwrap(deleteMyRetirement());
    onRemoved();
    return undefined;
  }, onSaved);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!isMonth(birth) || !isMonth(retirement) || (pensionMonth && !isMonth(pensionMonth))) {
      return save.setError(w.monthInvalid);
    }
    const lost = parseEurInput(earnings.trim() === "" ? "0" : earnings);
    const paid = parseEurInput(pension.trim() === "" ? "0" : pension);
    if (lost === null || paid === null || lost.startsWith("-") || paid.startsWith("-")) {
      return save.setError(w.amountInvalid);
    }
    save.mutation.mutate({
      birth,
      retirement,
      earnings: lost,
      pension_month: pensionMonth || null,
      pension: paid,
    });
  };
  return (
    <Section id="my-retirement" title={w.myRetirement} intro={w.myRetirementIntro}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={w.birthMonth}>
            {(id) => (
              <input
                id={id}
                type="month"
                className={fieldClass}
                value={birth}
                onChange={(e) => setBirth(e.target.value)}
              />
            )}
          </Field>
          <Field label={w.retirementMonth}>
            {(id) => (
              <input
                id={id}
                type="month"
                className={fieldClass}
                value={retirement}
                onChange={(e) => setRetirement(e.target.value)}
              />
            )}
          </Field>
          <Field label={w.earnings} hint={w.earningsHint}>
            {(id, hint) => (
              <input
                id={id}
                aria-describedby={hint}
                inputMode="decimal"
                className={`${fieldClass} tabular`}
                value={earnings}
                onChange={(e) => setEarnings(e.target.value)}
              />
            )}
          </Field>
          <Field label={w.pensionMonth} hint={w.pensionMonthHint}>
            {(id, hint) => (
              <input
                id={id}
                aria-describedby={hint}
                type="month"
                className={fieldClass}
                value={pensionMonth}
                onChange={(e) => setPensionMonth(e.target.value)}
              />
            )}
          </Field>
        </div>
        <Field label={w.pension} hint={w.pensionHint}>
          {(id, hint) => (
            <input
              id={id}
              aria-describedby={hint}
              inputMode="decimal"
              className={`${fieldClass} tabular sm:w-60`}
              value={pension}
              onChange={(e) => setPension(e.target.value)}
            />
          )}
        </Field>
        <ErrorAlert message={save.error ?? remove.error} />
        <div className="flex flex-wrap gap-3">
          <Button type="submit" disabled={save.mutation.isPending}>
            {w.saveRetirement}
          </Button>
          {me.birth && (
            <Button
              variant="ghost"
              onClick={() => remove.mutation.mutate(undefined)}
              disabled={remove.mutation.isPending}
            >
              {w.removeRetirement}
            </Button>
          )}
        </div>
      </form>
    </Section>
  );
}

function Others({ members }: { members: RetirementMemberOut[] }) {
  const { t } = useI18n();
  const w = t.wealth;
  return (
    <Section id="other-retirements" title={w.otherMembers}>
      <ul className="flex flex-col gap-1 text-sm">
        {members.map((m) => (
          <li key={m.user_id}>
            {m.retirement && m.pension !== null && m.age_at_retirement !== null
              ? w.memberRetirement(
                  m.display_name,
                  monthLabel(m.retirement),
                  m.age_at_retirement,
                  formatEurWhole(m.pension),
                )
              : w.memberNotEntered(m.display_name)}
          </li>
        ))}
      </ul>
    </Section>
  );
}

function SettingsForm({ data, onSaved }: { data: RetirementOut; onSaved: Saved }) {
  const { t } = useI18n();
  const w = t.wealth;
  const s = data.settings;
  const spent = data.spending;
  const [byAmount, setByAmount] = useState(s.spending_amount !== null);
  const [share, setShare] = useState(percentInput(s.spending_share ?? s.default_spending_share));
  const [amount, setAmount] = useState(
    s.spending_amount ? amountInputShort(s.spending_amount) : "",
  );
  const [indexation, setIndexation] = useState(percentInput(s.indexation));
  const [horizon, setHorizon] = useState(String(s.horizon_age));
  const save = useSave(
    (body: RetirementSettingsPatch) => unwrap(updateRetirementSettings({ body })),
    onSaved,
  );
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const body: RetirementSettingsPatch = {};
    if (byAmount) {
      const value = parseEurInput(amount);
      if (value === null || value.startsWith("-")) return save.setError(w.amountInvalid);
      body.spending_amount = value;
    } else {
      const value = parsePercentInput(share, 0);
      if (value === null || Number(value) < 0.5 || Number(value) > 1.5) {
        return save.setError(w.shareInvalid);
      }
      body.spending_share = value;
    }
    const rate = parsePercentInput(indexation, 1);
    if (rate === null || Number(rate) < -0.02 || Number(rate) > 0.01) {
      return save.setError(w.indexationInvalid);
    }
    const age = Number(horizon);
    if (!Number.isInteger(age) || age < 85 || age > 105) return save.setError(w.horizonInvalid);
    save.mutation.mutate({ ...body, indexation: rate, horizon_age: age });
  };
  const restore = () =>
    save.mutation.mutate({
      spending_share: null,
      spending_amount: null,
      indexation: null,
      horizon_age: null,
    });
  return (
    <Section
      id="household-retirement"
      title={w.householdRetirement}
      intro={w.householdRetirementIntro}
    >
      <form onSubmit={submit} className="flex flex-col gap-4">
        <p className="text-sm">
          {w.measuredSpending(
            formatEurWhole(spent.average),
            spent.months,
            formatEurWhole(spent.debt_payments),
            formatEurWhole(spent.base),
          )}{" "}
          {w.retirementSpending(formatEurWhole(spent.retirement_spending))}
        </p>
        <fieldset className="flex flex-col gap-2 text-sm">
          <label className="flex items-center gap-2">
            <input type="radio" checked={!byAmount} onChange={() => setByAmount(false)} />
            {w.spendingShare}
          </label>
          <label className="flex items-center gap-2">
            <input type="radio" checked={byAmount} onChange={() => setByAmount(true)} />
            {w.spendingAmount}
          </label>
        </fieldset>
        <div className="grid gap-4 sm:grid-cols-3">
          {byAmount ? (
            <Field label={w.spendingAmountField}>
              {(id) => (
                <input
                  id={id}
                  inputMode="decimal"
                  className={`${fieldClass} tabular`}
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                />
              )}
            </Field>
          ) : (
            <Field label={w.spendingShareField}>
              {(id) => (
                <input
                  id={id}
                  inputMode="numeric"
                  className={`${fieldClass} tabular`}
                  value={share}
                  onChange={(e) => setShare(e.target.value)}
                />
              )}
            </Field>
          )}
          <Field label={w.indexation} hint={w.indexationHint}>
            {(id, hint) => (
              <input
                id={id}
                aria-describedby={hint}
                inputMode="decimal"
                className={`${fieldClass} tabular`}
                value={indexation}
                onChange={(e) => setIndexation(e.target.value)}
              />
            )}
          </Field>
          <Field label={w.horizonAge} hint={w.horizonHint}>
            {(id, hint) => (
              <input
                id={id}
                aria-describedby={hint}
                inputMode="numeric"
                className={`${fieldClass} tabular`}
                value={horizon}
                onChange={(e) => setHorizon(e.target.value)}
              />
            )}
          </Field>
        </div>
        <ErrorAlert message={save.error} />
        <div className="flex flex-wrap gap-3">
          <Button type="submit" disabled={save.mutation.isPending}>
            {w.saveSettings}
          </Button>
          <Button variant="ghost" onClick={restore} disabled={save.mutation.isPending}>
            {w.restoreDefaults}
          </Button>
        </div>
      </form>
    </Section>
  );
}
