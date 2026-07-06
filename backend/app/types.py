"""Shared type aliases (CODE_BLUEPRINT.md §0)."""
from typing import Literal, TypedDict

TriState = Literal["pass", "fail", "unknown"]


class Criterion(TypedDict):
    state: TriState
    value: float | None
    detail: str
