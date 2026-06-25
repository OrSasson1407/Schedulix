"""
test_constraints.py
Full coverage for src/models/Constraints.py (SchedulingConstraints).

SchedulingConstraints holds the five user-configurable HARD constraints. Any
schedule that violates an ACTIVE constraint is rejected (is_satisfied_by ->
False). These tests cover configuration parsing/clamping, the accessors, the
serialisation helpers, the day/record helpers, every individual constraint
check, and combinations of multiple active constraints.
"""
import unittest
import sys
import os
from datetime import datetime, date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models import Course, Program, Schedule, ExamDate
from src.models.Constraints import SchedulingConstraints


# --------------------------------------------------------------------------- #
# Small builders so every test reads as "what data" -> "is it satisfied".
# --------------------------------------------------------------------------- #
def _prog(program_id="P1", year=1, semester="FALL", requirement="Obligatory"):
    """Creates a single Program membership."""
    return Program(program_id, year, semester, requirement)


def _course(course_id, programs):
    """Creates an exam Course with the given program memberships."""
    return Course(f"Course {course_id}", course_id, "Instr", programs, "Exam")


def _exam(day, semester="FALL", moed="Aleph"):
    """Builds an ExamDate on a January 2026 day (day is the day-of-month int)."""
    return ExamDate(datetime(2026, 1, day), semester, moed)


def _schedule(items):
    """
    Builds a Schedule from a list of (course, moed, day) tuples.
    'day' is the January 2026 day-of-month used for the exam date.
    """
    s = Schedule()
    for course, moed, day in items:
        s.add_assignment(course, moed, _exam(day))
    return s


def _one(key, k, **kw):
    """Builds a config that enables exactly ONE constraint with parameter k."""
    cfg = {key: {"enabled": True, "k": k}}
    cfg.update(kw)
    return SchedulingConstraints(cfg)


class TestConfigDefaults(unittest.TestCase):
    """An empty/omitted config must produce the safe, all-disabled defaults."""

    def test_empty_config_disables_everything(self):
        # With nothing configured, no constraint is active.
        c = SchedulingConstraints()
        self.assertFalse(c.any_enabled())

    def test_none_config_behaves_like_empty(self):
        # Passing None must not crash and yields the defaults.
        c = SchedulingConstraints(None)
        for key in SchedulingConstraints.KEYS:
            self.assertFalse(c.enabled(key))

    def test_all_keys_present(self):
        # Every known key is materialised in the config.
        c = SchedulingConstraints()
        self.assertEqual(set(c.config.keys()), set(SchedulingConstraints.KEYS))

    def test_default_k_values(self):
        # Defaults: positive-k constraints start at 1, elective_collisions at 0.
        c = SchedulingConstraints()
        self.assertEqual(c.k("mandatory_spacing"), 1)
        self.assertEqual(c.k("elective_collisions"), 0)


class TestConfigParsingAndClamping(unittest.TestCase):
    """k must be coerced to int and clamped to each constraint's lower bound."""

    def test_partial_config_keeps_other_defaults(self):
        # Configuring one key leaves the rest at their defaults (disabled).
        c = SchedulingConstraints({"daily_capacity": {"enabled": True, "k": 3}})
        self.assertTrue(c.enabled("daily_capacity"))
        self.assertFalse(c.enabled("mandatory_spacing"))

    def test_enabled_is_cast_to_bool(self):
        # Truthy/falsy values are normalised to real booleans.
        c = SchedulingConstraints({"daily_capacity": {"enabled": 1, "k": 2}})
        self.assertIs(c.enabled("daily_capacity"), True)

    def test_k_string_is_coerced_to_int(self):
        # A numeric string is accepted and converted.
        c = SchedulingConstraints({"daily_capacity": {"enabled": True, "k": "4"}})
        self.assertEqual(c.k("daily_capacity"), 4)

    def test_invalid_k_falls_back_to_default(self):
        # A non-numeric k falls back to the constraint's default value.
        c = SchedulingConstraints({"mandatory_spacing": {"enabled": True, "k": "abc"}})
        self.assertEqual(c.k("mandatory_spacing"), 1)

    def test_positive_k_clamped_to_one(self):
        # Positive-k constraints cannot go below 1.
        c = SchedulingConstraints({"mandatory_spacing": {"enabled": True, "k": -5}})
        self.assertEqual(c.k("mandatory_spacing"), 1)

    def test_elective_k_clamped_to_zero(self):
        # elective_collisions allows 0 but not negatives.
        c = SchedulingConstraints({"elective_collisions": {"enabled": True, "k": -3}})
        self.assertEqual(c.k("elective_collisions"), 0)

    def test_elective_k_zero_is_allowed(self):
        # Zero is a valid value for elective_collisions (no collisions allowed).
        c = SchedulingConstraints({"elective_collisions": {"enabled": True, "k": 0}})
        self.assertEqual(c.k("elective_collisions"), 0)


