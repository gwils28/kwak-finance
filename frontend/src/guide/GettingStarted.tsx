import { useQuery } from "@tanstack/react-query";
import { Link, type LinkProps } from "@tanstack/react-router";
import { useId, useState } from "react";
import { listAccounts, listMembers, listPlans, listTransactions } from "../api/generated";
import { PLANS_KEY } from "../budget/PlanPanel";
import { Button } from "../components/ui";
import { useI18n } from "../i18n";

const HIDDEN_KEY = "kwak-getting-started-hidden";

function readHidden(): boolean {
  try {
    return localStorage.getItem(HIDDEN_KEY) === "1";
  } catch {
    return false;
  }
}

/** How many transactions match, from one row of the list. */
async function countTransactions(uncategorised: boolean): Promise<number> {
  const query = { limit: 1, ...(uncategorised ? { uncategorised: true } : {}) };
  return (await listTransactions({ query, throwOnError: true })).data.total;
}

/**
 * The overview's "Getting started" list. Each step ticks itself from the household's data;
 * the list goes away once every step is done, or when hidden (a per-browser choice).
 */
export function GettingStarted() {
  const { t } = useI18n();
  const c = t.guide.checklist;
  const titleId = useId();
  const [hidden, setHidden] = useState(readHidden);
  const accounts = useQuery({
    queryKey: ["accounts", "getting-started"],
    queryFn: async () => (await listAccounts({ throwOnError: true })).data,
    enabled: !hidden,
  });
  const transactions = useQuery({
    queryKey: ["transactions", "getting-started"],
    queryFn: async () => ({
      all: await countTransactions(false),
      uncategorised: await countTransactions(true),
    }),
    enabled: !hidden,
  });
  const plans = useQuery({
    queryKey: PLANS_KEY,
    queryFn: async () => (await listPlans({ throwOnError: true })).data,
    enabled: !hidden,
  });
  const members = useQuery({
    queryKey: ["members", "getting-started"],
    queryFn: async () => (await listMembers({ throwOnError: true })).data,
    enabled: !hidden,
  });
  if (hidden || !accounts.data || !transactions.data || !plans.data || !members.data) return null;

  const imported = transactions.data.all > 0;
  const steps: { key: keyof typeof c.steps; done: boolean; link: LinkProps }[] = [
    { key: "account", done: accounts.data.length > 0, link: { to: "/accounts" } },
    { key: "import", done: imported, link: { to: "/accounts" } },
    {
      key: "categorise",
      done: imported && transactions.data.uncategorised === 0,
      link: { to: "/transactions", search: { category: "none" } },
    },
    {
      key: "plan",
      done: plans.data.some((p) => p.targets.length > 0),
      link: { to: "/budget" },
    },
    { key: "invite", done: members.data.length > 1, link: { to: "/members" } },
  ];
  const done = steps.filter((s) => s.done).length;
  if (done === steps.length) return null;

  const hide = () => {
    try {
      localStorage.setItem(HIDDEN_KEY, "1");
    } catch {
      // Storage refused (private window): hidden until the next visit only.
    }
    setHidden(true);
  };

  return (
    <section
      aria-labelledby={titleId}
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 id={titleId} className="text-lg font-bold">
            {c.title}
          </h2>
          <p className="text-sm text-muted">{c.progress(done, steps.length)}</p>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/guide" className="text-sm text-accent hover:underline">
            {c.readGuide}
          </Link>
          <Button variant="ghost" onClick={hide}>
            {c.hide}
          </Button>
        </div>
      </div>
      <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        {steps.map((step, i) => (
          <li
            key={step.key}
            aria-label={c.steps[step.key]}
            data-done={step.done}
            className={`flex items-start gap-2 rounded-md border px-3 py-2 text-sm ${
              step.done ? "border-border text-muted" : "border-accent"
            }`}
          >
            <span
              aria-hidden="true"
              className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                step.done ? "bg-budget-under-bg text-budget-under-fg" : "border border-accent"
              }`}
            >
              {step.done ? "✓" : i + 1}
            </span>
            {step.done ? (
              <span>
                <span className="line-through">{c.steps[step.key]}</span>
                <span className="sr-only"> · {c.done}</span>
              </span>
            ) : (
              <Link {...step.link} className="font-medium hover:text-accent hover:underline">
                {c.steps[step.key]}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
