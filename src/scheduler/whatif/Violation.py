"""
Violation.py
Small value objects used by the what-if scheduler to describe schedule problems.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Violation:
    kind: str
    message: str
    courses: Tuple[str, ...] = field(default_factory=tuple)
    program_id: Optional[str] = None
    year: Optional[int] = None
    severity: str = "hard"

    def to_dict(self):
        return {
            "kind": self.kind,
            "message": self.message,
            "courses": list(self.courses),
            "program_id": self.program_id,
            "year": self.year,
            "severity": self.severity,
        }


@dataclass
class ViolationReport:
    violations: List[Violation] = field(default_factory=list)
    collisions: List[Violation] = field(default_factory=list)

    @property
    def is_legal(self) -> bool:
        return len(self.violations) == 0

    def to_dict(self):
        return {
            "is_legal": self.is_legal,
            "violations": [v.to_dict() for v in self.violations],
            "collisions": [c.to_dict() for c in self.collisions],
        }

    def involved_courses(self):
        return {course_id for v in self.violations for course_id in v.courses}

    def components(self):
        return [set(v.courses) for v in self.violations]