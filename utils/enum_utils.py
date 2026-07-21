"""Small helper for enum-backed dropdown widgets."""
from __future__ import annotations

from typing import Dict, Type, TypeVar

E = TypeVar("E")


def label_lookup(enum_cls: Type[E]) -> Dict[str, E]:
    """Map each member's `.label` back to the member, for CTkOptionMenu selections."""
    return {member.label: member for member in enum_cls}
