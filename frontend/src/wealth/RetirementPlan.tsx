/**
 * Retirement's answer (F-RET-4): the standard of living as a tile, the pensions and the
 * withdrawal against the spending, the share covered and the chance that the wealth lasts;
 * then the members' timeline, the income once retired, the fan of net worth, the inputs, and
 * folded the limits. The inputs themselves are set below it, in `RetirementForm`.
 */
import { useQuery } from "@tanstack/react-query";
import { type RetirementPlanOut, runRetirement } from "../api/generated";
import { Callout, Chip, Fold, Jump, Tile, Tiles } from "../components/analysis";
import { ErrorAlert } from "../components/ui";
import { Card, DataTable } from "../dashboard/charts";
import { useI18n } from "../i18n";
import { formatEurHundreds, formatPercent, formatRateSigned } from "../lib/money";
import { monthLabel } from "../lib/months";
import { FanChart, IncomeChart, personColour, R, Timeline } from "./retirementCharts";

export const RETIREMENT_RUN_KEY = ["retirement", "run"];

/** A chance to the whole percent, never 0 nor 100 (F-SIM-5). */
function useChance() {
  const { t } = useI18n();
  return (chance: string) => {
    const n = Number(chance);
    if (n < 0.01) return t.retirement.chanceLow;
    if (n > 0.99) return t.retirement.chanceHigh;
    return formatPercent(chance);
  };
}

/** Every twelfth row, and the last. */
function yearly<T>(rows: T[]): T[] {
  const out = rows.filter((_, k) => k % 12 === 0);
  const last = rows.at(-1);
  if (last !== undefined && out.at(-1) !== last) out.push(last);
  return out;
}

export function RetirementPlan() {
  const { t } = useI18n();
  const r = t.retirement;
  const query = useQuery({
    queryKey: RETIREMENT_RUN_KEY,
    queryFn: async () => (await runRetirement({ throwOnError: true })).data,
  });
  return (
    <div className="flex flex-col gap-4">
      <p className="max-w-3xl text-muted">{r.intro}</p>
      {query.isPending && (
        <p role="status" className="text-muted">
          {r.loading}
        </p>
      )}
      {query.isError && <ErrorAlert message={t.errors.generic} />}
      {query.data?.problem && (
        <p className="rounded-lg border border-border bg-surface p-4">
          {r.problems[query.data.problem]}
        </p>
      )}
      {query.data?.plan && <Plan plan={query.data.plan} />}
    </div>
  );
}

function Plan({ plan }: { plan: RetirementPlanOut }) {
  const { t } = useI18n();
  const r = t.retirement;
  const chance = useChance();
  const living = plan.living;
  const retired = monthLabel(plan.retired);
  const withdrawal = living.withdrawal === null ? null : Number(living.withdrawal);
  const pensions = Number(living.pensions);
  const spending = Number(living.spending);
  const total = withdrawal === null ? null : pensions + withdrawal;
  const covered = total === null || !spending ? null : total / spending;

  const sentences = [
    withdrawal === null
      ? r.livingNone(retired, formatEurHundreds(pensions), formatEurHundreds(spending))
      : r.living(
          retired,
          formatEurHundreds(pensions),
          formatEurHundreds(withdrawal),
          formatEurHundreds(total ?? 0),
          formatEurHundreds(pensions + Number(living.withdrawal_half ?? withdrawal)),
          formatEurHundreds(spending),
          formatPercent(covered ?? 0),
        ),
    ...(living.later_pension ? [r.laterPension] : []),
  ];

  const lasts = plan.lasts;
  const lasting = [
    r.lasts(chance(lasts.chance), monthLabel(plan.horizon), plan.youngest_age_at_horizon),
    lasts.ten_age === null
      ? r.never(plan.horizon_age)
      : lasts.half_age === null
        ? r.runsOutTen(lasts.ten_age, plan.horizon_age)
        : r.runsOut(lasts.ten_age, lasts.half_age),
    ...(lasts.shortfall ? [r.shortfallAfter] : []),
  ];

  return (
    <div className="flex flex-col gap-4">
      <Jump
        label={r.sections}
        links={[
          ["ret-life", r.jumpLife],
          ["ret-income", r.jumpIncome],
          ["ret-fan", r.jumpFan],
          ["ret-inputs", r.jumpInputs],
        ]}
      />
      <Tiles>
        <Tile
          label={r.tileLiving(retired)}
          value={r.perMonth(formatEurHundreds(total ?? pensions))}
          note={sentences.join(" ")}
          wide
        >
          <Split pensions={pensions} withdrawal={withdrawal ?? 0} spending={spending} />
        </Tile>
        <Tile
          label={r.tileCovered}
          value={covered === null ? "—" : formatPercent(covered)}
          chips={
            covered === null ? undefined : covered >= 1 ? (
              <Chip status="ok">{r.covered}</Chip>
            ) : (
              <Chip status="over">{r.short}</Chip>
            )
          }
        />
        <Tile label={r.tileLasts} value={chance(lasts.chance)} note={lasting.join(" ")} />
      </Tiles>
      {withdrawal !== null && withdrawal > 0 && <Callout info>{r.model}</Callout>}

      <div className="grid gap-4 lg:grid-cols-2">
        <section id="ret-life" className="scroll-mt-4 lg:col-span-2">
          <Card title={r.lifeTitle} subtitle={r.lifeLede}>
            <Timeline plan={plan} />
          </Card>
        </section>
        <section id="ret-income" className="scroll-mt-4">
          <Card title={r.incomeTitle} subtitle={r.incomeLede}>
            <IncomeChart plan={plan} />
            <DataTable
              label={r.incomeTitle}
              head={[r.colMonth, r.pensions, r.withdrawal, r.spending]}
              rows={yearly(plan.income).map((m) => [
                monthLabel(m.month),
                formatEurHundreds(m.pensions),
                formatEurHundreds(m.withdrawal),
                formatEurHundreds(m.spending),
              ])}
            />
          </Card>
        </section>
        <section id="ret-fan" className="scroll-mt-4">
          <Card title={r.fanTitle} subtitle={r.fanLede}>
            <FanChart plan={plan} />
            <DataTable
              label={r.fanTitle}
              head={[r.colMonth, r.colP10, r.colMedian, r.colP90, r.liquid]}
              rows={yearly(plan.months).map((m) => [
                monthLabel(m.month),
                formatEurHundreds(m.p10),
                formatEurHundreds(m.p50),
                formatEurHundreds(m.p90),
                formatEurHundreds(m.liquid),
              ])}
            />
          </Card>
        </section>
        <section id="ret-inputs" className="scroll-mt-4 lg:col-span-2">
          <Inputs plan={plan} />
        </section>
      </div>
      <Fold title={r.limitsTitle} hint={r.limitsHint}>
        <ul className="list-disc pl-5 text-sm text-muted">
          {r.limits.map((limit) => (
            <li key={limit}>{limit}</li>
          ))}
        </ul>
        <p className="text-xs text-muted">
          {r.engine(
            new Intl.NumberFormat().format(plan.engine.paths),
            String(plan.engine.seed),
            String(plan.engine.version),
          )}
        </p>
      </Fold>
      <p className="max-w-3xl text-sm text-muted">{r.disclaimer}</p>
    </div>
  );
}

