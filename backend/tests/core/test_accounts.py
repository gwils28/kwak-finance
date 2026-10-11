from uuid import UUID, uuid4

from hypothesis import given
from hypothesis import strategies as st
from kwak_core.accounts import CASH_TYPES, AccountType, Scope, Visibility, can_view, in_scope

OWNER, OTHER = uuid4(), uuid4()


def test_the_owner_always_sees_their_account() -> None:
    for visibility in Visibility:
        assert can_view(owner_id=OWNER, visibility=visibility, viewer_id=OWNER)


def test_private_accounts_are_hidden_from_other_members() -> None:
    assert not can_view(owner_id=OWNER, visibility=Visibility.PRIVATE, viewer_id=OTHER)


def test_shared_accounts_are_visible_to_every_member() -> None:
    assert can_view(owner_id=OWNER, visibility=Visibility.SHARED, viewer_id=OTHER)


def test_joint_accounts_are_visible_to_every_member() -> None:
    assert can_view(owner_id=OWNER, visibility=Visibility.JOINT, viewer_id=OTHER)


@given(st.sampled_from(list(Visibility)), st.uuids(), st.uuids())
def test_only_private_accounts_are_hidden_from_someone_else(
    visibility: Visibility, owner: UUID, viewer: UUID
) -> None:
    visible = can_view(owner_id=owner, visibility=visibility, viewer_id=viewer)
    assert visible == (owner == viewer or visibility is not Visibility.PRIVATE)


def test_my_accounts_leave_out_the_joint_one_i_created() -> None:
    assert in_scope(Scope.MINE, owner_id=OWNER, visibility=Visibility.SHARED, viewer_id=OWNER)
    assert not in_scope(Scope.MINE, owner_id=OWNER, visibility=Visibility.JOINT, viewer_id=OWNER)
    assert not in_scope(Scope.MINE, owner_id=OTHER, visibility=Visibility.SHARED, viewer_id=OWNER)


def test_the_joint_scope_holds_joint_accounts_whoever_created_them() -> None:
    assert in_scope(Scope.JOINT, owner_id=OTHER, visibility=Visibility.JOINT, viewer_id=OWNER)
    assert not in_scope(Scope.JOINT, owner_id=OWNER, visibility=Visibility.SHARED, viewer_id=OWNER)


@given(st.sampled_from(list(Visibility)), st.sampled_from([OWNER, OTHER]))
def test_the_household_is_my_accounts_plus_the_joint_ones_plus_what_others_share(
    visibility: Visibility, owner: UUID
) -> None:
    def scoped(scope: Scope) -> bool:
        return in_scope(scope, owner_id=owner, visibility=visibility, viewer_id=OWNER)

    others_shared = owner != OWNER and visibility is Visibility.SHARED
    assert not (scoped(Scope.MINE) and scoped(Scope.JOINT))
    assert scoped(Scope.HOUSEHOLD) == (scoped(Scope.MINE) or scoped(Scope.JOINT) or others_shared)
    visible = can_view(owner_id=owner, visibility=visibility, viewer_id=OWNER)
    assert scoped(Scope.HOUSEHOLD) == visible


def test_cash_accounts_are_checking_and_savings() -> None:
    assert {AccountType.CHECKING, AccountType.SAVINGS} == CASH_TYPES
    assert AccountType.EMPLOYEE_SAVINGS.value == "employee_savings"
