"""
Constraints.py
Defines the user-configurable HARD constraints for the scheduling engine.

A "hard constraint" means that any generated schedule which violates an ACTIVE
condition is immediately disqualified (dropped) by the scheduler.

Each of the five constraints exposes:
  * an independent boolean toggle  ("enabled")
  * an independent integer parameter ("k")

Day differences always count calendar days (weekends and holidays included),
since they are computed directly on the assigned exam dates.
"""


class SchedulingConstraints:
    """
    Holds the configuration for the five optional hard constraints and knows
    how to validate a Schedule against every active constraint.
    """

    # Stable ordering / identity for the five constraints.
    KEYS = (
        "mandatory_spacing",
        "general_spacing",
        "elective_collisions",
        "mandatory_window",
        "daily_capacity",
        "moed_spacing",
    )

    # Default state: every constraint is OFF so existing behaviour is unchanged
    # until the user explicitly enables a constraint on the Settings screen.
    DEFAULTS = {
        "mandatory_spacing":   {"enabled": False, "k": 1},
        "general_spacing":     {"enabled": False, "k": 1},
        "elective_collisions": {"enabled": False, "k": 0},
        "mandatory_window":    {"enabled": False, "k": 1},
        "daily_capacity":      {"enabled": False, "k": 1},
        "moed_spacing":        {"enabled": False, "k": 1},
    }

    # k for these constraints must be a strictly positive integer; for
    # "elective_collisions" k is allowed to be zero (non-negative).
    POSITIVE_K = {
        "mandatory_spacing",
        "general_spacing",
        "mandatory_window",
        "daily_capacity",
        "moed_spacing",
    }

    def __init__(self, config=None):
        config = config or {}
        self.config = {}
        for key in self.KEYS:
            default = self.DEFAULTS[key]
            given = config.get(key, {}) or {}

            try:
                k = int(given.get("k", default["k"]))
            except (TypeError, ValueError):
                k = default["k"]

            # Clamp k to its valid lower bound depending on the constraint type.
            min_k = 1 if key in self.POSITIVE_K else 0
            if k < min_k:
                k = min_k

            self.config[key] = {
                "enabled": bool(given.get("enabled", default["enabled"])),
                "k": k,
            }

    # ------------------------------------------------------------------ #
    # Configuration accessors
    # ------------------------------------------------------------------ #
    def enabled(self, key) -> bool:
        return self.config[key]["enabled"]

    def k(self, key) -> int:
        return self.config[key]["k"]

    def any_enabled(self) -> bool:
        return any(c["enabled"] for c in self.config.values())

    def to_dict(self) -> dict:
        """Returns a plain serialisable copy of the configuration."""
        return {key: dict(val) for key, val in self.config.items()}

    @classmethod
    def default_config(cls) -> dict:
        """Returns a fresh mutable copy of the default configuration dict."""
        return {key: dict(val) for key, val in cls.DEFAULTS.items()}

    # ------------------------------------------------------------------ #
    # Validation entry point
    # ------------------------------------------------------------------ #
    def is_satisfied_by(self, schedule) -> bool:
        """
        Returns True if the given Schedule satisfies every ACTIVE constraint.
        Disabled constraints are ignored. When no constraint is active the
        schedule is always accepted (fast path).
        """
        if not self.any_enabled():
            return True

        records = self._extract_records(schedule)

        if self.enabled("mandatory_spacing"):
            if not self._check_spacing(records, self.k("mandatory_spacing"), mandatory_only=True):
                return False

        if self.enabled("general_spacing"):
            if not self._check_spacing(records, self.k("general_spacing"), mandatory_only=False):
                return False

        if self.enabled("elective_collisions"):
            if not self._check_elective_collisions(records, self.k("elective_collisions")):
                return False

        if self.enabled("mandatory_window"):
            if not self._check_mandatory_window(records, self.k("mandatory_window")):
                return False

        if self.enabled("daily_capacity"):
            if not self._check_daily_capacity(schedule, self.k("daily_capacity")):
                return False

        if self.enabled("moed_spacing"):
            if not self._check_moed_spacing(schedule, self.k("moed_spacing")):
                return False

        return True

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _day_of(exam_date):
        """Returns the calendar 'date' object for an assigned ExamDate."""
        raw = exam_date.date
        return raw.date() if hasattr(raw, "date") else raw

    @classmethod
    def _extract_records(cls, schedule):
        """
        Flattens a Schedule into one record per (assignment, program membership).

        Each record carries the program/year/requirement context together with
        the assigned calendar day, which is everything the per-program checks
        need.
        """
        records = []
        for (course, moed), exam_date in schedule.assignments.items():
            day = cls._day_of(exam_date)
            for prog in course.programs:
                records.append(
                    {
                        "course_id": course.course_id,
                        "program_id": prog.program_id,
                        "year": prog.year,
                        "requirement": prog.requirement,
                        "moed": moed,
                        "day": day,
                    }
                )
        return records

    @staticmethod
    def _check_spacing(records, k, mandatory_only):
        """
        Generic spacing check used by both the Mandatory and General spacing
        constraints. For every pair of distinct courses that share the same
        (program_id, year), the gap in calendar days must be >= k.

        When mandatory_only is True only Obligatory memberships participate.
        """
        groups = {}
        for r in records:
            if mandatory_only and r["requirement"] != "Obligatory":
                continue
            groups.setdefault((r["program_id"], r["year"]), []).append(r)

        for group in groups.values():
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    if a["course_id"] == b["course_id"]:
                        continue
                    gap = abs((a["day"] - b["day"]).days)
                    if gap < k:
                        return False
        return True

    @staticmethod
    def _check_elective_collisions(records, k):
        """
        Counts collisions (two exams on the exact same day) between any two
        Elective courses inside the same study program. The total number of
        such collisions across all programs must be <= k.
        """
        by_program = {}
        for r in records:
            if r["requirement"] != "Elective":
                continue
            by_program.setdefault(r["program_id"], []).append(r)

        total = 0
        for group in by_program.values():
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    if a["course_id"] == b["course_id"]:
                        continue
                    if a["day"] == b["day"]:
                        total += 1
                        if total > k:
                            return False
        return total <= k

    @staticmethod
    def _check_mandatory_window(records, k):
        """
        For each (program_id, year, moed) the gap in calendar days between the
        first and last Obligatory exam must be >= k. Groups with fewer than two
        mandatory exams have no meaningful window and are skipped.
        """
        groups = {}
        for r in records:
            if r["requirement"] != "Obligatory":
                continue
            groups.setdefault((r["program_id"], r["year"], r["moed"]), []).append(r["day"])

        for days in groups.values():
            if len(days) < 2:
                continue
            span = (max(days) - min(days)).days
            if span < k:
                return False
        return True

    @classmethod
    def _check_daily_capacity(cls, schedule, k):
        """
        The number of exams scheduled on any single calendar day (across the
        whole schedule) must be <= k.
        """
        counts = {}
        for (course, moed), exam_date in schedule.assignments.items():
            day = cls._day_of(exam_date)
            counts[day] = counts.get(day, 0) + 1
            if counts[day] > k:
                return False
        return True

    @classmethod
    def _check_moed_spacing(cls, schedule, k):
        """
        For any course that has BOTH a Moed Aleph and a Moed Bet exam in this
        schedule, the gap in calendar days between the two must be >= k. Courses
        present in only one moed are ignored (nothing to space).

        Note: the core engine generates each moed independently, so a single-moed
        Schedule never trips this check. It applies to combined schedules and is
        enforced interactively in the reschedule editor via companion dates.
        """
        by_course = {}
        for (course, moed), exam_date in schedule.assignments.items():
            by_course.setdefault(course.course_id, {})[moed] = cls._day_of(exam_date)

        for moeds in by_course.values():
            if "Aleph" in moeds and "Bet" in moeds:
                gap = abs((moeds["Aleph"] - moeds["Bet"]).days)
                if gap < k:
                    return False
        return True