class TestAccessorsAndSerialisation(unittest.TestCase):
    """enabled / k / any_enabled / to_dict / default_config behaviour."""

    def test_any_enabled_true_when_one_active(self):
        c = SchedulingConstraints({"daily_capacity": {"enabled": True, "k": 1}})
        self.assertTrue(c.any_enabled())

    def test_to_dict_round_trips(self):
        # to_dict produces a config that rebuilds an equivalent instance.
        original = SchedulingConstraints({"daily_capacity": {"enabled": True, "k": 3}})
        rebuilt = SchedulingConstraints(original.to_dict())
        self.assertEqual(rebuilt.to_dict(), original.to_dict())

    def test_to_dict_is_a_copy(self):
        # Mutating the returned dict must not affect the instance's internal state.
        c = SchedulingConstraints({"daily_capacity": {"enabled": True, "k": 3}})
        snapshot = c.to_dict()
        snapshot["daily_capacity"]["k"] = 999
        self.assertEqual(c.k("daily_capacity"), 3)

    def test_default_config_returns_defaults(self):
        # The classmethod exposes a fresh copy of the documented defaults.
        cfg = SchedulingConstraints.default_config()
        self.assertEqual(set(cfg.keys()), set(SchedulingConstraints.KEYS))
        self.assertFalse(cfg["mandatory_spacing"]["enabled"])

    def test_default_config_is_independent_copy(self):
        # Mutating one returned default config must not leak into another.
        a = SchedulingConstraints.default_config()
        a["mandatory_spacing"]["enabled"] = True
        b = SchedulingConstraints.default_config()
        self.assertFalse(b["mandatory_spacing"]["enabled"])


class TestHelpers(unittest.TestCase):
    """The static/class helpers used by the constraint checks."""

    def test_day_of_datetime(self):
        # datetime-backed dates are normalised to a calendar date.
        exam = ExamDate(datetime(2026, 1, 8, 9, 0), "FALL", "Aleph")
        self.assertEqual(SchedulingConstraints._day_of(exam), date(2026, 1, 8))

    def test_day_of_plain_date(self):
        # date-backed dates are returned unchanged.
        exam = ExamDate(date(2026, 1, 8), "FALL", "Aleph")
        self.assertEqual(SchedulingConstraints._day_of(exam), date(2026, 1, 8))

    def test_extract_records_one_per_program(self):
        # A course in two programs yields two records for its single assignment.
        c1 = _course("C1", [_prog("P1"), _prog("P2")])
        records = SchedulingConstraints._extract_records(_schedule([(c1, "Aleph", 1)]))
        self.assertEqual(len(records), 2)
        self.assertEqual({r["program_id"] for r in records}, {"P1", "P2"})


class TestFastPath(unittest.TestCase):
    """When no constraint is active, every schedule is accepted."""

    def test_no_active_constraint_accepts_any_schedule(self):
        # Even a "bad" schedule passes because nothing is enabled.
        c1 = _course("C1", [_prog("P1")])
        c2 = _course("C2", [_prog("P1")])
        sched = _schedule([(c1, "Aleph", 1), (c2, "Aleph", 1)])
        self.assertTrue(SchedulingConstraints().is_satisfied_by(sched))


