import { keepPreviousData, useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { useEffect, useId, useMemo, useState } from "react";
import {
  type Audience,
  type AuditIn,
  type AuditOut,
  type AuditPrivacyIn,
  auditDocument,
  auditDocumentIssued,
  type Language,
  listSpendingCategories,
  type PropertyAge,
  type Scope,
} from "../api/generated";
import { meQuery } from "../auth/session";
import { Button, ErrorAlert } from "../components/ui";
import { LANGUAGE_NAMES, MESSAGES, useI18n } from "../i18n";
import { parseEurInput, parsePercentInput } from "../lib/money";
import { isMonth } from "../lib/months";
import { AuditDocumentView } from "./AuditDocumentView";
import { buildDocument, toMarkdown } from "./document";

const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";
const labelClass = "flex flex-col gap-1 text-sm font-medium";
const AUDIENCES: Audience[] = ["banker", "advisor", "notary", "ai"];
const SCOPES: Scope[] = ["household", "mine", "joint"];

/** F-AUD-4: names and exact amounts for people, anonymised for an AI chat. */
function privacyFor(audience: Audience): AuditPrivacyIn {
  const named = audience !== "ai";
  return { named_members: named, named_lines: named, exact_amounts: true };
}

type ProjectForm = {
  price: string;
  notary: string;
  age: PropertyAge;
  agency: string;
  guarantee: string;
  down: string;
  loan: string;
  years: string;
  rate: string;
  insurance: string;
  rent: string;
  rentStops: boolean;
};

const EMPTY_PROJECT: ProjectForm = {
  price: "",
  notary: "",
  age: "old",
  agency: "",
  guarantee: "",
  down: "",
  loan: "",
  years: "25",
  rate: "",
  insurance: "",
  rent: "",
  rentStops: true,
};

/** The project as the API takes it, or null while a required field is missing or wrong. */
function projectBody(p: ProjectForm): AuditIn["project"] | null {
  const amount = (text: string) => (text.trim() ? parseEurInput(text) : "0.00");
  const optional = (text: string) => (text.trim() ? parseEurInput(text) : undefined);
  const price = parseEurInput(p.price);
  const rate = parsePercentInput(p.rate, 2);
  const years = Number(p.years);
  const fields = [amount(p.agency), amount(p.guarantee), amount(p.down), amount(p.insurance)];
  if (!price || !rate || !Number.isInteger(years) || fields.includes(null)) return null;
  if (optional(p.notary) === null || optional(p.loan) === null || amount(p.rent) === null) {
    return null;
  }
  return {
    price,
    notary_fees: optional(p.notary) ?? null,
    property_age: p.age,
    agency_fees: amount(p.agency) ?? "0.00",
    guarantee_fees: amount(p.guarantee) ?? "0.00",
    down_payment: amount(p.down) ?? "0.00",
    loan: optional(p.loan) ?? null,
    years,
    rate,
    insurance: amount(p.insurance) ?? "0.00",
    rent: amount(p.rent) ?? "0.00",
    rent_stops: p.rentStops,
  };
}

/** The audit document for a chosen reader (§4.15): the form, then the document as printed. */
export function AuditPage() {
  const { data: user } = useSuspenseQuery(meQuery);
  const { t, language: uiLanguage } = useI18n();
  const a = t.audit;
  const ids = {
    start: useId(),
    end: useId(),
    language: useId(),
    scope: useId(),
    withholding: useId(),
  };
  const [audience, setAudience] = useState<Audience>("banker");
  const [scope, setScope] = useState<Scope>("household");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [language, setLanguage] = useState<Language>(user.language ?? uiLanguage);
  const [privacy, setPrivacy] = useState<AuditPrivacyIn>(privacyFor("banker"));
  const [counted, setCounted] = useState<string[] | null>(null);
  const [withholding, setWithholding] = useState("");
  const [project, setProject] = useState<ProjectForm | null>(null);
  const [copied, setCopied] = useState(false);

  const chooseAudience = (next: Audience) => {
    setAudience(next);
    setPrivacy(privacyFor(next));
  };

  const withholdingRate = withholding.trim() ? parsePercentInput(withholding, 1) : null;
  const withholdingWrong =
    withholding.trim() !== "" &&
    (withholdingRate === null || Number(withholdingRate) < 0 || Number(withholdingRate) > 0.45);
  const projectIn = project ? projectBody(project) : null;
  const period = isMonth(start) && isMonth(end) ? { start, end } : {};

  const body: AuditIn = {
    audience,
    scope,
    language,
    privacy,
    ...period,
    ...(counted ? { counted } : {}),
    ...(audience === "banker" && withholdingRate && !withholdingWrong
      ? { withholding: withholdingRate }
      : {}),
    ...(audience === "banker" && projectIn ? { project: projectIn } : {}),
  };

  const doc = useQuery({
    queryKey: ["audit-document", body],
    queryFn: async () => (await auditDocument({ body, throwOnError: true })).data,
    placeholderData: keepPreviousData,
  });
  const categories = useQuery({
    queryKey: ["spending-categories"],
    queryFn: async () => (await listSpendingCategories({ throwOnError: true })).data,
  });
  const incomeCategories = (categories.data ?? []).filter((c) => c.kind === "income");

  // The period shown starts as the API's default, then the form holds it.
  useEffect(() => {
    if (doc.data && !start && !end) {
      setStart(doc.data.period.start);
      setEnd(doc.data.period.end);
    }
  }, [doc.data, start, end]);

  const built = useMemo(() => (doc.data ? buildDocument(doc.data) : null), [doc.data]);

  const log = (how: "print" | "copy" | "download", d: AuditOut) =>
    auditDocumentIssued({
      body: { audience: d.audience, scope: d.scope, start: d.period.start, end: d.period.end, how },
    });

  const markdown = () => {
    if (!built || !doc.data) return "";
    const dm = MESSAGES[doc.data.language].audit.doc;
    return toMarkdown(built, dm.promptTitle, dm.contents);
  };

  const print = () => {
    if (!doc.data) return;
    void log("print", doc.data);
    window.print();
  };
  const copy = async () => {
    if (!doc.data) return;
    await navigator.clipboard.writeText(markdown());
    setCopied(true);
    void log("copy", doc.data);
  };
  const download = () => {
    if (!doc.data) return;
    const url = URL.createObjectURL(new Blob([markdown()], { type: "text/markdown" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `kwak-audit-${doc.data.period.end}.md`;
    link.click();
    URL.revokeObjectURL(url);
    void log("download", doc.data);
  };

  const isCounted = (id: string, name: string) =>
    counted ? counted.includes(id) : (doc.data?.ratio.counted ?? []).includes(name);
  const toggleCounted = (id: string, on: boolean) => {
    const current = incomeCategories.filter((c) => isCounted(c.id, c.name)).map((c) => c.id);
    setCounted(on ? [...current, id] : current.filter((c) => c !== id));
  };

  const setP = (field: keyof ProjectForm) => (e: { target: { value: string } }) =>
    setProject((p) => (p ? { ...p, [field]: e.target.value } : p));

  return (
    <div className="flex flex-col gap-6">
      <div className="print:hidden">
        <h1 className="text-3xl font-black tracking-tight">{t.nav.audit}</h1>
        <p className="mt-2 max-w-3xl text-muted">{a.intro}</p>
      </div>

      <section
        aria-label={a.settings}
        className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4 print:hidden"
      >
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium">{a.audience}</legend>
          <div className="flex flex-wrap gap-2">
            {AUDIENCES.map((x) => (
              <label
                key={x}
                className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm ${
                  audience === x ? "border-accent" : "border-border"
                }`}
              >
                <input
                  type="radio"
                  name="audience"
                  checked={audience === x}
                  onChange={() => chooseAudience(x)}
                />
                {a.audiences[x]}
              </label>
            ))}
          </div>
        </fieldset>

        <div className="flex flex-wrap items-end gap-3">
          <label htmlFor={ids.scope} className={labelClass}>
            {a.scope}
            <select
              id={ids.scope}
              className={fieldClass}
              value={scope}
              onChange={(e) => setScope(e.target.value as Scope)}
            >
              {SCOPES.map((s) => (
                <option key={s} value={s}>
                  {a.scopes[s]}
                </option>
              ))}
            </select>
          </label>
          <label htmlFor={ids.start} className={labelClass}>
            {a.start}
            <input
              id={ids.start}
              type="month"
              className={fieldClass}
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </label>
          <label htmlFor={ids.end} className={labelClass}>
            {a.end}
            <input
              id={ids.end}
              type="month"
              className={fieldClass}
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
          </label>
          <label htmlFor={ids.language} className={labelClass}>
            {a.language}
            <select
              id={ids.language}
              className={fieldClass}
              value={language}
              onChange={(e) => setLanguage(e.target.value as Language)}
            >
              {(Object.keys(LANGUAGE_NAMES) as Language[]).map((code) => (
                <option key={code} value={code} lang={code}>
                  {LANGUAGE_NAMES[code]}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="text-xs text-muted">{a.periodHelp}</p>

        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium">{a.privacy}</legend>
          <div className="flex flex-wrap gap-4 text-sm">
            {(
              [
                ["named_members", a.namedMembers],
                ["named_lines", a.namedLines],
                ["exact_amounts", a.exactAmounts],
              ] as const
            ).map(([key, text]) => (
              <label key={key} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={privacy[key]}
                  onChange={(e) => setPrivacy({ ...privacy, [key]: e.target.checked })}
                />
                {text}
              </label>
            ))}
          </div>
          <p className="text-xs text-muted">{a.privacyHelp}</p>
        </fieldset>

        {(audience === "banker" || audience === "ai") && incomeCategories.length > 0 && (
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-sm font-medium">{a.counted}</legend>
            <div className="flex flex-wrap gap-4 text-sm">
              {incomeCategories.map((c) => (
                <label key={c.id} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={isCounted(c.id, c.name)}
                    onChange={(e) => toggleCounted(c.id, e.target.checked)}
                  />
                  {c.name}
                </label>
              ))}
            </div>
            <p className="text-xs text-muted">{a.countedHelp}</p>
          </fieldset>
        )}

        {audience === "banker" && (
          <>
            <label htmlFor={ids.withholding} className={`${labelClass} max-w-xs`}>
              {a.withholding}
              <input
                id={ids.withholding}
                inputMode="decimal"
                className={fieldClass}
                value={withholding}
                aria-invalid={withholdingWrong}
                onChange={(e) => setWithholding(e.target.value)}
              />
            </label>
            <p className="text-xs text-muted">
              {withholdingWrong ? a.withholdingInvalid : a.withholdingHelp}
            </p>
            {project ? (
              <fieldset className="flex flex-col gap-3 rounded-md border border-border p-3">
                <legend className="px-1 text-sm font-medium">{a.project}</legend>
                <p className="text-xs text-muted">{a.projectHelp}</p>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  <ProjectField label={a.price} value={project.price} onChange={setP("price")} />
                  <label className={labelClass}>
                    {a.propertyAge}
                    <select
                      className={fieldClass}
                      value={project.age}
                      onChange={(e) =>
                        setProject({ ...project, age: e.target.value as PropertyAge })
                      }
                    >
                      {(["old", "new"] as const).map((x) => (
                        <option key={x} value={x}>
                          {a.propertyAges[x]}
                        </option>
                      ))}
                    </select>
                  </label>
                  <ProjectField
                    label={a.notaryFees}
                    placeholder={a.notaryEstimated}
                    value={project.notary}
                    onChange={setP("notary")}
                  />
                  <ProjectField
                    label={a.agencyFees}
                    value={project.agency}
                    onChange={setP("agency")}
                  />
                  <ProjectField
                    label={a.guaranteeFees}
                    value={project.guarantee}
                    onChange={setP("guarantee")}
                  />
                  <ProjectField
                    label={a.downPayment}
                    value={project.down}
                    onChange={setP("down")}
                  />
                  <ProjectField
                    label={a.loan}
                    placeholder={a.loanAuto}
                    value={project.loan}
                    onChange={setP("loan")}
                  />
                  <ProjectField label={a.years} value={project.years} onChange={setP("years")} />
                  <ProjectField label={a.rate} value={project.rate} onChange={setP("rate")} />
                  <ProjectField
                    label={a.insurance}
                    value={project.insurance}
                    onChange={setP("insurance")}
                  />
                  <ProjectField label={a.rent} value={project.rent} onChange={setP("rent")} />
                  <label className="flex items-center gap-2 self-end text-sm">
                    <input
                      type="checkbox"
                      checked={project.rentStops}
                      onChange={(e) => setProject({ ...project, rentStops: e.target.checked })}
                    />
                    {a.rentStops}
                  </label>
                </div>
                <div>
                  <Button variant="ghost" onClick={() => setProject(null)}>
                    {a.projectRemove}
                  </Button>
                </div>
              </fieldset>
            ) : (
              <div>
                <Button variant="ghost" onClick={() => setProject(EMPTY_PROJECT)}>
                  {a.projectAdd}
                </Button>
              </div>
            )}
          </>
        )}

        <div className="flex flex-wrap gap-2 border-t border-border pt-4">
          {audience === "ai" ? (
            <>
              <Button onClick={() => void copy()} disabled={!built}>
                {copied ? a.copied : a.copy}
              </Button>
              <Button variant="ghost" onClick={download} disabled={!built}>
                {a.download}
              </Button>
            </>
          ) : (
            <Button onClick={print} disabled={!built}>
              {a.print}
            </Button>
          )}
        </div>
      </section>

      {doc.isError && (
        <div className="print:hidden">
          <ErrorAlert message={doc.error?.message ?? a.failed} />
        </div>
      )}
      {!built && !doc.isError && <p className="text-sm text-muted">{a.building}</p>}
      {built && <AuditDocumentView doc={built} language={language} />}
    </div>
  );
}

function ProjectField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (e: { target: { value: string } }) => void;
  placeholder?: string;
}) {
  const id = useId();
  return (
    <label htmlFor={id} className={labelClass}>
      {label}
      <input
        id={id}
        inputMode="decimal"
        className={fieldClass}
        value={value}
        placeholder={placeholder}
        onChange={onChange}
      />
    </label>
  );
}
