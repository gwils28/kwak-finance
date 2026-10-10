import { accountsFr } from "./accounts";
import { authFr, navFr } from "./auth";
import { budgetFr } from "./budget";
import { categoriesFr } from "./categories";
import { commonFr, errorsFr } from "./common";
import { dashboardFr } from "./dashboard";
import type { Messages } from "./en";
import { householdFr } from "./household";
import { importsFr } from "./imports";
import { reviewFr } from "./review";
import { runGuideFr } from "./runGuide";
import { transactionsFr } from "./transactions";

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
  budget: budgetFr,
  review: reviewFr,
  categories: categoriesFr,
  runGuide: runGuideFr,
};
