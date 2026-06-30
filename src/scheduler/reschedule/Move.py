"""
Move.py
A single hypothetical exam relocation, modelled as an immutable Command /
value object. A Move relocates one (course, moed) assignment from one date
ordinal to another. Ordinals index into the moed's available-dates list.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Move:
    course_id: str
    moed: str
    from_ordinal: int
    to_ordinal: int

    def inverse(self) -> "Move":
        """Returns the Move that undoes this one (used for trail/undo logic)."""
        return Move(self.course_id, self.moed, self.to_ordinal, self.from_ordinal)
