"""
Violation.py

Small value objects used by the what-if scheduler to describe schedule problems.

A Violation is one broken rule.
A ViolationReport groups all schedule problems found by the ConstraintEvaluator.

Hard violations affect legality.
Informational collisions are shown to the user but do not necessarily make the
schedule illegal.
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

    def to_dict(self) -> dict:
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
    """
    Holds all violations found for a schedule.

    violations:
        Hard rule breaks. These decide if the schedule is legal.

    collisions:
        Informational elective collisions. These are useful for the UI, but they
        do not always make the schedule illegal.
    """

    violations: List[Violation] = field(default_factory=list)
    collisions: List[Violation] = field(default_factory=list)

    @property
    def is_legal(self) -> bool:
        return not self.violations

    def involved_courses(self) -> set:
        out = set()
        for violation in self.violations:
            out.update(violation.courses)
        return out

    def components(self) -> list:
        """
        Groups courses that are connected by hard violations.

        This is used by the cascade resolver. If two violations share a course,
        they belong to the same component. The number of components is a safe
        lower-bound estimate for how many independent problems remain.
        """
        parent = {}

        def find(x):
            parent.setdefault(x, x)
            root = x

            while parent[root] != root:
                root = parent[root]

            while parent[x] != x:
                parent[x], x = root, parent[x]

            return root

        def union(a, b):
            parent[find(a)] = find(b)

        for violation in self.violations:
            courses = list(violation.courses)

            if not courses:
                continue

            for course_id in courses:
                parent.setdefault(course_id, course_id)

            first = courses[0]
            for course_id in courses[1:]:
                union(first, course_id)

        groups = {}
        for course_id in parent:
            groups.setdefault(find(course_id), set()).add(course_id)

        return list(groups.values())

    def to_dict(self) -> dict:
        return {
            "legal": self.is_legal,
            "is_legal": self.is_legal,
            "violations": [v.to_dict() for v in self.violations],
            "collisions": [c.to_dict() for c in self.collisions],
        }