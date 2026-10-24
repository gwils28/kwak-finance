import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import {
  type AssumptionsOut,
  type CategoryAssumptionOut,
  type DebtOut,
  getAssumptions,
  restoreCategoryAssumption,
  setCategoryAssumption,
  setDebtTerms,
  setInflation,
} from "../api/generated";
import { detailSentence } from "../auth/errors";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import {
  amountInputShort,
  formatEur,
  formatRate,
  parseEurInput,
  parsePercentInput,
  percentInput,
} from "../lib/money";

export const ASSUMPTIONS_KEY = ["projection", "assumptions"];
const fieldClass = "w-24 rounded-md border border-border bg-surface px-2 py-1 tabular";
const cellClass = "px-2 py-2 align-top";

type Saved = (next: AssumptionsOut) => void;

/** Bounds of F-SIM-1, as shares; the API checks them again. */
const inRange = (value: string, low: number, high: number, lowIncluded = true) => {
  const n = Number(value);
  return (lowIncluded ? n >= low : n > low) && n <= high;
};

function useSave<T>(call: (input: T) => Promise<AssumptionsOut>, onSaved: Saved) {
  const { t } = useI18n();
  const [error, setError] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: call,
    onSuccess: (next) => {
      setError(null);
      onSaved(next);
    },
    onError: (failure) => setError(detailSentence(failure) ?? t.errors.generic),
  });
  return { mutation, error, setError };
}

async function unwrap<D>(request: Promise<{ data?: D; error?: unknown }>): Promise<D> {
  const { data, error } = await request;
  if (error || data === undefined) throw error;
  return data;
}

/**
 * The projection's assumptions (F-SIM-1), a household setting any member can change: the
 * inflation, each asset category's return and volatility, and each debt's repayment. Saving
 * one reloads the Dash page through `onSaved`.
 */
export function ProjectionAssumptions({ onSaved }: { onSaved: () => void }) {
  const { t } = useI18n();
  const w = t.wealth;
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ASSUMPTIONS_KEY,
    queryFn: async () => (await getAssumptions({ throwOnError: true })).data,
  });
  const saved: Saved = (next) => {
    queryClient.setQueryData(ASSUMPTIONS_KEY, next);
    onSaved();
  };
  return (
    <section
      aria-labelledby="projection-assumptions"
      className="flex flex-col gap-6 rounded-lg border border-border bg-surface p-4"
    >
      <div>
        <h2 id="projection-assumptions" className="text-lg font-bold">
          {w.assumptionsTitle}
        </h2>
        <p className="max-w-3xl text-sm text-muted">{w.assumptionsIntro}</p>
      </div>
      {query.isError && <ErrorAlert message={w.loadFailed} />}
      {query.data && (
        <>
          <InflationForm data={query.data} onSaved={saved} />
          <CategoryTable categories={query.data.categories} onSaved={saved} />
          <DebtTable debts={query.data.debts} onSaved={saved} />
        </>
      )}
    </section>
  );
}

function InflationForm({ data, onSaved }: { data: AssumptionsOut; onSaved: Saved }) {
  const { t } = useI18n();
  const w = t.wealth;
  const [value, setValue] = useState(percentInput(data.inflation));
  const { mutation, error, setError } = useSave(
    (inflation: string | null) => unwrap(setInflation({ body: { inflation } })),
    (next) => {
      setValue(percentInput(next.inflation));
      onSaved(next);
    },
  );
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const share = parsePercentInput(value);
    if (share === null) return setError(w.percentInvalid(1));
    if (!inRange(share, -0.05, 0.2)) return setError(w.inflationRange);
    mutation.mutate(share);
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm font-medium">
          {w.inflation}
          <input
            className={fieldClass}
            inputMode="decimal"
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        </label>
        <Button type="submit" disabled={mutation.isPending}>
          {w.saveAssumption}
        </Button>
        {data.inflation !== data.default_inflation && (
          <Button variant="ghost" onClick={() => mutation.mutate(null)}>
            {w.restoreDefault}
          </Button>
        )}
      </div>
      <p className="text-sm text-muted">{w.defaultValue(formatRate(data.default_inflation))}</p>
      <ErrorAlert message={error} />
    </form>
  );
}