class TestMandatorySpacing(unittest.TestCase):
    """Every mandatory pair (same program/year) must be at least k days apart."""

    def test_gap_meets_threshold_passes(self):
        # Days 1 & 3 -> gap 2; k=2 is satisfied (gap >= k).
        prog = "P1"
        c1 = _course("C1", [_prog(prog)])
        c2 = _course("C2", [_prog(prog)])
        sched = _schedule([(c1, "Aleph", 1), (c2, "Aleph", 3)])
        self.assertTrue(_one("mandatory_spacing", 2).is_satisfied_by(sched))

    def test_gap_below_threshold_fails(self):
        # Days 1 & 3 -> gap 2; k=3 fails (gap < k).
        prog = "P1"
        c1 = _course("C1", [_prog(prog)])
        c2 = _course("C2", [_prog(prog)])
        sched = _schedule([(c1, "Aleph", 1), (c2, "Aleph", 3)])
        self.assertFalse(_one("mandatory_spacing", 3).is_satisfied_by(sched))

    def test_electives_do_not_trigger(self):
        # Mandatory spacing ignores electives, so a tight elective pair passes.
        c1 = _course("C1", [_prog("P1", requirement="Elective")])
        c2 = _course("C2", [_prog("P1", requirement="Elective")])
        sched = _schedule([(c1, "Aleph", 1), (c2, "Aleph", 2)])
        self.assertTrue(_one("mandatory_spacing", 5).is_satisfied_by(sched))

    def test_different_programs_independent(self):
        # Tight pair but in different programs -> not compared -> passes.
        c1 = _course("C1", [_prog("P1")])
        c2 = _course("C2", [_prog("P2")])
        sched = _schedule([(c1, "Aleph", 1), (c2, "Aleph", 2)])
        self.assertTrue(_one("mandatory_spacing", 5).is_satisfied_by(sched))


class TestGeneralSpacing(unittest.TestCase):
    """Every pair (any requirement) in the same program/year must be >= k apart."""

    def test_includes_electives(self):
        # Unlike mandatory spacing, electives count -> a tight pair fails.
        c1 = _course("C1", [_prog("P1", requirement="Elective")])
        c2 = _course("C2", [_prog("P1", requirement="Elective")])
        sched = _schedule([(c1, "Aleph", 1), (c2, "Aleph", 2)])
        self.assertFalse(_one("general_spacing", 5).is_satisfied_by(sched))

    def test_adequate_gap_passes(self):
        # Days 1 & 6 -> gap 5; k=5 is satisfied.
        c1 = _course("C1", [_prog("P1", requirement="Elective")])
        c2 = _course("C2", [_prog("P1")])
        sched = _schedule([(c1, "Aleph", 1), (c2, "Aleph", 6)])
        self.assertTrue(_one("general_spacing", 5).is_satisfied_by(sched))


class TestElectiveCollisions(unittest.TestCase):
    """Total same-day elective collisions per program must be <= k."""

    def test_within_budget_passes(self):
        # One collision with k=1 is allowed.
        c1 = _course("C1", [_prog("P1", requirement="Elective")])
        c2 = _course("C2", [_prog("P1", requirement="Elective")])
        sched = _schedule([(c1, "Aleph", 5), (c2, "Aleph", 5)])
        self.assertTrue(_one("elective_collisions", 1).is_satisfied_by(sched))

    def test_over_budget_fails(self):
        # One collision with k=0 (none allowed) fails.
        c1 = _course("C1", [_prog("P1", requirement="Elective")])
        c2 = _course("C2", [_prog("P1", requirement="Elective")])
        sched = _schedule([(c1, "Aleph", 5), (c2, "Aleph", 5)])
        self.assertFalse(_one("elective_collisions", 0).is_satisfied_by(sched))

    def test_obligatory_collision_ignored(self):
        # Only elective-vs-elective collisions count; obligatory clashes are ignored.
        c1 = _course("C1", [_prog("P1")])
        c2 = _course("C2", [_prog("P1")])
        sched = _schedule([(c1, "Aleph", 5), (c2, "Aleph", 5)])
        self.assertTrue(_one("elective_collisions", 0).is_satisfied_by(sched))


