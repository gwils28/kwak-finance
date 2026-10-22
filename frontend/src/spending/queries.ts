import { type QueryClient, queryOptions } from "@tanstack/react-query";
import {
  labelSuggestions,
  listFixed,
  listSpendingCategories,
  monthIncome,
  monthLines,
  monthOccurrences,
  monthSummary,
  type SpendingCategoryOut,
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

export const incomeQuery = (month: string) =>
  queryOptions({
    queryKey: [SPENDING, "income", month],
    queryFn: async () => (await monthIncome({ path: { month }, throwOnError: true })).data,
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

/** After any write: lines, figures, occurrences and labels all move together. */
export function refreshSpending(queryClient: QueryClient): Promise<void> {
  return queryClient.invalidateQueries({ queryKey: [SPENDING] });
}

/** Expense categories first, then savings ones, each in the household's order. */
export function byKind(categories: SpendingCategoryOut[]) {
  const sorted = [...categories].sort((a, b) => a.position - b.position);
  return {
    expense: sorted.filter((c) => c.kind === "expense"),
    savings: sorted.filter((c) => c.kind === "savings"),
  };
}