function CategoryTable({
  categories,
  onSaved,
}: {
  categories: CategoryAssumptionOut[];
  onSaved: Saved;
}) {
  const { t } = useI18n();
  const w = t.wealth;
  return (
    <div className="overflow-x-auto">
      <table className="text-sm">
        <thead>
          <tr className="text-left text-muted">
            <th className={cellClass}>{w.colCategory}</th>
            <th className={cellClass}>{w.colReturn}</th>
            <th className={cellClass}>{w.colVolatility}</th>
            <th className={cellClass}>{w.colMedianGrowth}</th>
            <th className={cellClass}>{w.colDefault}</th>
            <th className={cellClass} />
          </tr>
        </thead>
        <tbody>
          {categories.map((c) => (
            // Keyed by its values: a save from elsewhere resets the row's fields.
            <CategoryRow key={`${c.id}-${c.ret}-${c.volatility}`} category={c} onSaved={onSaved} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CategoryRow({
  category: c,
  onSaved,
}: {
  category: CategoryAssumptionOut;
  onSaved: Saved;
}) {
  const { t } = useI18n();
  const w = t.wealth;
  const [ret, setRet] = useState(percentInput(c.ret));
  const [volatility, setVolatility] = useState(percentInput(c.volatility));
  const { mutation, error, setError } = useSave(
    (body: { ret: string; volatility: string } | null) =>
      unwrap(
        body
          ? setCategoryAssumption({ path: { category_id: c.id }, body })
          : restoreCategoryAssumption({ path: { category_id: c.id } }),
      ),
    onSaved,
  );
  const save = () => {
    const r = parsePercentInput(ret);
    const v = parsePercentInput(volatility);
    if (r === null || v === null) return setError(w.percentInvalid(1));
    if (!inRange(r, -1, 1, false)) return setError(w.returnRange);
    if (!inRange(v, 0, 2)) return setError(w.volatilityRange);
    mutation.mutate({ ret: r, volatility: v });
  };
  return (
    <>
      <tr className="border-t border-border">
        <th scope="row" className={`${cellClass} text-left font-medium`}>
          {c.name}
        </th>
        <td className={cellClass}>
          <input
            aria-label={w.returnOf(c.name)}
            className={fieldClass}
            inputMode="decimal"
            value={ret}
            onChange={(e) => setRet(e.target.value)}
          />
        </td>
        <td className={cellClass}>
          <input
            aria-label={w.volatilityOf(c.name)}
            className={fieldClass}
            inputMode="decimal"
            value={volatility}
            onChange={(e) => setVolatility(e.target.value)}
          />
        </td>
        <td className={`${cellClass} tabular`}>{formatRate(c.median_growth)}</td>
        <td className={`${cellClass} tabular text-muted`}>
          {formatRate(c.default_ret)} ± {formatRate(c.default_volatility)}
        </td>
        <td className={`${cellClass} whitespace-nowrap`}>
          <Button
            aria-label={w.saveCategoryAssumption(c.name)}
            onClick={save}
            disabled={mutation.isPending}
          >
            {w.saveAssumption}
          </Button>
          {c.own && (
            <Button
              variant="ghost"
              aria-label={w.restoreCategory(c.name)}
              onClick={() => mutation.mutate(null)}
            >
              {w.restoreDefault}
            </Button>
          )}
        </td>
      </tr>
      {error && (
        <tr>
          <td colSpan={6} className={cellClass}>
            <ErrorAlert message={error} />
          </td>
        </tr>
      )}
    </>
  );
}

function DebtTable({ debts, onSaved }: { debts: DebtOut[]; onSaved: Saved }) {
  const { t } = useI18n();
  const w = t.wealth;
  return (
    <div className="flex flex-col gap-2">
      <h3 className="font-bold">{w.debtsTitle}</h3>
      <p className="max-w-3xl text-sm text-muted">{w.debtsIntro}</p>
      {debts.length === 0 ? (
        <p className="text-sm">{w.noDebts}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="text-sm">
            <thead>
              <tr className="text-left text-muted">
                <th className={cellClass}>{w.colDebt}</th>
                <th className={cellClass}>{w.colOwed}</th>
                <th className={cellClass}>{w.colPayment}</th>
                <th className={cellClass}>{w.colRate}</th>
                <th className={cellClass}>{w.colInsurance}</th>
                <th className={cellClass} />
              </tr>
            </thead>
            <tbody>
              {debts.map((d) => (
                <DebtRow
                  key={`${d.id}-${d.payment}-${d.rate}-${d.insurance}`}
                  debt={d}
                  onSaved={onSaved}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function DebtRow({ debt: d, onSaved }: { debt: DebtOut; onSaved: Saved }) {
  const { t } = useI18n();
  const w = t.wealth;
  const [payment, setPayment] = useState(d.payment ? amountInputShort(d.payment) : "");
  const [rate, setRate] = useState(percentInput(d.rate));
  const [insurance, setInsurance] = useState(amountInputShort(d.insurance));
  const { mutation, error, setError } = useSave(
    (body: { payment: string | null; rate: string; insurance: string }) =>
      unwrap(setDebtTerms({ path: { line_id: d.id }, body })),
    onSaved,
  );
  const save = () => {
    const amount = payment.trim() === "" ? null : parseEurInput(payment);
    const cover = parseEurInput(insurance.trim() === "" ? "0" : insurance);
    const share = parsePercentInput(rate.trim() === "" ? "0" : rate, 2);
    if ((payment.trim() !== "" && amount === null) || cover === null) {
      return setError(w.amountInvalid);
    }
    if (amount?.startsWith("-") || cover.startsWith("-")) return setError(w.amountInvalid);
    if (share === null) return setError(w.percentInvalid(2));
    if (!inRange(share, 0, 1)) return setError(w.rateRange);
    mutation.mutate({ payment: amount, rate: share, insurance: cover });
  };
  return (
    <>
      <tr className="border-t border-border">
        <th scope="row" className={`${cellClass} text-left font-medium`}>
          {d.name}
        </th>
        <td className={`${cellClass} tabular`}>{d.owed ? formatEur(d.owed) : "—"}</td>
        <td className={cellClass}>
          <input
            aria-label={w.paymentOf(d.name)}
            className={fieldClass}
            inputMode="decimal"
            placeholder={w.notSet}
            value={payment}
            onChange={(e) => setPayment(e.target.value)}
          />
        </td>
        <td className={cellClass}>
          <input
            aria-label={w.rateOf(d.name)}
            className={fieldClass}
            inputMode="decimal"
            value={rate}
            onChange={(e) => setRate(e.target.value)}
          />
        </td>
        <td className={cellClass}>
          <input
            aria-label={w.insuranceOf(d.name)}
            className={fieldClass}
            inputMode="decimal"
            value={insurance}
            onChange={(e) => setInsurance(e.target.value)}
          />
        </td>
        <td className={cellClass}>
          <Button aria-label={w.saveDebt(d.name)} onClick={save} disabled={mutation.isPending}>
            {w.saveAssumption}
          </Button>
        </td>
      </tr>
      {(d.grows || error) && (
        <tr>
          <td colSpan={6} className={cellClass}>
            {d.grows && <p className="text-sm text-warning">{w.debtGrows}</p>}
            <ErrorAlert message={error} />
          </td>
        </tr>
      )}
    </>
  );
}
