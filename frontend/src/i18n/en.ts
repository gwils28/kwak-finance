import { activityEn } from "./activity";
import { authEn, navEn } from "./auth";
import { commonEn, errorsEn } from "./common";
import { dashboardEn } from "./dashboard";
import { demoEn } from "./demo";
import { forecastEn } from "./forecast";
import { goalAnalysisEn } from "./goalAnalysis";
import { goalsEn } from "./goals";
import { guideEn } from "./guide";
import { householdEn } from "./household";
import { overviewEn } from "./overview";
import { projectionEn } from "./projection";
import { reportsEn } from "./reports";
import { runGuideEn } from "./runGuide";
import { spendingEn } from "./spending";
import { spendingBudgetEn } from "./spendingBudget";
import { wealthEn } from "./wealth";

/** The reference dictionary: every other language must have exactly this shape. */
export const en = {
  common: commonEn,
  errors: errorsEn,
  nav: navEn,
  auth: authEn,
  dashboard: dashboardEn,
  household: householdEn,
  spending: spendingEn,
  spendingBudget: spendingBudgetEn,
  overview: overviewEn,
  reports: reportsEn,
  forecast: forecastEn,
  activity: activityEn,
  demo: demoEn,
  wealth: wealthEn,
  projection: projectionEn,
  goals: goalsEn,
  goalAnalysis: goalAnalysisEn,
  runGuide: runGuideEn,
  guide: guideEn,
};

export type Messages = typeof en;
