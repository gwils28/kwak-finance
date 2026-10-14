from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.transfers import (
    Movement,
    SideEdit,
    TransferEditError,
    find_transfer_pairs,
    link_candidates,
    mirror_edit,
)

CHECKING, SAVINGS, OTHER = uuid4(), uuid4(), uuid4()
D0 = date(2026, 3, 10)


def _m(account: UUID, day: int, amount: str) -> Movement:
    return Movement(
        id=uuid4(), account_id=account, booked_on=D0 + timedelta(days=day), amount=Decimal(amount)
    )


def test_an_outflow_and_an_inflow_of_the_same_amount_in_two_accounts_pair_up() -> None:
    out, inn = _m(CHECKING, 0, "-150.00"), _m(SAVINGS, 1, "150.00")
    assert find_transfer_pairs([out, inn]) == [(out.id, inn.id)]


def test_no_pair_within_one_account_or_for_different_amounts_or_far_apart() -> None:
    assert find_transfer_pairs([_m(CHECKING, 0, "-150.00"), _m(CHECKING, 0, "150.00")]) == []
    assert find_transfer_pairs([_m(CHECKING, 0, "-150.00"), _m(SAVINGS, 0, "150.01")]) == []
    assert find_transfer_pairs([_m(CHECKING, 0, "-150.00"), _m(SAVINGS, 4, "150.00")]) == []
    assert len(find_transfer_pairs([_m(CHECKING, 0, "-150.00"), _m(SAVINGS, 3, "150.00")])) == 1


def test_the_closest_date_wins() -> None:
    out = _m(CHECKING, 0, "-100.00")
    far, near = _m(SAVINGS, 3, "100.00"), _m(OTHER, -1, "100.00")
    assert find_transfer_pairs([out, far, near]) == [(out.id, near.id)]


def test_two_identical_transfers_pair_one_to_one() -> None:
    outs = [_m(CHECKING, 0, "-50.00"), _m(CHECKING, 0, "-50.00")]
    ins = [_m(SAVINGS, 0, "50.00"), _m(SAVINGS, 1, "50.00")]
    pairs = find_transfer_pairs(outs + ins)
    assert len(pairs) == 2
    assert {o for o, _ in pairs} == {m.id for m in outs}


movements = st.lists(
    st.builds(
        _m,
        st.sampled_from([CHECKING, SAVINGS, OTHER]),
        st.integers(0, 10),
        st.sampled_from(["-50.00", "50.00", "-120.00", "120.00", "-7.30", "300.00"]),
    ),
    max_size=30,
)


@given(movements)
def test_pairs_net_to_zero_across_two_accounts_and_never_reuse_a_movement(
    ms: list[Movement],
) -> None:
    """Invariant §8.3."""
    by_id = {m.id: m for m in ms}
    pairs = find_transfer_pairs(ms)
    used = [i for pair in pairs for i in pair]
    assert len(used) == len(set(used))
    for out_id, in_id in pairs:
        out, inn = by_id[out_id], by_id[in_id]
        assert out.amount < 0 < inn.amount
        assert out.amount + inn.amount == 0
        assert out.account_id != inn.account_id
        assert abs((out.booked_on - inn.booked_on).days) <= 3


@given(movements)
def test_the_result_does_not_depend_on_input_order(ms: list[Movement]) -> None:
    assert sorted(find_transfer_pairs(ms)) == sorted(find_transfer_pairs(list(reversed(ms))))


def test_link_candidates_are_the_opposite_amount_on_another_account_within_31_days() -> None:
    side = _m(CHECKING, 0, "-500.00")
    near, far = _m(SAVINGS, 6, "500.00"), _m(OTHER, -20, "500.00")
    others = [
        _m(SAVINGS, 32, "500.00"),  # too far
        _m(SAVINGS, 1, "499.00"),  # not the same amount
        _m(SAVINGS, 1, "-500.00"),  # same direction
        _m(CHECKING, 1, "500.00"),  # same account
    ]
    assert link_candidates(side, [far, near, side, *others]) == [near.id, far.id]


def test_link_candidates_tie_on_distance_break_on_date() -> None:
    side = _m(CHECKING, 0, "500.00")
    before, after = _m(SAVINGS, -2, "-500.00"), _m(OTHER, 2, "-500.00")
    assert link_candidates(side, [after, before]) == [before.id, after.id]


def test_editing_a_side_moves_a_manual_other_side_with_it() -> None:
    out, inn = _m(CHECKING, 0, "-500.00"), _m(SAVINGS, 1, "500.00")
    edit = SideEdit(amount=Decimal("-550.00"), booked_on=out.booked_on + timedelta(days=3))
    assert mirror_edit(out, inn, edit, other_manual=True) == SideEdit(
        amount=Decimal("550.00"), booked_on=inn.booked_on + timedelta(days=3)
    )


def test_a_side_from_a_statement_locks_the_amount_but_not_the_date() -> None:
    out, inn = _m(CHECKING, 0, "-500.00"), _m(SAVINGS, 0, "500.00")
    with pytest.raises(TransferEditError, match="locked"):
        mirror_edit(inn, out, SideEdit(amount=Decimal("450.00")), other_manual=False)
    later = SideEdit(amount=Decimal("500.00"), booked_on=inn.booked_on + timedelta(days=1))
    assert mirror_edit(inn, out, later, other_manual=False) == SideEdit()


def test_a_side_keeps_its_direction() -> None:
    out, inn = _m(CHECKING, 0, "-500.00"), _m(SAVINGS, 0, "500.00")
    for amount in ("500.00", "0.00"):
        with pytest.raises(TransferEditError, match="direction"):
            mirror_edit(out, inn, SideEdit(amount=Decimal(amount)), other_manual=True)


cents = st.integers(1, 10**8).map(lambda c: Decimal(c) / 100)


@given(cents, st.lists(st.tuples(st.booleans(), cents, st.integers(-40, 40)), max_size=10))
def test_edits_keep_both_sides_opposite(
    start: Decimal, edits: list[tuple[bool, Decimal, int]]
) -> None:
    """Invariant §8.3: whatever side is edited, the transfer still nets to zero."""
    sides = [_m(CHECKING, 0, str(-start)), _m(SAVINGS, 0, str(start))]
    for on_outflow, size, days in edits:
        side, other = sides if on_outflow else sides[::-1]
        edit = SideEdit(
            amount=-size if side.amount < 0 else size,
            booked_on=side.booked_on + timedelta(days=days),
        )
        mirrored = mirror_edit(side, other, edit, other_manual=True)
        new_side = Movement(
            side.id, side.account_id, edit.booked_on or side.booked_on, edit.amount or side.amount
        )
        new_other = Movement(
            other.id,
            other.account_id,
            mirrored.booked_on or other.booked_on,
            other.amount if mirrored.amount is None else mirrored.amount,
        )
        sides = [new_side, new_other] if on_outflow else [new_other, new_side]
        assert sides[0].amount + sides[1].amount == 0
        assert sides[0].amount < 0 < sides[1].amount
