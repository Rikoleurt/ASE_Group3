"""Who may do what with a corrected copy (#84), with no database.

Levels, each including the ones before it:
    view     see the copy, its change log and its image
    comment  also comment on boxes (#86)
    edit     also change boxes and undo changes
    manage   also share the copy, change and revoke others' access
    owner    also delete the copy; nobody can change the owner's access

A user's level is the higher of their own share and the copy's level for everyone logged
in. The everyone-level stops at edit: managing is only ever given to named people.
"""
from typing import Literal

Level = Literal["view", "comment", "edit", "manage", "owner"]
ShareLevel = Literal["view", "comment", "edit", "manage"]
EveryoneLevel = Literal["none", "view", "comment", "edit"]
LEVELS: tuple[str, ...] = ("view", "comment", "edit", "manage", "owner")


def rank(level: str | None) -> int:
    """0 for no access, then 1 (view) to 5 (owner)."""
    return LEVELS.index(level) + 1 if level in LEVELS else 0


def level_of(owner_id: int, everyone: str, user_id: int, share: str | None) -> str | None:
    """The user's level on a copy, or None when they may not see it at all."""
    if user_id == owner_id:
        return "owner"
    best = max((share, everyone if everyone != "none" else None), key=rank)
    return best if rank(best) else None


def allows(level: str | None, needed: str) -> bool:
    return rank(level) >= rank(needed)


REFUSALS = {
    "comment": "You can view this copy but not comment on it.",
    "edit": "You can view this copy but not change it.",
    "manage": "Only the owner and people who manage this copy can change who it is shared with.",
    "owner": "Only the owner can delete this copy.",
}
