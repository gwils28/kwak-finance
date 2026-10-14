import { accountsEn } from "./accounts";
import { activityEn } from "./activity";
import { authEn, navEn } from "./auth";
import { budgetEn } from "./budget";
import { categoriesEn } from "./categories";
import { commonEn, errorsEn } from "./common";
import { dashboardEn } from "./dashboard";
import { guideEn } from "./guide";
import { householdEn } from "./household";
import { importsEn } from "./imports";
import { recurringEn } from "./recurring";
import { reportsEn } from "./reports";
import { reviewEn } from "./review";
import { runGuideEn } from "./runGuide";
import { transactionsEn } from "./transactions";

/** The reference dictionary: every other language must have exactly this shape. */
export const en = {
  common: commonEn,
  errors: errorsEn,
  nav: navEn,
  auth: authEn,
  accounts: accountsEn,
  imports: importsEn,
  dashboard: dashboardEn,
  household: householdEn,
  transactions: transactionsEn,
  recurring: recurringEn,
  budget: budgetEn,
  review: reviewEn,
  reports: reportsEn,
  activity: activityEn,
  categories: categoriesEn,
  runGuide: runGuideEn,
  guide: guideEn,
};

export type Messages = typeof en;
