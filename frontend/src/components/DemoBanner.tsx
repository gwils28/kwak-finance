import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useId, useState } from "react";
import {
  enter as enterDemo,
  leave as leaveDemo,
  reset as resetDemo,
  type UserOut,
} from "../api/generated";
import { detailSentence } from "../auth/errors";
import { meQuery } from "../auth/session";
import { useI18n } from "../i18n";
import { Button, ErrorAlert } from "./ui";

type Switch = typeof enterDemo;

/**
 * Open, leave or reset the demo (F-ADM-5): the session then shows the other household, so every
 * page is loaded again, from the overview.
 */
export function useDemoSwitch() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: async (call: Switch) => {
      const { data, error: failure } = await call();
      if (failure !== undefined || data === undefined) throw failure;
      return data;
    },
    onSuccess: async (user: UserOut) => {
      setError(null);
      queryClient.setQueryData(meQuery.queryKey, user);
      await navigate({ to: "/" });
      await queryClient.resetQueries({ predicate: (query) => query.queryKey[0] !== "me" });
    },
    onError: (failure) => setError(detailSentence(failure) ?? t.errors.generic),
  });
  return {
    open: () => mutation.mutate(enterDemo),
    leave: () => mutation.mutate(leaveDemo),
    reset: () => mutation.mutate(resetDemo),
    pending: mutation.isPending,
    error,
  };
}

/** Under the header while the session is in the demo: what it is, the way back, the reset. */
export function DemoBanner({ demo }: { demo: ReturnType<typeof useDemoSwitch> }) {
  const { t } = useI18n();
  const d = t.demo;
  const [confirming, setConfirming] = useState(false);
  const title = useId();

  return (
    <section
      aria-labelledby={title}
      className="border-b border-secondary-300 bg-secondary-50 text-sm text-secondary-900 dark:border-secondary-800 dark:bg-secondary-900 dark:text-secondary-50"
    >
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-3">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <p className="min-w-0 flex-1 basis-80">
            <strong id={title} className="font-semibold">
              {d.banner}
            </strong>{" "}
            <span>{d.explain}</span>
          </p>
          <div className="flex flex-wrap gap-2">
            <Button onClick={demo.leave} disabled={demo.pending}>
              {d.leave}
            </Button>
            <Button variant="ghost" onClick={() => setConfirming(true)} disabled={demo.pending}>
              {d.reset}
            </Button>
          </div>
        </div>
        {confirming && (
          <div
            role="alertdialog"
            aria-label={d.reset}
            className="flex max-w-xl flex-col gap-3 rounded-lg border border-negative bg-surface p-4"
          >
            <p>{d.confirmReset}</p>
            <div className="flex gap-3">
              <Button
                onClick={() => {
                  setConfirming(false);
                  demo.reset();
                }}
              >
                {d.confirm}
              </Button>
              <Button variant="ghost" onClick={() => setConfirming(false)}>
                {d.cancel}
              </Button>
            </div>
          </div>
        )}
        {demo.error && (
          // On the banner's colour, the alert keeps its own background to stay legible.
          <div className="max-w-xl rounded-md bg-surface">
            <ErrorAlert message={demo.error} />
          </div>
        )}
      </div>
    </section>
  );
}