/** The pensions and the withdrawal as one bar, a mark at the spending under it. */
function Split({
  pensions,
  withdrawal,
  spending,
}: {
  pensions: number;
  withdrawal: number;
  spending: number;
}) {
  const { t } = useI18n();
  const r = t.retirement;
  const total = pensions + withdrawal;
  if (!total) return null;
  const at = Math.min(spending / total, 1) * 100;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex h-7 overflow-hidden rounded text-xs font-medium">
        {pensions > 0 && (
          <span
            className="flex items-center overflow-hidden px-2 whitespace-nowrap text-surface"
            style={{ flex: `${pensions} 1 0`, background: R.pensions }}
          >
            {r.splitPensions(formatEurHundreds(pensions))}
          </span>
        )}
        {withdrawal > 0 && (
          <span
            className="flex items-center overflow-hidden px-2 whitespace-nowrap text-fg"
            style={{ flex: `${withdrawal} 1 0`, background: R.withdrawal }}
          >
            {r.splitWithdrawal(formatEurHundreds(withdrawal))}
          </span>
        )}
      </div>
      <div className="relative h-5 text-xs text-muted">
        <span
          className={`absolute border-l-2 border-fg pl-1 whitespace-nowrap ${at > 70 ? "-translate-x-full border-r-2 border-l-0 pr-1 pl-0" : ""}`}
          style={{ left: `${at}%` }}
        >
          {r.against(formatEurHundreds(spending))}
        </span>
      </div>
    </div>
  );
}

function Inputs({ plan }: { plan: RetirementPlanOut }) {
  const { t } = useI18n();
  const r = t.retirement;
  const s = plan.spending;
  const how =
    s.share === null
      ? r.howAmount
      : r.howShare(formatPercent(s.share), formatEurHundreds(s.base), s.months);
  return (
    <Card title={r.inputsTitle}>
      <div className="grid gap-2 sm:grid-cols-2">
        {plan.people.map((p, k) => (
          <div
            key={p.name}
            className="rounded-md border border-l-4 border-border p-2 text-sm"
            style={{ borderLeftColor: personColour(k) }}
          >
            <b>{p.name}</b>
            <p className="text-muted">
              {r.inputMember(
                p.name,
                monthLabel(p.birth),
                monthLabel(p.retirement),
                p.age_at_retirement,
                formatEurHundreds(p.earnings),
                formatEurHundreds(p.pension),
                monthLabel(p.pension_month),
                p.age_at_pension,
              )}
            </p>
          </div>
        ))}
      </div>
      <ul className="list-disc pl-5 text-sm text-muted">
        <li>{r.inputSpending(formatEurHundreds(s.retirement), how)}</li>
        <li>{r.inputIndexation(formatRateSigned(plan.indexation))}</li>
        <li>{r.inputHorizon(monthLabel(plan.horizon), plan.horizon_age)}</li>
        {plan.left_out.length > 0 && <li>{r.leftOut(plan.left_out.join(", "))}</li>}
        <li>{r.scope}</li>
      </ul>
    </Card>
  );
}