class TestMandatoryWindow(unittest.TestCase):
    """First-to-last mandatory span per (program, year, moed) must be >= k."""

    def test_wide_enough_window_passes(self):
        # Days 1 & 10 -> span 9; k=9 is satisfied.
        prog = "P1"
        c1 = _course("C1", [_prog(prog)])
        c2 = _course("C2", [_prog(prog)])
        sched = _schedule([(c1, "Aleph", 1), (c2, "Aleph", 10)])
        self.assertTrue(_one("mandatory_window", 9).is_satisfied_by(sched))

    def test_too_narrow_window_fails(self):
        # Days 1 & 10 -> span 9; k=10 fails.
        prog = "P1"
        c1 = _course("C1", [_prog(prog)])
        c2 = _course("C2", [_prog(prog)])
        sched = _schedule([(c1, "Aleph", 1), (c2, "Aleph", 10)])
        self.assertFalse(_one("mandatory_window", 10).is_satisfied_by(sched))

    def test_single_exam_group_skipped(self):
        # A group with one mandatory exam has no window, so it cannot fail.
        c1 = _course("C1", [_prog("P1")])
        sched = _schedule([(c1, "Aleph", 1)])
        self.assertTrue(_one("mandatory_window", 50).is_satisfied_by(sched))


class TestDailyCapacity(unittest.TestCase):
    """No single day may hold more than k exams (counted across the whole schedule)."""

    def test_within_capacity_passes(self):
        # Two exams on the same day with k=2 is allowed.
        c1 = _course("C1", [_prog("P1")])
        c2 = _course("C2", [_prog("P2")])
        sched = _schedule([(c1, "Aleph", 4), (c2, "Aleph", 4)])
        self.assertTrue(_one("daily_capacity", 2).is_satisfied_by(sched))

    def test_over_capacity_fails(self):
        # Three exams on the same day with k=2 fails.
        c1 = _course("C1", [_prog("P1")])
        c2 = _course("C2", [_prog("P2")])
        c3 = _course("C3", [_prog("P3")])
        sched = _schedule([(c1, "Aleph", 4), (c2, "Aleph", 4), (c3, "Aleph", 4)])
        self.assertFalse(_one("daily_capacity", 2).is_satisfied_by(sched))

    def test_capacity_counts_assignments_not_programs(self):
        # A course in many programs is still ONE exam on the day -> within k=1.
        c1 = _course("C1", [_prog("P1"), _prog("P2"), _prog("P3")])
        sched = _schedule([(c1, "Aleph", 4)])
        self.assertTrue(_one("daily_capacity", 1).is_satisfied_by(sched))


class TestMultipleConstraints(unittest.TestCase):
    """When several constraints are active, ALL must hold for acceptance."""

    def test_disabled_constraint_is_ignored(self):
        # daily_capacity would fail (3 on a day) but it is disabled -> accepted.
        c1 = _course("C1", [_prog("P1")])
        c2 = _course("C2", [_prog("P2")])
        c3 = _course("C3", [_prog("P3")])
        sched = _schedule([(c1, "Aleph", 4), (c2, "Aleph", 4), (c3, "Aleph", 4)])
        cfg = SchedulingConstraints({
            "daily_capacity": {"enabled": False, "k": 1},
            "mandatory_window": {"enabled": True, "k": 1},  # harmless (no >=2 group)
        })
        self.assertTrue(cfg.is_satisfied_by(sched))

    def test_passes_only_when_all_active_constraints_hold(self):
        # mandatory_spacing OK (gap 9) AND daily_capacity OK (max 1/day) -> accepted.
        prog = "P1"
        c1 = _course("C1", [_prog(prog)])
        c2 = _course("C2", [_prog(prog)])
        sched = _schedule([(c1, "Aleph", 1), (c2, "Aleph", 10)])
        cfg = SchedulingConstraints({
            "mandatory_spacing": {"enabled": True, "k": 5},
            "daily_capacity": {"enabled": True, "k": 1},
        })
        self.assertTrue(cfg.is_satisfied_by(sched))

    def test_fails_when_any_active_constraint_violated(self):
        # mandatory_spacing OK (gap 10) but daily_capacity violated elsewhere.
        prog = "P1"
        c1 = _course("C1", [_prog(prog)])
        c2 = _course("C2", [_prog(prog)])
        # Two more courses share a day to break daily_capacity (k=1).
        c3 = _course("C3", [_prog("P9")])
        c4 = _course("C4", [_prog("P8")])
        sched = _schedule([
            (c1, "Aleph", 1), (c2, "Aleph", 11),
            (c3, "Aleph", 5), (c4, "Aleph", 5),
        ])
        cfg = SchedulingConstraints({
            "mandatory_spacing": {"enabled": True, "k": 5},
            "daily_capacity": {"enabled": True, "k": 1},
        })
        self.assertFalse(cfg.is_satisfied_by(sched))


if __name__ == "__main__":
    unittest.main()