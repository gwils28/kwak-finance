import { keepPreviousData, useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { type AuditEntryOut, type AuditKind, activityLog, listMembers } from "../api/generated";
import { meQuery } from "../auth/session";
import { usePeriodLabel } from "../budget/PlanPanel";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { formatDate, formatDateTime } from "../lib/dates";
import { formatEur, formatPercent } from "../lib/money";
import { monthLabel } from "../lib/months";

const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";
const labelClass = "flex flex-col gap-1 text-sm font-medium";
const PAGE = 50;
const KINDS: AuditKind[] = ["sign_in", "household", "import", "deletion", "rules"];

/** The details as the sentences expect them: amounts, dates and percentages formatted. */
function formatted(
  details: AuditEntryOut["details"],
  period: (text: string) => string,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(details)) {
    const text = String(value);
    if (key === "amount" || key === "min" || key === "max") out[key] = formatEur(text);
    else if (key === "date") out[key] = formatDate(text);
    else if (key === "warn_at") out[key] = formatPercent(text);
    else if (key === "period") out[key] = period(text);
    else if (key === "analysis_start" || key === "wealth_start")
      out[key] = text && monthLabel(text);
    else out[key] = text;
  }
  return out;
}

/** The activity log (F-ADM-3): the owner sees the household's, a member their own. */
export function ActivityPage() {
  const { data: user } = useSuspenseQuery(meQuery);
  const { t } = useI18n();
  const period = usePeriodLabel();
  const ids = { kind: useId(), member: useId() };
  const isOwner = user.role === "owner";
  const [kind, setKind] = useState<AuditKind | "">("");
  const [member, setMember] = useState("");
  const [offset, setOffset] = useState(0);

  const members = useQuery({
    queryKey: ["members"],
    queryFn: async () => (await listMembers({ throwOnError: true })).data,
    enabled: isOwner,
  });
  const log = useQuery({
    queryKey: ["audit", { kind, member, offset }],
    queryFn: async () =>
      (
        await activityLog({
          query: {
            ...(kind ? { kind } : {}),
            ...(member ? { user_id: member } : {}),
            limit: PAGE,
            offset,
          },
          throwOnError: true,
        })
      ).data,
    placeholderData: keepPreviousData,
  });
  const filter = (apply: () => void) => {
    apply();
    setOffset(0);
  };
  const total = log.data?.total ?? 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight">{t.activity.title}</h1>
          <p className="max-w-2xl text-sm text-muted">
            {isOwner ? t.activity.introOwner : t.activity.introMember}
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <label htmlFor={ids.kind} className={labelClass}>
            {t.activity.kind}
            <select
              id={ids.kind}
              className={fieldClass}
              value={kind}
              onChange={(e) => filter(() => setKind(e.target.value as AuditKind | ""))}
            >
              <option value="">{t.activity.allKinds}</option>
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {t.activity.kinds[k]}
                </option>
              ))}
            </select>
          </label>
          {isOwner && members.data && (
            <label htmlFor={ids.member} className={labelClass}>
              {t.activity.member}
              <select
                id={ids.member}
                className={fieldClass}
                value={member}
                onChange={(e) => filter(() => setMember(e.target.value))}
              >
                <option value="">{t.activity.allMembers}</option>
                {members.data.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.display_name}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
      </div>
      {log.isError && <ErrorAlert message={t.activity.loadFailed} />}
      {log.isPending && <p className="text-sm text-muted">{t.common.loading}</p>}
      {log.data && log.data.items.length === 0 && <p className="text-sm">{t.activity.empty}</p>}
      {log.data && log.data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-lg border border-border bg-surface">
            <table aria-label={t.activity.title} className="w-full text-sm">
              <thead className="text-left text-muted">
                <tr>
                  {[t.activity.when, t.activity.who, t.activity.what, t.activity.address].map(
                    (h) => (
                      <th key={h} scope="col" className="whitespace-nowrap px-3 py-2 font-medium">
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {log.data.items.map((e) => (
                  <tr key={e.id}>
                    <td className="tabular whitespace-nowrap px-3 py-2 text-muted">
                      {formatDateTime(e.at)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2">
                      {e.user_name ?? t.activity.removedMember}
                    </td>
                    <td className="px-3 py-2">
                      {t.activity.actions[e.action](formatted(e.details, period))}
                    </td>
                    <td className="tabular whitespace-nowrap px-3 py-2 text-muted">{e.ip ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <Button
              variant="ghost"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE))}
            >
              {t.activity.previous}
            </Button>
            <span className="tabular text-muted">
              {t.activity.page(offset + 1, Math.min(offset + PAGE, total), total)}
            </span>
            <Button
              variant="ghost"
              disabled={offset + PAGE >= total}
              onClick={() => setOffset(offset + PAGE)}
            >
              {t.activity.next}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
