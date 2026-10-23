import { activityFr } from "./activity";
import { authFr, navFr } from "./auth";
import { commonFr, errorsFr } from "./common";
import { dashboardFr } from "./dashboard";
import type { Messages } from "./en";
import { goalAnalysisFr } from "./goalAnalysis";
import { goalsFr } from "./goals";
import { guideFr } from "./guide";
import { householdFr } from "./household";
import { overviewFr } from "./overview";
import { reportsFr } from "./reports";
import { runGuideFr } from "./runGuide";
import { spendingFr } from "./spending";
import { spendingBudgetFr } from "./spendingBudget";
import { wealthFr } from "./wealth";

export const fr: Messages = {
  common: commonFr,
  errors: errorsFr,
  nav: navFr,
  auth: authFr,
  dashboard: dashboardFr,
  household: householdFr,
  spending: spendingFr,
  spendingBudget: spendingBudgetFr,
  overview: overviewFr,
  reports: reportsFr,
  activity: activityFr,
  wealth: wealthFr,
  goals: goalsFr,
  goalAnalysis: goalAnalysisFr,
  runGuide: runGuideFr,
  guide: guideFr,
};
