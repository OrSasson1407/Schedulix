"""
ConstraintEvaluator.py
Strategy object that inspects a Schedule and returns a structured ViolationReport
instead of a single boolean. It answers the two UI questions directly:

  * Which baseline requirements were violated?   -> report.violations (hard)
  * Which elective courses are now colliding?    -> report.collisions (info)

"Baseline" always includes the fundamental legality rule (two exams of the same
program & year on the same day, where at least one is mandatory). On top of that,
every ACTIVE hard constraint from SchedulingConstraints contributes its own
violations. Elective collisions are always listed for display, and additionally
become a hard violation when the elective-collisions constraint is enabled and
its limit k is exceeded.
"""

from .Violation import Violation, ViolationReport


class ConstraintEvaluator:
    def __init__(self, constraints, companion_dates=None):
        self.constraints = constraints
        # {course_id: date} of the SAME course's exam in the OTHER moed. Used to
        # enforce the Moed A <-> Moed B spacing constraint while editing one moed.
        self.companion_dates = companion_dates or {}

    # ------------------------------------------------------------------ #
    def evaluate(self, schedule) -> ViolationReport:
        records = self._records(schedule)
        names = {r["course_id"]: r["name"] for r in records}
        report = ViolationReport()

        self._check_baseline(records, report)

        c = self.constraints
        if c is not None:
            if c.enabled("mandatory_spacing"):
                self._check_spacing(records, c.k("mandatory_spacing"), True, "mandatory_spacing", report)
            if c.enabled("general_spacing"):
                self._check_spacing(records, c.k("general_spacing"), False, "general_spacing", report)
            if c.enabled("mandatory_window"):
                self._check_window(records, c.k("mandatory_window"), report)
            if c.enabled("daily_capacity"):
                self._check_daily_capacity(records, c.k("daily_capacity"), names, report)
            if c.enabled("moed_spacing") and self.companion_dates:
                self._check_moed_spacing(records, c.k("moed_spacing"), report)

        # Elective collisions: always reported as info; promoted to a hard
        # violation if the constraint is enabled and its limit is exceeded.
        collisions = self._elective_collisions(records)
        for pair in collisions:
            a, b, ds = pair
            report.collisions.append(
                Violation(
                    kind="elective_collision",
                    message=f"Electives '{names[a]}' and '{names[b]}' both on {ds}",
                    courses=(a, b),
                    severity="info",
                )
            )
        if c is not None and c.enabled("elective_collisions"):
            k = c.k("elective_collisions")
            if len(collisions) > k:
                involved = tuple({cid for pair in collisions for cid in pair[:2]})
                report.violations.append(
                    Violation(
                        kind="elective_collisions",
                        message=f"{len(collisions)} elective collisions exceed the limit of {k}",
                        courses=involved,
                        severity="hard",
                    )
                )

        return report

    # ------------------------------------------------------------------ #
    @staticmethod
    def _records(schedule):
        records = []
        for (course, moed), exam_date in schedule.assignments.items():
            raw = exam_date.date
            day = raw.date() if hasattr(raw, "date") else raw
            ds = raw.strftime("%Y-%m-%d") if hasattr(raw, "strftime") else str(raw)
            for prog in course.programs:
                records.append(
                    {
                        "course_id": course.course_id,
                        "name": course.name,
                        "program_id": prog.program_id,
                        "year": prog.year,
                        "requirement": prog.requirement,
                        "moed": moed,
                        "day": day,
                        "date_str": ds,
                    }
                )
        return records

    @staticmethod
    def _check_baseline(records, report):
        """Fundamental rule: same program+year+day with at least one mandatory exam."""
        groups = {}
        for r in records:
            groups.setdefault((r["program_id"], r["year"], r["day"]), []).append(r)

        for (pid, year, day), group in groups.items():
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    if a["course_id"] == b["course_id"]:
                        continue
                    if a["requirement"] == "Obligatory" or b["requirement"] == "Obligatory":
                        report.violations.append(
                            Violation(
                                kind="baseline",
                                message=(
                                    f"'{a['name']}' and '{b['name']}' clash on {a['date_str']} "
                                    f"(program {pid}, year {year})"
                                ),
                                courses=(a["course_id"], b["course_id"]),
                                program_id=pid,
                                year=year,
                            )
                        )

    @staticmethod
    def _check_spacing(records, k, mandatory_only, kind, report):
        groups = {}
        for r in records:
            if mandatory_only and r["requirement"] != "Obligatory":
                continue
            groups.setdefault((r["program_id"], r["year"]), []).append(r)

        for (pid, year), group in groups.items():
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    if a["course_id"] == b["course_id"]:
                        continue
                    gap = abs((a["day"] - b["day"]).days)
                    if gap < k:
                        report.violations.append(
                            Violation(
                                kind=kind,
                                message=(
                                    f"'{a['name']}' and '{b['name']}' are {gap}d apart "
                                    f"(need >= {k}; program {pid}, year {year})"
                                ),
                                courses=(a["course_id"], b["course_id"]),
                                program_id=pid,
                                year=year,
                            )
                        )

    @staticmethod
    def _check_window(records, k, report):
        groups = {}
        for r in records:
            if r["requirement"] != "Obligatory":
                continue
            groups.setdefault((r["program_id"], r["year"], r["moed"]), []).append(r)

        for (pid, year, moed), group in groups.items():
            if len(group) < 2:
                continue
            days = [r["day"] for r in group]
            span = (max(days) - min(days)).days
            if span < k:
                report.violations.append(
                    Violation(
                        kind="mandatory_window",
                        message=(
                            f"Mandatory window for program {pid} year {year} ({moed}) "
                            f"is {span}d (need >= {k})"
                        ),
                        courses=tuple(r["course_id"] for r in group),
                        program_id=pid,
                        year=year,
                    )
                )

    def _check_moed_spacing(self, records, k, report):
        """
        For each course in this (single-moed) schedule that also has an exam in the
        OTHER moed (companion_dates), the gap between the two must be >= k days.
        """
        by_course = {}
        for r in records:
            by_course.setdefault(r["course_id"], r)  # one representative per course

        for cid, r in by_course.items():
            companion = self.companion_dates.get(cid)
            if companion is None:
                continue
            gap = abs((r["day"] - companion).days)
            if gap < k:
                report.violations.append(
                    Violation(
                        kind="moed_spacing",
                        message=(
                            f"'{r['name']}' Moed A/B exams are {gap}d apart (need >= {k})"
                        ),
                        courses=(cid,),
                    )
                )

    @staticmethod
    def _check_daily_capacity(records, k, names, report):
        by_day = {}
        for r in records:
            by_day.setdefault(r["day"], set()).add(r["course_id"])
        for day, course_ids in by_day.items():
            if len(course_ids) > k:
                ds = next(r["date_str"] for r in records if r["day"] == day)
                report.violations.append(
                    Violation(
                        kind="daily_capacity",
                        message=f"{len(course_ids)} exams on {ds} exceed the daily limit of {k}",
                        courses=tuple(course_ids),
                    )
                )

    @staticmethod
    def _elective_collisions(records):
        """Returns a list of (course_a, course_b, date_str) elective collision pairs."""
        by_program = {}
        for r in records:
            if r["requirement"] != "Elective":
                continue
            by_program.setdefault(r["program_id"], []).append(r)

        seen = set()
        pairs = []
        for group in by_program.values():
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    if a["course_id"] == b["course_id"]:
                        continue
                    if a["day"] == b["day"]:
                        key = tuple(sorted((a["course_id"], b["course_id"]))) + (a["date_str"],)
                        if key in seen:
                            continue
                        seen.add(key)
                        pairs.append((a["course_id"], b["course_id"], a["date_str"]))
        return pairs
