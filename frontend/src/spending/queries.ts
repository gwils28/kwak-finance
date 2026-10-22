import { type QueryClient, queryOptions } from "@tanstack/react-query";
import {
  labelSuggestions,
  listFixed,
  listSpendingCategories,
  listTargets,
  monthLines,
  monthOccurrences,
  monthSummary,
  type SpendingCategoryOut,
  spendingMatrix,
  spendingYear,
} from "../api/generated";

/** Every query below starts with this key: a write refreshes them all. */
export const SPENDING = "spending";

export const spendingCategoriesQuery = queryOptions({
  queryKey: [SPENDING, "categories"],
  queryFn: async () => (await listSpendingCategories({ throwOnError: true })).data,
});

export const linesQuery = (month: string) =>
  queryOptions({
    queryKey: [SPENDING, "lines", month],
    queryFn: async () => (await monthLines({ query: { month }, throwOnError: true })).data,
  });

export const summaryQuery = (month: string) =>
  queryOptions({
    queryKey: [SPENDING, "summary", month],
    queryFn: async () => (await monthSummary({ query: { month }, throwOnError: true })).data,
  });

export const occurrencesQuery = (month: string) =>
  queryOptions({
    queryKey: [SPENDING, "occurrences", month],
    queryFn: async () => (await monthOccurrences({ query: { month }, throwOnError: true })).data,
  });

export const fixedQuery = queryOptions({
  queryKey: [SPENDING, "fixed"],
  queryFn: async () => (await listFixed({ throwOnError: true })).data,
});

export const labelsQuery = (q: string) =>
  queryOptions({
    queryKey: [SPENDING, "labels", q],
    queryFn: async () => (await labelSuggestions({ query: { q }, throwOnError: true })).data,
    enabled: q.trim() !== "",
    staleTime: 60_000,
  });

export const matrixQuery = (first: string, last: string) =>
  queryOptions({
    queryKey: [SPENDING, "matrix", first, last],
    queryFn: async () =>
      (await spendingMatrix({ query: { first, last }, throwOnError: true })).data,
  });

export const yearQuery = (year: number) =>
  queryOptions({
    queryKey: [SPENDING, "year", year],
    queryFn: async () => (await spendingYear({ query: { year }, throwOnError: true })).data,
  });

export const targetsQuery = queryOptions({
  queryKey: [SPENDING, "targets"],
  queryFn: async () => (await listTargets({ throwOnError: true })).data,
});

/** After any write: lines, figures, occurrences and labels all move together. */
export function refreshSpending(queryClient: QueryClient): Promise<void> {
  return queryClient.invalidateQueries({ queryKey: [SPENDING] });
}

/** Expense categories first, then savings and income ones, each in the household's order. */
export function byKind(categories: SpendingCategoryOut[]) {
  const sorted = [...categories].sort((a, b) => a.position - b.position);
  return {
    expense: sorted.filter((c) => c.kind === "expense"),
    savings: sorted.filter((c) => c.kind === "savings"),
    income: sorted.filter((c) => c.kind === "income"),
  };
}
