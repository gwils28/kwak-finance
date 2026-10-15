import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { getSettings, type SettingsOut, updateSettings } from "../api/generated";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { isMonth, monthLabel, thisMonth } from "../lib/months";

const SETTINGS_KEY = ["household", "settings"];

type Field = "analysis_start" | "wealth_start";

type Text = {
  title: string;
  help: string;
  month: string;
  current: (settings: SettingsOut) => string;
  clear: string;
  failed: string;
  loadFailed: string;
};

/** A first month set by the owner and shown to everyone; null clears it. */
function MonthSetting({ field, isOwner, text }: { field: Field; isOwner: boolean; text: Text }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const ids = { title: useId(), month: useId() };
  const [month, setMonth] = useState("");
  const settings = useQuery({
    queryKey: SETTINGS_KEY,
    queryFn: async () => (await getSettings({ throwOnError: true })).data,
  });
  const save = useMutation({
    mutationFn: async (start: string | null) => {
      const { response } = await updateSettings({ body: { [field]: start } });
      if (!response?.ok) throw new Error(text.failed);
    },
    onSuccess: async () => {
      setMonth("");
      // Every analysis may change: the overview, the reports, the suggestions, the wealth.
      await queryClient.invalidateQueries();
    },
  });
  const start = settings.data?.[field] ?? null;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (isMonth(month)) save.mutate(month);
  };

  return (
    <section aria-labelledby={ids.title} className="flex flex-col gap-3">
      <h2 id={ids.title} className="text-2xl font-black tracking-tight">
        {text.title}
      </h2>
      <p className="max-w-2xl text-sm text-muted">{text.help}</p>
      {settings.data && <p className="text-sm font-medium">{text.current(settings.data)}</p>}
      {isOwner && settings.data && (
        <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
          <label htmlFor={ids.month} className="flex flex-col gap-1 text-sm font-medium">
            {text.month}
            <input
              id={ids.month}
              type="month"
              className="rounded-md border border-border bg-surface px-3 py-2"
              value={month || start || ""}
              max={thisMonth()}
              onChange={(e) => setMonth(e.target.value)}
            />
          </label>
          <Button type="submit" disabled={save.isPending || !isMonth(month) || month === start}>
            {t.common.save}
          </Button>
          {start && (
            <Button variant="ghost" disabled={save.isPending} onClick={() => save.mutate(null)}>
              {text.clear}
            </Button>
          )}
        </form>
      )}
      <ErrorAlert message={settings.isError ? text.loadFailed : (save.error?.message ?? null)} />
    </section>
  );
}

/** The first month analyses count (F-ADM-4). */
export function AnalysisStart({ isOwner }: { isOwner: boolean }) {
  const { t } = useI18n();
  const h = t.household;
  return (
    <MonthSetting
      field="analysis_start"
      isOwner={isOwner}
      text={{
        title: h.analysisStart,
        help: h.analysisStartHelp,
        month: h.analysisStartMonth,
        current: (s) =>
          s.analysis_start ? h.startsIn(monthLabel(s.analysis_start)) : h.everyMonth,
        clear: h.countEveryMonth,
        failed: h.analysisStartFailed,
        loadFailed: h.analysisStartLoadFailed,
      }}
    />
  );
}

/** The first month the wealth page shows (F-WLT-5), apart from the analyses start. */
export function WealthStart({ isOwner }: { isOwner: boolean }) {
  const { t } = useI18n();
  const h = t.household;
  return (
    <MonthSetting
      field="wealth_start"
      isOwner={isOwner}
      text={{
        title: h.wealthStart,
        help: h.wealthStartHelp,
        month: h.wealthStartMonth,
        current: (s) =>
          s.wealth_start
            ? h.wealthStartsIn(monthLabel(s.wealth_start))
            : h.wealthFollows(s.analysis_start && monthLabel(s.analysis_start)),
        clear: h.followAnalyses,
        failed: h.wealthStartFailed,
        loadFailed: h.wealthStartLoadFailed,
      }}
    />
  );
}
