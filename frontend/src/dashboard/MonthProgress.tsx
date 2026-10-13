import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type FormEvent, useId, useState } from "react";
import {
  monthSoFar,
  type ProgressLineOut,
  type ProgressStatus,
  type Scope,
  updateSettings,
} from "../api/generated";
import { apiErrorMessage, detailSentence } from "../auth/errors";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { formatEurWhole, formatPercent } from "../lib/money";
import { monthLabel } from "../lib/months";

const BAR: Record<ProgressStatus, string> = {
  on_track: "bg-progress-ok",
  watch: "bg-progress-watch",
  over: "bg-progress-over",
};
const ICON: Record<ProgressStatus, string> = { on_track: "✓", watch: "!", over: "▲" };

/** The month so far (F-BUD-2): each category with a target, highest share used first. */
export function MonthProgress({
  month,
  scope,
  isOwner,
}: {
  month: string;
  scope: Scope;
  isOwner: boolean;
}) {
  const { t } = useI18n();
  const query = useQuery({
    queryKey: ["dashboard", "progress", { month, scope }],
    queryFn: async () => (await monthSoFar({ query: { month, scope }, throwOnError: true })).data,
    placeholderData: keepPreviousData,
  });
  const data = query.data;
  const hasPace = data?.lines.some((line) => line.pace !== null);

  return (
    <section
      aria-label={t.dashboard.targets.titleOf(monthLabel(month))}
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">{t.dashboard.targets.title}</h2>
        {data && <Threshold warnAt={data.warn_at} isOwner={isOwner} />}
      </div>
      {query.isError && <ErrorAlert message={t.dashboard.loadFailed} />}
      {data && data.plan === null && (
        <p className="text-sm text-muted">
          {t.dashboard.targets.noPlan}{" "}
          <Link to="/budget" className="text-accent hover:underline">
            {t.dashboard.targets.createPlan}
          </Link>
        </p>
      )}
      {data && data.plan !== null && data.lines.length === 0 && (
        <p className="text-sm text-muted">{t.dashboard.targets.noTargets}</p>
      )}
      {data && data.lines.length > 0 && (
        <>
          <ul className="flex flex-col gap-3">
            {data.lines.map((line) => (
              <Line key={line.category_id} line={line} month={data.month} />
            ))}
          </ul>
          {hasPace && <p className="text-xs text-muted">{t.dashboard.targets.paceLegend}</p>}
        </>
      )}
    </section>
  );
}

function Line({ line, month }: { line: ProgressLineOut; month: string }) {
  const { t } = useI18n();
  const over = line.remaining.startsWith("-");
  const filled =
    line.share === null ? (over ? 1 : 0) : Math.min(Math.max(Number(line.share), 0), 1);
  return (
    <li className="flex flex-col gap-1 text-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <Link
          to="/transactions"
          search={{ category: line.category_id, month }}
          aria-label={t.dashboard.targets.openTransactions(line.name)}
          className="font-medium hover:text-accent hover:underline"
        >
          {line.name}
        </Link>
        <span className="tabular text-muted">
          {t.dashboard.targets.spentOf(formatEurWhole(line.spent), formatEurWhole(line.target))}
          {" · "}
          {over
            ? t.dashboard.targets.overBy(formatEurWhole(line.remaining.slice(1)))
            : t.dashboard.targets.left(formatEurWhole(line.remaining))}
        </span>
      </div>
      <div className="relative h-2 rounded-full bg-border">
        <div
          className={`h-2 rounded-full ${BAR[line.status]}`}
          style={{ width: `${filled * 100}%` }}
        />
        {line.pace !== null && (
          <div
            aria-hidden="true"
            className="absolute -top-1 h-4 w-0.5 rounded bg-fg"
            style={{ left: `calc(${Number(line.pace) * 100}% - 1px)` }}
          />
        )}
      </div>
      <div className="flex flex-wrap justify-between gap-x-3 text-xs">
        <span className={line.status === "on_track" ? "text-muted" : "font-semibold"}>
          <span aria-hidden="true">{ICON[line.status]} </span>
          {t.dashboard.targets.status[line.status]}
          {line.share !== null && ` · ${t.dashboard.targets.used(formatPercent(line.share))}`}
        </span>
        <span className="text-muted">
          {line.pace === null
            ? t.dashboard.targets.oneOff
            : t.dashboard.targets.pace(formatPercent(line.pace))}
        </span>
      </div>
    </li>
  );
}

/** The household's warning threshold; the owner can change it. */
function Threshold({ warnAt, isOwner }: { warnAt: string; isOwner: boolean }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const id = useId();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(String(Math.round(Number(warnAt) * 100)));
  const [invalid, setInvalid] = useState(false);
  const save = useMutation({
    mutationFn: async (percent: number) => {
      const result = await updateSettings({ body: { warn_at: (percent / 100).toFixed(2) } });
      if (!result.data) {
        throw new Error(detailSentence(result.error) ?? apiErrorMessage(t, result.response));
      }
      return result.data;
    },
    onSuccess: async () => {
      setEditing(false);
      await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  if (!editing) {
    return (
      <span className="flex items-baseline gap-2 text-xs text-muted">
        {t.dashboard.targets.warnAt(formatPercent(warnAt))}
        {isOwner && (
          <button
            type="button"
            className="text-accent hover:underline"
            onClick={() => {
              setValue(String(Math.round(Number(warnAt) * 100)));
              setEditing(true);
            }}
          >
            {t.dashboard.targets.change}
          </button>
        )}
      </span>
    );
  }
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const n = Number(value);
    const ok = Number.isInteger(n) && n >= 50 && n <= 100;
    setInvalid(!ok);
    if (ok) save.mutate(n);
  };
  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2 text-sm">
      <label htmlFor={id} className="flex flex-col gap-1 text-xs font-medium">
        {t.dashboard.targets.threshold}
        <input
          id={id}
          inputMode="numeric"
          className="w-20 rounded-md border border-border bg-surface px-2 py-1"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
      </label>
      <Button type="submit" className="px-2 py-1 text-xs" disabled={save.isPending}>
        {t.dashboard.targets.save}
      </Button>
      <Button variant="ghost" className="px-2 py-1 text-xs" onClick={() => setEditing(false)}>
        {t.common.cancel}
      </Button>
      {invalid && (
        <p className="w-full text-xs text-negative">{t.dashboard.targets.invalidThreshold}</p>
      )}
      {save.isError && <p className="w-full text-xs text-negative">{save.error.message}</p>}
    </form>
  );
}
