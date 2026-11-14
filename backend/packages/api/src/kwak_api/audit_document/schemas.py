"""What the audit document's form sends and what the document holds (§4.15).

Amounts are already rounded when the privacy asks for it, and names already replaced by
pseudonyms: the web only lays them out, in the document's language.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from kwak_core.audit_document import Audience, Duration, PropertyAge
from kwak_core.fixed import FixedFrequency
from kwak_core.goals import AidSource, GoalStatus, ProType, Tier
from kwak_core.money import require_cents
from kwak_core.users import Language
from kwak_core.visibility import Scope
from kwak_core.wealth import Milestone, RegulatedType, TaxEnvelope, WealthKind
from pydantic import AfterValidator, BaseModel, Field

Amount = Annotated[Decimal, Field(ge=0, lt=Decimal("1e12")), AfterValidator(require_cents)]
MonthText = Annotated[str, Field(pattern=r"^(19|20)[0-9]{2}-(0[1-9]|1[0-2])$")]


# The form


class AuditPrivacyIn(BaseModel):
    named_members: bool
    named_lines: bool
    exact_amounts: bool


class AuditProjectIn(BaseModel):
    """F-AUD-5: never saved."""

    price: Amount
    notary_fees: Amount | None = None
    """None: 8 % of the price for an older property, 2.5 % for a new one."""
    property_age: PropertyAge = PropertyAge.OLD
    agency_fees: Amount = Decimal(0)
    guarantee_fees: Amount = Decimal(0)
    down_payment: Amount = Decimal(0)
    loan: Amount | None = None
    """None: price + fees - down payment."""
    years: int = Field(ge=1, le=30)
    rate: Decimal = Field(ge=0, le=Decimal("0.2"))
    """The yearly nominal rate, 0.035 for 3.5 %."""
    insurance: Amount = Decimal(0)
    rent: Amount = Decimal(0)
    rent_stops: bool = True


class AuditIn(BaseModel):
    audience: Audience
    scope: Scope = Scope.HOUSEHOLD
    start: MonthText | None = None
    end: MonthText | None = None
    """Both or neither: the last twelve complete months by default."""
    language: Language | None = None
    """The viewer's by default."""
    privacy: AuditPrivacyIn | None = None
    """The audience's defaults when left out."""
    counted: list[UUID] | None = None
    """The income categories the debt ratio counts; all but Refunds by default."""
    withholding: Decimal | None = Field(default=None, ge=0, le=Decimal("0.45"))
    project: AuditProjectIn | None = None


class AuditIssuedIn(BaseModel):
    """A document printed, copied or downloaded: logged without a figure."""

    audience: Audience
    scope: Scope
    start: MonthText
    end: MonthText
    how: Literal["print", "copy", "download"]


# The document


class AuditLabelOut(BaseModel):
    """A name, or the pseudonym to show instead: Member A, PEA 1, Savings accounts 2,
    Long-term goal 1."""

    name: str | None = None
    group: Literal["member", "envelope", "category", "tier"] | None = None
    key: str | None = None
    """The member's letter, the envelope, the category's name as entered or the tier."""
    number: int | None = None


class AuditPeriodOut(BaseModel):
    start: str
    end: str
    months: int
    shortened: bool
    """The history is shorter than twelve months: the period starts at its first month."""


class AuditMemberOut(BaseModel):
    label: AuditLabelOut
    age: int | None
    """In whole years today; none without a birth month (F-RET-1)."""


class AuditHouseholdOut(BaseModel):
    name: str | None
    """None with members anonymised: "the household"."""
    members: list[AuditMemberOut]


class AuditMonthOut(BaseModel):
    month: str
    income: Decimal
    spent: Decimal
    saved: Decimal
    rest: Decimal


class AuditSpreadOut(BaseModel):
    total: Decimal
    average: Decimal
    lowest_month: str
    lowest: Decimal
    highest_month: str
    highest: Decimal


class AuditNamedAmountOut(BaseModel):
    name: str
    amount: Decimal


class AuditYearOut(BaseModel):
    year: int
    months: int
    partial: bool
    income: Decimal
    spent: Decimal
    saved: Decimal
    rest: Decimal


class AuditFixedOut(BaseModel):
    category: str
    frequency: FixedFrequency
    monthly: Decimal


class AuditMoneyOut(BaseModel):
    """Always the household's, in every scope (F-AUD-2)."""

    months: list[AuditMonthOut]
    income: AuditSpreadOut
    spent: AuditSpreadOut
    saved: AuditSpreadOut
    rest: AuditSpreadOut
    no_income: list[str]
    """Months without an income line, counted as 0."""
    income_by_category: list[AuditNamedAmountOut]
    spending_by_category: list[AuditNamedAmountOut]
    """Largest first; the rest grouped in `spending_rest`."""
    spending_rest: Decimal
    fixed: list[AuditFixedOut]
    """The fixed expenses by category, a month (a line's label is never shown)."""
    fixed_monthly: Decimal
    savings_rate: Decimal | None
    """(income - spent) / income, a percentage to one decimal."""
    saved_share: Decimal | None
    """saved / income, a percentage to one decimal."""
    capacity: Decimal
    capacity_start: str | None
    capacity_end: str | None
    capacity_set: bool
    """Set by hand on the goals page rather than measured."""
    years: list[AuditYearOut]


