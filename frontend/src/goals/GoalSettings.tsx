import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { getSettings, type SettingsOut, updateSettings } from "../api/generated";
import { detailSentence } from "../auth/errors";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { amountInputShort, formatPercent, parseEurInput } from "../lib/money";
import { GOALS_KEY } from "./shared";

const SHARES = ["0.50", "0.60", "0.70", "0.80", "0.90", "1.00"];
const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";
const labelClass = "flex flex-col gap-1 text-sm font-medium";
export const SETTINGS_KEY = ["household", "settings"];

/** The precaution share and the monthly capacity of the effort plan (F-GOAL-6). */
export function GoalSettings({ isOwner, onDone }: { isOwner: boolean; onDone: () => void }) {
  const { t } = useI18n();
  const g = t.goals;
  const settings = useQuery({
    queryKey: SETTINGS_KEY,
    queryFn: async () => (await getSettings({ throwOnError: true })).data,
  });
  return (
    <section
      aria-labelledby="goal-settings"
      className="flex max-w-xl flex-col gap-4 rounded-lg border border-border bg-surface p-4"
    >
      <h2 id="goal-settings" className="text-lg font-bold">
        {g.settingsTitle}
      </h2>
      {!isOwner && <p className="text-sm text-muted">{g.settingsOwnerOnly}</p>}
      {settings.data && (
        <SettingsForm settings={settings.data} disabled={!isOwner} onDone={onDone} />
      )}
    </section>
  );
}

function SettingsForm({
  settings,
  disabled,
  onDone,
}: {
  settings: SettingsOut;
  disabled: boolean;
  onDone: () => void;
}) {
  const { t } = useI18n();
  const g = t.goals;
  const queryClient = useQueryClient();
  const shareId = useId();
  const amountId = useId();
  const [share, setShare] = useState(settings.precaution_share);
  const [manual, setManual] = useState(settings.goal_capacity !== null);
  const [amount, setAmount] = useState(
    settings.goal_capacity ? amountInputShort(settings.goal_capacity) : "",
  );
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: async (capacity: string | null) => {
      const { error: failure } = await updateSettings({
        body: { precaution_share: share, goal_capacity: capacity },
      });
      if (failure) throw failure;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: SETTINGS_KEY });
      await queryClient.invalidateQueries({ queryKey: GOALS_KEY });
      onDone();
    },
    onError: (failure) => setError(detailSentence(failure) ?? t.errors.generic),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!manual) return save.mutate(null);
    const capacity = parseEurInput(amount);
    if (capacity === null || capacity.startsWith("-")) return setError(g.targetInvalid);
    save.mutate(capacity);
  };
  const shares = SHARES.includes(share) ? SHARES : [...SHARES, share].sort();
  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <div className={labelClass}>
        <label htmlFor={shareId}>{g.precautionShare}</label>
        <select
          id={shareId}
          aria-describedby={`${shareId}-hint`}
          className={fieldClass}
          value={share}
          disabled={disabled}
          onChange={(e) => setShare(e.target.value)}
        >
          {shares.map((s) => (
            <option key={s} value={s}>
              {formatPercent(s)}
            </option>
          ))}
        </select>
        <p id={`${shareId}-hint`} className="font-normal text-muted">
          {g.precautionShareHint}
        </p>
      </div>
      <fieldset className="flex flex-col gap-2 text-sm" disabled={disabled}>
        <legend className="mb-1 font-medium">{g.capacity}</legend>
        <label className="flex items-center gap-2">
          <input type="radio" checked={!manual} onChange={() => setManual(false)} />
          {g.capacityAuto}
        </label>
        <label className="flex items-center gap-2">
          <input type="radio" checked={manual} onChange={() => setManual(true)} />
          {g.capacityManual}
        </label>
        {manual && (
          <label htmlFor={amountId} className={labelClass}>
            {g.capacityAmount}
            <input
              id={amountId}
              inputMode="decimal"
              className={`${fieldClass} tabular`}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </label>
        )}
      </fieldset>
      <ErrorAlert message={error} />
      <div className="flex gap-3">
        {!disabled && (
          <Button type="submit" disabled={save.isPending}>
            {g.save}
          </Button>
        )}
        <Button variant="ghost" onClick={onDone}>
          {g.cancel}
        </Button>
      </div>
    </form>
  );
}
