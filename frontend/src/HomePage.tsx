import { useSuspenseQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import type { Scope } from "./api/generated";
import { meQuery } from "./auth/session";
import { ScopeSelect } from "./components/ScopeSelect";
import { GoalsTile } from "./dashboard/GoalsTile";
import { NetWorth } from "./dashboard/NetWorth";
import { GettingStarted } from "./guide/GettingStarted";
import { useI18n } from "./i18n";
import { thisMonth } from "./lib/months";
import { MonthOverview } from "./spending/MonthOverview";

const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";

/**
 * The overview (F-DSH-1): net worth and goals in the scope chosen, then the household's
 * spending for the month.
 */
export function HomePage() {
  const { t } = useI18n();
  const ids = { month: useId(), scope: useId() };
  const [month, setMonth] = useState(thisMonth());
  const [scope, setScope] = useState<Scope>("household");
  const { data: user } = useSuspenseQuery(meQuery);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-3xl font-black tracking-tight">{t.dashboard.title}</h1>
        <div className="flex flex-wrap items-end gap-3">
          <label htmlFor={ids.month} className="flex flex-col gap-1 text-sm font-medium">
            {t.dashboard.month}
            <input
              id={ids.month}
              type="month"
              className={fieldClass}
              value={month}
              max={thisMonth()}
              onChange={(e) => e.target.value && setMonth(e.target.value)}
            />
          </label>
          <div className="flex flex-col gap-1">
            <ScopeSelect
              label={t.overview.scope}
              value={scope}
              onChange={setScope}
              labelClassName="flex flex-col gap-1 text-sm font-medium"
              fieldClassName={fieldClass}
            />
          </div>
        </div>
      </div>
      <p className="-mt-3 text-xs text-muted">{t.overview.scopeHint}</p>
      <GettingStarted />
      <NetWorth month={month} scope={scope} />
      <GoalsTile scope={scope} />
      <MonthOverview month={month} isOwner={user.role === "owner"} />
    </div>
  );
}
