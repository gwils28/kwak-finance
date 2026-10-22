import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
import { listMembers, type Scope } from "../api/generated";
import { useI18n } from "../i18n";

/** Whether the household has several members: only then is anything held jointly. */
function useSharedHousehold(): boolean {
  const { data: members } = useQuery({
    queryKey: ["members"],
    queryFn: async () => (await listMembers({ throwOnError: true })).data,
  });
  return (members?.length ?? 0) > 1;
}

/**
 * Which wealth lines and goals a view covers. "Joint" is offered once the household has
 * several members, or when it is already the scope shown.
 */
export function ScopeSelect({
  value,
  onChange,
  labelClassName,
  fieldClassName,
  label,
}: {
  label?: string;
  value: Scope;
  onChange: (scope: Scope) => void;
  labelClassName: string;
  fieldClassName: string;
}) {
  const { t } = useI18n();
  const id = useId();
  const hasJoint = useSharedHousehold();
  return (
    <label htmlFor={id} className={labelClassName}>
      {label ?? t.dashboard.scope}
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
