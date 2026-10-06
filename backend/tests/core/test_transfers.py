from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from hypothesis import given
from hypothesis import strategies as st
from kwak_core.transfers import Movement, find_transfer_pairs

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
