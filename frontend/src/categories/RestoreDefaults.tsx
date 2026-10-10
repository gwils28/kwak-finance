import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { previewRestore, type RestoreOut, restoreDefaults } from "../api/generated";
import { apiErrorMessage, detailSentence } from "../auth/errors";
import { Button } from "../components/ui";
import { useI18n } from "../i18n";

/** Everything a restore touches: rows, rules, plans… so every page reloads them. */
const AFFECTED = ["categories", "rules", "transactions", "toCategorise", "budget", "dashboard"];

/**
 * "Restore the default categories" (owner only): a preview of what goes, a warning, then the
 * restore itself.
 */
export function RestoreDefaults({
  onError,
  onNotice,
}: {
  onError: (message: string | null) => void;
  onNotice: (message: string) => void;
}) {
  const { t } = useI18n();
  const r = t.categories.restore;
  const titleId = useId();
  const queryClient = useQueryClient();
  const [preview, setPreview] = useState<RestoreOut | null>(null);

  const call = async (fetch: typeof previewRestore) => {
    const { data, error, response } = await fetch();
    if (!data) throw new Error(detailSentence(error) ?? apiErrorMessage(t, response));
    return data;
  };
  const load = useMutation({
    mutationFn: () => call(previewRestore),
    onSuccess: (data) => {
      onError(null);
      setPreview(data);
    },
    onError: (exc) => onError(exc.message),
  });
  const restore = useMutation({
    mutationFn: () => call(restoreDefaults),
    onSuccess: async () => {
      setPreview(null);
      onError(null);
      onNotice(r.done);
      await Promise.all(AFFECTED.map((key) => queryClient.invalidateQueries({ queryKey: [key] })));
    },
    onError: (exc) => onError(exc.message),
  });

  const changes =
    preview &&
    ([
      [r.deleted, preview.deleted],
      [r.merged, preview.merged.map((m) => `${m.from} → ${m.to}`)],
      [r.renamed, preview.renamed.map((m) => `${m.from} → ${m.to}`)],
      [r.moved, preview.moved],
      [r.created, preview.created],
    ] as const);
  const nothing = changes?.every(([, names]) => names.length === 0);

  return (
    <section
      aria-labelledby={titleId}
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
    >
      <h2 id={titleId} className="text-lg font-bold">
        {r.title}
      </h2>
      <p className="text-sm text-muted">{r.intro}</p>
      {!preview && (
        <div>
          <Button variant="ghost" disabled={load.isPending} onClick={() => load.mutate()}>
            {load.isPending ? r.loading : r.open}
          </Button>
        </div>
      )}
      {preview && nothing && <p className="text-sm">{r.nothing}</p>}
      {preview && !nothing && changes && (
        <>
          <div role="alert" className="rounded-md border border-warning px-3 py-2 text-sm">
            <p className="font-semibold">{r.warningTitle}</p>
            <ul className="mt-1 list-inside list-disc">
              {preview.transactions_to_categorise > 0 && (
                <li>{r.toCategorise(preview.transactions_to_categorise)}</li>
              )}
              {preview.rules_deleted > 0 && <li>{r.rules(preview.rules_deleted)}</li>}
              {preview.plan_targets_deleted > 0 && (
                <li>{r.targets(preview.plan_targets_deleted, preview.locked_plans_affected)}</li>
              )}
            </ul>
            <p className="mt-1">{r.backup}</p>
          </div>
          <ul className="flex flex-col gap-1 text-sm">
            {changes
              .filter(([, names]) => names.length > 0)
              .map(([label, names]) => (
                <li key={label(0, "")}>{label(names.length, names.join(", "))}</li>
              ))}
          </ul>
        </>
      )}
      {preview && (
        <div className="flex gap-2">
          {!nothing && (
            <Button disabled={restore.isPending} onClick={() => restore.mutate()}>
              {r.confirm}
            </Button>
          )}
          <Button variant="ghost" onClick={() => setPreview(null)}>
            {r.cancel}
          </Button>
        </div>
      )}
    </section>
  );
}