class AuditWealthCategoryOut(BaseModel):
    name: str
    kind: WealthKind
    colour: str
    value: Decimal
    share: Decimal | None
    """Of gross assets, a percentage to one decimal; none for debts."""
    liquid: bool


class AuditWealthLineOut(BaseModel):
    label: AuditLabelOut
    category: str
    kind: WealthKind
    holder: AuditLabelOut | None
    """Who holds it as filed in the app; none for a joint line."""
    value: Decimal
    carried: bool
    """No value entered in the end month: an earlier one carried forward."""
    envelope: TaxEnvelope | None
    opening_year: int | None
    age: int | None
    milestone: Milestone | None
    regulated: RegulatedType | None
    ceiling: Decimal | None


class AuditHolderOut(BaseModel):
    holder: AuditLabelOut | None
    """None: joint."""
    net: Decimal


class AuditDebtOut(BaseModel):
    label: AuditLabelOut
    owed: Decimal
    payment: Decimal | None
    insurance: Decimal
    rate: Decimal
    """A percentage, to the hundredth."""
    ends: str | None


class AuditWealthOut(BaseModel):
    month: str
    categories: list[AuditWealthCategoryOut]
    lines: list[AuditWealthLineOut]
    gross: Decimal
    debts: Decimal
    net: Decimal
    liquid: Decimal
    illiquid: Decimal
    start_month: str
    """The month before the period: the position it opens with."""
    start_net: Decimal
    change: Decimal
    holders: list[AuditHolderOut]
    debt_lines: list[AuditDebtOut]
    carried: bool
    """Some values are carried from earlier months."""


class AuditRatioOut(BaseModel):
    income: Decimal
    """The average monthly income counted, after tax withheld."""
    counted: list[str]
    left_out: list[str]
    payments: Decimal
    """The running debts' payments and insurance a month."""
    ratio: Decimal | None
    """A percentage to one decimal; none without income."""
    above_ceiling: bool
    """Compared on the exact ratio."""
    withholding: Decimal | None
    before_tax_ratio: Decimal | None
    before_tax_above: bool
    remaining: Decimal
    debts: list[AuditDebtOut]
    """The running debts counted, the household's the viewer sees, whatever the scope."""
    left_out_debts: list[AuditLabelOut]
    """Running debts without a payment entered."""


class AuditAidOut(BaseModel):
    source: AidSource
    amount: Decimal
    received: bool


class AuditGoalOut(BaseModel):
    label: AuditLabelOut
    tier: Tier
    target: Decimal
    deadline: str | None
    value: Decimal
    status: GoalStatus
    pro_type: ProType | None
    cost: Decimal | None
    aids: list[AuditAidOut]


class AuditGoalsOut(BaseModel):
    goals: list[AuditGoalOut]
    precaution: Decimal
    """The precaution goals to fill first, added up."""
    precaution_months: Decimal | None
    """In months of fixed expenses, to one decimal."""


class AuditRetirementOut(BaseModel):
    member: AuditLabelOut
    retirement: str
    pension_month: str
    pension: Decimal


class AuditAssumptionOut(BaseModel):
    category: str
    expected_return: Decimal
    """A percentage, to one decimal."""
    volatility: Decimal


class AuditProjectOut(BaseModel):
    price: Decimal
    notary_fees: Decimal
    notary_estimated: bool
    agency_fees: Decimal
    guarantee_fees: Decimal
    down_payment: Decimal
    cost: Decimal
    loan: Decimal
    years: int
    duration: Duration
    rate: Decimal
    """A percentage, to the hundredth."""
    payment: Decimal
    insurance: Decimal
    ratio_after: Decimal | None
    above_ceiling: bool
    before_tax_ratio_after: Decimal | None
    before_tax_above: bool
    remaining_after_housing: Decimal
    rent: Decimal
    rent_stops: bool
    housing_change: Decimal
    average_saved: Decimal
    capacity: Decimal
    down_share: Decimal
    """Of price and fees, a percentage to one decimal."""
    liquid_left: Decimal
    precaution: Decimal


class AuditOut(BaseModel):
    audience: Audience
    scope: Scope
    language: Language
    privacy: AuditPrivacyIn
    generated_at: datetime
    period: AuditPeriodOut
    household: AuditHouseholdOut
    money: AuditMoneyOut
    wealth: AuditWealthOut
    ratio: AuditRatioOut
    goals: AuditGoalsOut
    retirement: list[AuditRetirementOut]
    assumptions: list[AuditAssumptionOut]
    project: AuditProjectOut | None
