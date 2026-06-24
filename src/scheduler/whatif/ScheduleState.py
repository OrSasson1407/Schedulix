"""
ScheduleState.py
Immutable, hashable snapshot of a hypothetical schedule (a Memento). States are
the nodes of the search tree explored by the CascadeResolver.

assignments : frozenset of ((course_id, moed), date_ordinal)
pinned      : frozenset of (course_id, moed) that may NOT be moved
              (the exam the user dragged, plus anything already confirmed).
"""

from dataclasses import dataclass
from .Move import Move


@dataclass(frozen=True)
class ScheduleState:
    assignments: frozenset
    pinned: frozenset = frozenset()

    def as_map(self) -> dict:
        """Returns a mutable {(course_id, moed): ordinal} view of the assignments."""
        return dict(self.assignments)

    def with_move(self, move: Move) -> "ScheduleState":
        """Returns a NEW state with the given move applied (pins are preserved)."""
        m = self.as_map()
        m[(move.course_id, move.moed)] = move.to_ordinal
        return ScheduleState(frozenset(m.items()), self.pinned)

    def with_pin(self, course_id: str, moed: str) -> "ScheduleState":
        """Returns a NEW state where (course_id, moed) is pinned (immutable)."""
        return ScheduleState(self.assignments, self.pinned | {(course_id, moed)})

    def signature(self):
        """Hashable identity used for the visited-set in the search."""
        return self.assignments
