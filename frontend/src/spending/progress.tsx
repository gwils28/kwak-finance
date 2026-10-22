import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { type ProgressStatus, updateSettings } from "../api/generated";
import { apiErrorMessage, detailSentence } from "../auth/errors";
import { Button } from "../components/ui";
import { useI18n } from "../i18n";
import { formatPercent } from "../lib/money";
import { SPENDING } from "./queries";

/** A month-so-far bar's colour (F-BUD-2); its status is also an icon and a word. */
export const BAR: Record<ProgressStatus, string> = {
  on_track: "bg-progress-ok",
  watch: "bg-progress-watch",
  over: "bg-progress-over",
};
export const ICON: Record<ProgressStatus, string> = { on_track: "✓", watch: "!", over: "▲" };

/** The household's warning threshold; the owner can change it. */
export function Threshold({ warnAt, isOwner }: { warnAt: string; isOwner: boolean }) {
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
      await queryClient.invalidateQueries({ queryKey: [SPENDING] });
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
