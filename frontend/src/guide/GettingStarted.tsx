import { useQuery } from "@tanstack/react-query";
import { Link, type LinkProps } from "@tanstack/react-router";
import { useId, useState } from "react";
import { listMembers } from "../api/generated";
import { Button } from "../components/ui";
import { goalsQuery } from "../goals/GoalsPage";
import { useI18n } from "../i18n";
import { thisMonth } from "../lib/months";
import {
  fixedQuery,
  incomeQuery,
  linesQuery,
  spendingCategoriesQuery,
  targetsQuery,
} from "../spending/queries";

const HIDDEN_KEY = "kwak-getting-started-hidden";

function readHidden(): boolean {
  try {
    return localStorage.getItem(HIDDEN_KEY) === "1";
  } catch {
    return false;
  }
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
  const month = thisMonth();
  const income = useQuery({ ...incomeQuery(month), enabled: !hidden });
  // The last entry is the household's, in any month.
  const lines = useQuery({ ...linesQuery(month), enabled: !hidden });
  const fixed = useQuery({ ...fixedQuery, enabled: !hidden });
  const targets = useQuery({ ...targetsQuery, enabled: !hidden });
  const categories = useQuery({ ...spendingCategoriesQuery, enabled: !hidden });
  const members = useQuery({
    queryKey: ["members", "getting-started"],
    queryFn: async () => (await listMembers({ throwOnError: true })).data,
    enabled: !hidden,
  });
  // Optional for the list: without goals (or if they cannot load), the step stays to do.
  const goals = useQuery({ ...goalsQuery("household"), enabled: !hidden });
  if (
    hidden ||
    !income.data ||
    !lines.data ||
    !fixed.data ||
    !targets.data ||
    !categories.data ||
    !members.data
  ) {
    return null;
  }
  if (goals.isPending && goals.fetchStatus !== "idle") return null;

  const steps: { key: keyof typeof c.steps; done: boolean; link: LinkProps }[] = [
    { key: "income", done: income.data.amount !== null, link: { to: "/spending" } },
    { key: "line", done: lines.data.last_entry !== null, link: { to: "/spending" } },
    { key: "fixed", done: fixed.data.length > 0, link: { to: "/spending/fixed" } },
    {
      key: "plan",
      // Spending targets: a savings objective alone does not count.
      done: targets.data.some(
        (target) =>
          target.amount !== null &&
          categories.data.find((c) => c.id === target.category_id)?.kind === "expense",
      ),
      link: { to: "/budget" },
    },
    {
      key: "goal",
      done: [...(goals.data?.goals ?? []), ...(goals.data?.closed ?? [])].some(
        (goal) => goal.precaution,
      ),
      link: { to: "/goals" },
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
      <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
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
