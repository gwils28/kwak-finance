import { accountsFr } from "./accounts";
import { activityFr } from "./activity";
import { authFr, navFr } from "./auth";
import { budgetFr } from "./budget";
import { categoriesFr } from "./categories";
import { commonFr, errorsFr } from "./common";
import { dashboardFr } from "./dashboard";
import type { Messages } from "./en";
import { goalsFr } from "./goals";
import { guideFr } from "./guide";
import { householdFr } from "./household";
import { importsFr } from "./imports";
import { recurringFr } from "./recurring";
import { reportsFr } from "./reports";
import { reviewFr } from "./review";
import { runGuideFr } from "./runGuide";
import { transactionsFr } from "./transactions";
import { wealthFr } from "./wealth";

export const fr: Messages = {
  common: commonFr,
  errors: errorsFr,
  nav: navFr,
  auth: authFr,
  accounts: accountsFr,
  imports: importsFr,
  dashboard: dashboardFr,
  household: householdFr,
  transactions: transactionsFr,
  recurring: recurringFr,
  budget: budgetFr,
  review: reviewFr,
  reports: reportsFr,
  activity: activityFr,
  wealth: wealthFr,
  goals: goalsFr,
  categories: categoriesFr,
  runGuide: runGuideFr,
  guide: guideFr,
};
