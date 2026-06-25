"""
Violation.py

Value objects describing what is wrong with a hypothetical schedule.

A Violation is one broken rule. A ViolationReport aggregates all of them and can
group the involved courses into independent "components" — the count of those
components is the admissible heuristic used by the A* cascade search.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Violation:
    kind: str            # e.g. "baseline", "mandatory_spacing", "daily_capacity"
    message: str         # human-readable explanation for the UI
    courses: tuple = field(default_factory=tuple)
    program_id: str = ""
    year: int = 0
    severity: str = "hard"   # "hard" => defines legality, "info" => advisory

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
    # Hard violations define legality.
    violations: list = field(default_factory=list)

    # Informational elective collisions shown to the user.
    collisions: list = field(default_factory=list)

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
        Union-find over the courses that share a hard violation.

        Two courses are in the same component if they appear together in at least
        one violation. Since one exam move touches one course, the number of
        components is an admissible lower bound for the remaining repair moves.
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
            root = find(course_id)
            groups.setdefault(root, set()).add(course_id)

        return list(groups.values())

    def to_dict(self) -> dict:
        return {
            "legal": self.is_legal,
            "is_legal": self.is_legal,
            "violations": [v.to_dict() for v in self.violations],
            "collisions": [c.to_dict() for c in self.collisions],
        }