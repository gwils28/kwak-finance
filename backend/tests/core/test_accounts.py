from uuid import UUID, uuid4

from hypothesis import given
from hypothesis import strategies as st
from kwak_core.accounts import CASH_TYPES, AccountType, Visibility, can_view

OWNER, OTHER = uuid4(), uuid4()


def test_the_owner_always_sees_their_account() -> None:
    for visibility in Visibility:
        assert can_view(owner_id=OWNER, visibility=visibility, viewer_id=OWNER)


def test_private_accounts_are_hidden_from_other_members() -> None:
    assert not can_view(owner_id=OWNER, visibility=Visibility.PRIVATE, viewer_id=OTHER)


def test_shared_accounts_are_visible_to_every_member() -> None:
    assert can_view(owner_id=OWNER, visibility=Visibility.SHARED, viewer_id=OTHER)


@given(st.sampled_from(list(Visibility)), st.uuids(), st.uuids())
def test_only_shared_accounts_are_visible_to_someone_else(
    visibility: Visibility, owner: UUID, viewer: UUID
) -> None:
    visible = can_view(owner_id=owner, visibility=visibility, viewer_id=viewer)
    assert visible == (owner == viewer or visibility is Visibility.SHARED)


def test_cash_accounts_are_checking_and_savings() -> None:
    assert {AccountType.CHECKING, AccountType.SAVINGS} == CASH_TYPES
    assert AccountType.EMPLOYEE_SAVINGS.value == "employee_savings"
