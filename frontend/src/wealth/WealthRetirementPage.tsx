import { useQueryClient } from "@tanstack/react-query";
import { useI18n } from "../i18n";
import { RetirementForm } from "./RetirementForm";
import { RETIREMENT_RUN_KEY, RetirementPlan } from "./RetirementPlan";

/** Retirement (F-RET-4): the plan's answer, then the members' retirements and the settings. */
export function WealthRetirementPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-3xl font-black tracking-tight">{t.wealth.retirementTitle}</h1>
      <RetirementPlan />
      <RetirementForm
        onSaved={() => void queryClient.invalidateQueries({ queryKey: RETIREMENT_RUN_KEY })}
      />
    </div>
  );
}
