import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { getSettings, updateSettings } from "../api/generated";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { isMonth, monthLabel, thisMonth } from "../lib/months";

const SETTINGS_KEY = ["household", "settings"];

/** The first month analyses count (F-ADM-4): set by the owner, shown to everyone. */
export function AnalysisStart({ isOwner }: { isOwner: boolean }) {
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
      const { response } = await updateSettings({ body: { analysis_start: start } });
      if (!response?.ok) throw new Error(t.household.analysisStartFailed);
    },
    onSuccess: async () => {
      setMonth("");
      // Every analysis may change: the overview, the reports, the suggestions.
      await queryClient.invalidateQueries();
    },
  });
  const start = settings.data?.analysis_start ?? null;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (isMonth(month)) save.mutate(month);
  };

  return (
    <section aria-labelledby={ids.title} className="flex flex-col gap-3">
      <h2 id={ids.title} className="text-2xl font-black tracking-tight">
        {t.household.analysisStart}
      </h2>
      <p className="max-w-2xl text-sm text-muted">{t.household.analysisStartHelp}</p>
      {settings.data && (
        <p className="text-sm font-medium">
          {start ? t.household.startsIn(monthLabel(start)) : t.household.everyMonth}
        </p>
      )}
      {isOwner && settings.data && (
        <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
          <label htmlFor={ids.month} className="flex flex-col gap-1 text-sm font-medium">
            {t.household.analysisStartMonth}
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
              {t.household.countEveryMonth}
            </Button>
          )}
        </form>
      )}
      <ErrorAlert
        message={
          settings.isError ? t.household.analysisStartLoadFailed : (save.error?.message ?? null)
        }
      />
    </section>
  );
}
