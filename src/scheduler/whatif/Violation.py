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
    courses: tuple       # tuple of course_ids involved in this violation
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
    # Hard violations define legality (baseline rule + active hard constraints).
    violations: list = field(default_factory=list)
    # Informational elective collisions ("which electives are now colliding").
    collisions: list = field(default_factory=list)

    @property
    def is_legal(self) -> bool:
        return not self.violations

    def involved_courses(self) -> set:
        out = set()
        for v in self.violations:
            out.update(v.courses)
        return out

    def components(self) -> list:
        """
        Union-find over the courses that share a hard violation. Two courses are in
        the same component if they appear together in some violation. A single exam
        move touches exactly one course, so it can repair at most one component —
        therefore the number of components is an admissible lower bound on the
        remaining moves (the A* heuristic).
        """
        parent = {}

        def find(x):
            parent.setdefault(x, x)
            root = x
            while parent[root] != root:
                root = parent[root]
            while parent[x] != root:
                parent[x], x = root, parent[x]
            return root

        def union(a, b):
            parent[find(a)] = find(b)

        for v in self.violations:
            cs = list(v.courses)
            for c in cs[1:]:
                union(cs[0], c)

        roots = {find(c) for v in self.violations for c in v.courses}
        return list(roots)

    def to_dict(self) -> dict:
        return {
            "legal": self.is_legal,
            "violations": [v.to_dict() for v in self.violations],
            "collisions": [c.to_dict() for c in self.collisions],
        }