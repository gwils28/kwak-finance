"""Who may see a wealth line or a goal, and which ones a view covers (docs/SPECIFICATIONS.md
§3)."""

import enum
from uuid import UUID


class Visibility(enum.StrEnum):
    PRIVATE = "private"  # its owner only
    SHARED = "shared"  # every household member, still one member's
    JOINT = "joint"  # the household's in common: every member, nobody's own


def can_view(*, owner_id: UUID, visibility: Visibility, viewer_id: UUID) -> bool:
    """Within one household: the owner sees everything, others all but the private ones."""
    return owner_id == viewer_id or visibility is not Visibility.PRIVATE


class Scope(enum.StrEnum):
    """Which wealth lines and goals a view covers (F-WLT-5, F-GOAL-7)."""

    HOUSEHOLD = "household"
    """Everything the viewer can see."""
    MINE = "mine"
    """The viewer's own, without the joint ones even if the viewer created them."""
    JOINT = "joint"
    """The household's joint ones, whoever created them."""


def in_scope(scope: Scope, *, owner_id: UUID, visibility: Visibility, viewer_id: UUID) -> bool:
    if scope is Scope.MINE:
        return owner_id == viewer_id and visibility is not Visibility.JOINT
    if scope is Scope.JOINT:
        return visibility is Visibility.JOINT
    return can_view(owner_id=owner_id, visibility=visibility, viewer_id=viewer_id)
