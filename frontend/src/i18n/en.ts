import { accountsEn } from "./accounts";
import { authEn, navEn } from "./auth";
import { budgetEn } from "./budget";
import { categoriesEn } from "./categories";
import { commonEn, errorsEn } from "./common";
import { dashboardEn } from "./dashboard";
import { householdEn } from "./household";
import { importsEn } from "./imports";
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
  budget: budgetEn,
  review: reviewEn,
  categories: categoriesEn,
  runGuide: runGuideEn,
};

export type Messages = typeof en;
