import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
import { listAccounts, type Scope } from "../api/generated";
import { useI18n } from "../i18n";

/**
 * Which accounts an aggregated view covers. "Joint accounts" is offered once the household
 * has one, closed ones included since they still hold history.
 */
export function ScopeSelect({
  value,
  onChange,
  labelClassName,
  fieldClassName,
}: {
  value: Scope;
  onChange: (scope: Scope) => void;
  labelClassName: string;
  fieldClassName: string;
}) {
  const { t } = useI18n();
  const id = useId();
  const { data: accounts } = useQuery({
    queryKey: ["accounts", { includeClosed: true }],
    queryFn: async () =>
      (await listAccounts({ query: { include_closed: true }, throwOnError: true })).data,
  });
  const hasJoint = accounts?.some((a) => a.visibility === "joint") ?? false;
  return (
    <label htmlFor={id} className={labelClassName}>
      {t.dashboard.scope}
      <select
        id={id}
        className={fieldClassName}
        value={value}
        onChange={(e) => onChange(e.target.value as Scope)}
      >
        <option value="household">{t.dashboard.household}</option>
        {(hasJoint || value === "joint") && <option value="joint">{t.dashboard.joint}</option>}
        <option value="mine">{t.dashboard.mine}</option>
      </select>
    </label>
  );
}
