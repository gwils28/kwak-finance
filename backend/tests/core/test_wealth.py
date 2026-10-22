from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.budget import Month, month_range
from kwak_core.users import Language
from kwak_core.visibility import Scope, Visibility
from kwak_core.wealth import (
    DEFAULT_WEALTH_CATEGORIES,
    CategoryInput,
    LineInput,
    WealthKind,
    WealthValueError,
    check_value,
    in_scope,
    line_cell,
    to_update,
    wealth_matrix,
)

D = Decimal
AUG, SEP, OCT, NOV, DEC = (Month(2026, m) for m in (8, 9, 10, 11, 12))
ME, OTHER = uuid4(), uuid4()
STOCKS = CategoryInput(uuid4(), WealthKind.ASSET)
GOLD = CategoryInput(uuid4(), WealthKind.ASSET)
DEBTS = CategoryInput(uuid4(), WealthKind.DEBT)
CATEGORIES = [STOCKS, GOLD, DEBTS]


def _line(
    category: CategoryInput,
    values: dict[Month, Decimal],
    *,
    closed_from: Month | None = None,
    owner: UUID = ME,
    visibility: Visibility = Visibility.SHARED,
) -> LineInput:
    return LineInput(uuid4(), category.id, values, owner, visibility, closed_from=closed_from)


def test_a_month_without_a_value_carries_the_previous_one() -> None:
    values = {OCT: D("1000"), DEC: D("1200")}
    assert line_cell(values, SEP) is None  # before its first value: empty
    october, november, december = (line_cell(values, m) for m in (OCT, NOV, DEC))
    assert october is not None
    assert (october.amount, october.carried) == (D("1000"), False)
    assert november is not None
    assert (november.amount, november.carried) == (D("1000"), True)
    assert december is not None
    assert december.carried is False


def test_a_closed_line_leaves_the_months_after() -> None:
    values = {OCT: D("1000")}
    assert line_cell(values, NOV, closed_from=DEC) is not None
    assert line_cell(values, DEC, closed_from=DEC) is None


def test_the_matrix_gives_subtotals_gross_debts_net_and_changes() -> None:
    pea = _line(STOCKS, {OCT: D("10000"), NOV: D("10500")})
    cto = _line(STOCKS, {OCT: D("2000")})
    loan = _line(DEBTS, {OCT: D("5000"), NOV: D("4800")})

    m = wealth_matrix(CATEGORIES, [pea, cto, loan], [OCT, NOV])

    assert m.categories == {
        STOCKS.id: [D("12000"), D("12500")],
        GOLD.id: [D("0"), D("0")],  # every category has its row, in the given order
        DEBTS.id: [D("5000"), D("4800")],
    }
    assert list(m.categories) == [STOCKS.id, GOLD.id, DEBTS.id]
    assert (m.gross, m.debts, m.net) == (
        [D("12000"), D("12500")],
        [D("5000"), D("4800")],
        [D("7000"), D("7700")],
    )
    assert m.change == [None, D("700")]
    assert m.change_ratio[1] == D("0.1")
    assert m.shares == {STOCKS.id: D("1"), GOLD.id: D("0")}
    assert m.line_shares[pea.id] == D("10500") / D("12500")


def test_the_kind_is_the_categorys() -> None:
    with pytest.raises(ValueError, match="unknown category"):
        wealth_matrix([STOCKS], [_line(DEBTS, {OCT: D("1")})], [OCT])


def test_the_first_month_shown_compares_with_the_month_before_it() -> None:
    pea = _line(STOCKS, {SEP: D("900"), OCT: D("1000")})
    m = wealth_matrix(CATEGORIES, [pea], [OCT, NOV])
    assert m.change == [D("100"), D("0")]


def test_a_month_holding_nothing_is_no_reference() -> None:
    pea = _line(STOCKS, {OCT: D("500")})
    m = wealth_matrix(CATEGORIES, [pea], [AUG, SEP, OCT])
    # The same answer whatever month the window starts on.
    assert m.change == [None, None, None]
    closed = _line(STOCKS, {AUG: D("500")}, closed_from=SEP)
    assert wealth_matrix(CATEGORIES, [closed], [AUG, SEP, OCT]).change == [None, None, None]


def test_debts_only_and_a_zero_reference() -> None:
    loan = _line(DEBTS, {SEP: D("1000"), OCT: D("800")})
    m = wealth_matrix(CATEGORIES, [loan], [SEP, OCT])
    assert (m.gross, m.net) == ([D("0"), D("0")], [D("-1000"), D("-800")])
    assert m.shares == {}  # no gross assets to share
    assert m.change_ratio == [None, D("0.2")]  # from -1000 to -800: better
    zero = _line(STOCKS, {SEP: D("0"), OCT: D("100")})
    assert wealth_matrix(CATEGORIES, [zero], [SEP, OCT]).change_ratio == [None, None]


def test_no_month_and_no_line() -> None:
    m = wealth_matrix(CATEGORIES, [], [])
    assert (m.gross, m.net, m.change) == ([], [], [])
    empty = wealth_matrix(CATEGORIES, [], [OCT])
    assert (empty.net, empty.change, empty.change_ratio) == ([D("0")], [None], [None])


def test_values_are_positive_cents() -> None:
    check_value(D("0"))
    with pytest.raises(WealthValueError):
        check_value(D("-1"))
    with pytest.raises(WealthValueError):
        check_value(D("1.005"))  # cents at most


def test_update_this_month_lists_the_open_lines_with_their_last_value() -> None:
    pea = _line(STOCKS, {SEP: D("900")})
    sold = _line(GOLD, {SEP: D("300")}, closed_from=OCT)
    new = _line(GOLD, {})
    assert to_update([pea, sold, new], OCT) == [(pea, D("900")), (new, None)]


def test_scopes_select_lines_by_visibility() -> None:
    mine = _line(STOCKS, {OCT: D("1")})
    theirs = _line(STOCKS, {OCT: D("2")}, owner=OTHER)
    hidden = _line(STOCKS, {OCT: D("4")}, owner=OTHER, visibility=Visibility.PRIVATE)
    joint = _line(STOCKS, {OCT: D("8")}, visibility=Visibility.JOINT)
    lines = [mine, theirs, hidden, joint]
    assert in_scope(lines, Scope.MINE, ME) == [mine]
    assert in_scope(lines, Scope.JOINT, ME) == [joint]
    assert in_scope(lines, Scope.HOUSEHOLD, ME) == [mine, theirs, joint]


def test_default_categories_end_with_the_debts() -> None:
    names = [c.names.name(Language.FR) for c in DEFAULT_WEALTH_CATEGORIES]
    assert names[:2] == ["Livrets", "Comptes courants"]
    assert names[-1] == "Dettes"
    assert [c.kind for c in DEFAULT_WEALTH_CATEGORIES].count(WealthKind.DEBT) == 1
    assert len({c.colour for c in DEFAULT_WEALTH_CATEGORIES}) == len(DEFAULT_WEALTH_CATEGORIES)
    # Every category takes lines entered by hand, the bank accounts' ones too (F-WLT-4).
    assert not any(hasattr(c, "holds") for c in DEFAULT_WEALTH_CATEGORIES)


ALL = month_range(Month(2026, 1), Month(2026, 12))
amounts = st.integers(0, 1_000_000_00).map(lambda c: D(c) / 100)
lines_strategy = st.lists(
    st.builds(
        _line,
        st.sampled_from(CATEGORIES),
        st.dictionaries(st.sampled_from(ALL), amounts, max_size=6),
        closed_from=st.one_of(st.none(), st.sampled_from(ALL)),
        owner=st.sampled_from([ME, OTHER]),
        visibility=st.sampled_from(list(Visibility)),
    ),
    max_size=8,
)


@given(lines_strategy)
def test_values_carry_forward_and_net_worth_is_assets_minus_debts(
    lines: list[LineInput],
) -> None:
    """Invariants §8.5 and §8.6."""
    m = wealth_matrix(CATEGORIES, lines, ALL)
    kinds = {c.id: c.kind for c in CATEGORIES}
    for i, month in enumerate(ALL):
        for line in lines:
            cell = m.lines[line.id][i]
            earlier = [mm for mm in line.values if mm <= month]
            if not earlier or (line.closed_from is not None and month >= line.closed_from):
                assert cell is None
            else:
                assert cell is not None
                assert cell.amount == line.values[max(earlier)]
        for category in CATEGORIES:
            cells = [m.lines[ln.id][i] for ln in lines if ln.category_id == category.id]
            assert m.categories[category.id][i] == sum((c.amount for c in cells if c), D(0))
        assets = sum(
            (m.categories[c][i] for c in m.categories if kinds[c] is WealthKind.ASSET), D(0)
        )
        debts = sum((m.categories[c][i] for c in m.categories if kinds[c] is WealthKind.DEBT), D(0))
        assert (m.gross[i], m.debts[i], m.net[i]) == (assets, debts, assets - debts)


@given(lines_strategy)
def test_the_household_is_mine_plus_joint_plus_what_others_share(
    lines: list[LineInput],
) -> None:
    """Invariant §8.6, as invariant 11."""

    def net(scoped: list[LineInput]) -> list[Decimal]:
        return wealth_matrix(CATEGORIES, scoped, ALL).net

    others = [ln for ln in lines if ln.owner_id != ME and ln.visibility is Visibility.SHARED]
    parts = [
        net(in_scope(lines, Scope.MINE, ME)),
        net(in_scope(lines, Scope.JOINT, ME)),
        net(others),
    ]
    household = net(in_scope(lines, Scope.HOUSEHOLD, ME))
    assert household == [sum(column, D(0)) for column in zip(*parts, strict=True)]
