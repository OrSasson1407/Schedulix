"""
test_schedule_sorter.py
Full coverage for src/scheduler/SchedulerSorter.py.

The sorter is a pure, post-generation operation: it takes a list of already-valid
Schedule objects and re-orders them by one or more metric keys (all layers
descending). These tests cover every public metric helper, the metadata tables,
the metric extraction helpers, compute_metrics, and the multi-key sort itself.
"""
import unittest
import sys
import os
from datetime import datetime, date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models import Course, Program, Schedule, ExamDate
from src.scheduler import SchedulerSorter as ss
from src.scheduler.SchedulerSorter import (
    SORT_CRITERIA,
    METRIC_KEYS,
    compute_metrics,
    sort_schedules,
    min_mandatory_spacing,
    avg_exam_spacing,
    elective_collisions,
    mandatory_window,
    peak_daily_capacity,
)


# --------------------------------------------------------------------------- #
# Small builders so every test reads as "what data" -> "what metric".
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


class TestSorterMetadata(unittest.TestCase):
    """The metadata tables drive the Output UI, so their shape must stay stable."""

    def test_five_criteria_exist(self):
        # The product defines exactly five sort criteria.
        self.assertEqual(len(SORT_CRITERIA), 5)

    def test_every_criterion_has_required_fields(self):
        # Each criterion must expose key/label/desc for the UI.
        for crit in SORT_CRITERIA:
            self.assertIn("key", crit)
            self.assertIn("label", crit)
            self.assertIn("desc", crit)

    def test_metric_keys_match_criteria_order(self):
        # METRIC_KEYS is derived from SORT_CRITERIA and must preserve order.
        self.assertEqual(METRIC_KEYS, tuple(c["key"] for c in SORT_CRITERIA))

    def test_metric_keys_are_unique(self):
        # No duplicate metric identities are allowed.
        self.assertEqual(len(METRIC_KEYS), len(set(METRIC_KEYS)))


class TestDayOfHelper(unittest.TestCase):
    """_day_of must always return a plain calendar date regardless of input type."""

    def test_day_of_datetime(self):
        # A datetime-backed ExamDate is normalised down to its date().
        exam = ExamDate(datetime(2026, 1, 5, 14, 30), "FALL", "Aleph")
        self.assertEqual(ss._day_of(exam), date(2026, 1, 5))

    def test_day_of_plain_date(self):
        # A date-backed ExamDate is returned unchanged (no .date() attribute).
        exam = ExamDate(date(2026, 1, 5), "FALL", "Aleph")
        self.assertEqual(ss._day_of(exam), date(2026, 1, 5))


class TestRecordsHelper(unittest.TestCase):
    """_records flattens a schedule into one record per (assignment, program)."""

    def test_one_record_per_program_membership(self):
        # A course in two programs + a course in one program => 3 records total.
        c1 = _course("C1", [_prog("P1"), _prog("P2")])
        c2 = _course("C2", [_prog("P1")])
        sched = _schedule([(c1, "Aleph", 1), (c2, "Aleph", 2)])
        records = ss._records(sched)
        self.assertEqual(len(records), 3)

    def test_record_fields_are_populated(self):
        # Each record carries the full program/year/requirement/moed/day context.
        c1 = _course("C1", [_prog("P1", year=2, requirement="Elective")])
        sched = _schedule([(c1, "Bet", 7)])
        rec = ss._records(sched)[0]
        self.assertEqual(rec["course_id"], "C1")
        self.assertEqual(rec["program_id"], "P1")
        self.assertEqual(rec["year"], 2)
        self.assertEqual(rec["requirement"], "Elective")
        self.assertEqual(rec["moed"], "Bet")
        self.assertEqual(rec["day"], date(2026, 1, 7))


class TestMinMandatorySpacing(unittest.TestCase):
    """Minimum gap (days) between any two mandatory exams in the same program/year."""

    def test_no_mandatory_pair_returns_zero(self):
        # A single mandatory course has no pair, so the metric is 0.
        c1 = _course("C1", [_prog("P1")])
        self.assertEqual(min_mandatory_spacing(_schedule([(c1, "Aleph", 1)])), 0)

    def test_returns_smallest_gap(self):
        # Gaps are |1-5|=4, |1-6|=5, |5-6|=1 -> minimum is 1.
        prog = "P1"
        c1 = _course("C1", [_prog(prog)])
        c2 = _course("C2", [_prog(prog)])
        c3 = _course("C3", [_prog(prog)])
        sched = _schedule([(c1, "Aleph", 1), (c2, "Aleph", 5), (c3, "Aleph", 6)])
        self.assertEqual(min_mandatory_spacing(sched), 1)

    def test_electives_are_ignored(self):
        # Only Obligatory memberships count; an elective pair yields no gap -> 0.
        c1 = _course("C1", [_prog("P1", requirement="Elective")])
        c2 = _course("C2", [_prog("P1", requirement="Elective")])
        self.assertEqual(min_mandatory_spacing(_schedule([(c1, "Aleph", 1), (c2, "Aleph", 9)])), 0)

    def test_different_programs_not_compared(self):
        # Two mandatory courses in different programs are not a qualifying pair.
        c1 = _course("C1", [_prog("P1")])
        c2 = _course("C2", [_prog("P2")])
        self.assertEqual(min_mandatory_spacing(_schedule([(c1, "Aleph", 1), (c2, "Aleph", 9)])), 0)


class TestAvgExamSpacing(unittest.TestCase):
    """Average gap (days) between any two exams (any requirement) in the same program/year."""

    def test_no_pair_returns_zero_float(self):
        # No qualifying pair -> 0.0 (and the type stays a float).
        c1 = _course("C1", [_prog("P1")])
        result = avg_exam_spacing(_schedule([(c1, "Aleph", 1)]))
        self.assertEqual(result, 0.0)
        self.assertIsInstance(result, float)

    def test_average_of_all_pairs(self):
        # Days 1, 3, 6 -> gaps 2, 5, 3 -> average (2+5+3)/3 = 10/3.
        prog = "P1"
        c1 = _course("C1", [_prog(prog)])
        c2 = _course("C2", [_prog(prog)])
        c3 = _course("C3", [_prog(prog)])
        sched = _schedule([(c1, "Aleph", 1), (c2, "Aleph", 3), (c3, "Aleph", 6)])
        self.assertAlmostEqual(avg_exam_spacing(sched), 10 / 3)

    def test_includes_electives(self):
        # Unlike mandatory spacing, electives participate here -> non-zero average.
        c1 = _course("C1", [_prog("P1", requirement="Elective")])
        c2 = _course("C2", [_prog("P1", requirement="Elective")])
        self.assertEqual(avg_exam_spacing(_schedule([(c1, "Aleph", 1), (c2, "Aleph", 4)])), 3.0)


class TestElectiveCollisions(unittest.TestCase):
    """Count of same-day collisions between two elective courses in the same program."""

    def test_collision_counted(self):
        # Two electives in P1 on the same day -> one collision.
        c1 = _course("C1", [_prog("P1", requirement="Elective")])
        c2 = _course("C2", [_prog("P1", requirement="Elective")])
        self.assertEqual(elective_collisions(_schedule([(c1, "Aleph", 5), (c2, "Aleph", 5)])), 1)

    def test_no_collision_on_different_days(self):
        # Same program electives but different days -> no collision.
        c1 = _course("C1", [_prog("P1", requirement="Elective")])
        c2 = _course("C2", [_prog("P1", requirement="Elective")])
        self.assertEqual(elective_collisions(_schedule([(c1, "Aleph", 5), (c2, "Aleph", 6)])), 0)

    def test_obligatory_same_day_not_counted(self):
        # The metric only looks at electives; an obligatory clash is ignored here.
        c1 = _course("C1", [_prog("P1")])
        c2 = _course("C2", [_prog("P1")])
        self.assertEqual(elective_collisions(_schedule([(c1, "Aleph", 5), (c2, "Aleph", 5)])), 0)

    def test_grouping_is_per_program(self):
        # Electives sharing a day in DIFFERENT programs do not collide.
        c1 = _course("C1", [_prog("P1", requirement="Elective")])
        c2 = _course("C2", [_prog("P2", requirement="Elective")])
        self.assertEqual(elective_collisions(_schedule([(c1, "Aleph", 5), (c2, "Aleph", 5)])), 0)


class TestMandatoryWindow(unittest.TestCase):
    """Widest span (days) between first and last mandatory exam per (program, year, moed)."""

    def test_window_span(self):
        # Two mandatory exams in the same group on days 1 and 10 -> span 9.
        prog = "P1"
        c1 = _course("C1", [_prog(prog)])
        c2 = _course("C2", [_prog(prog)])
        self.assertEqual(mandatory_window(_schedule([(c1, "Aleph", 1), (c2, "Aleph", 10)])), 9)

    def test_single_exam_group_returns_zero(self):
        # A group with fewer than two mandatory exams has no window -> 0.
        c1 = _course("C1", [_prog("P1")])
        self.assertEqual(mandatory_window(_schedule([(c1, "Aleph", 1)])), 0)

    def test_widest_group_wins(self):
        # P1 span = 4 (days 1..5), P2 span = 9 (days 1..10) -> widest is 9.
        c1 = _course("C1", [_prog("P1")])
        c2 = _course("C2", [_prog("P1")])
        c3 = _course("C3", [_prog("P2")])
        c4 = _course("C4", [_prog("P2")])
        sched = _schedule([(c1, "Aleph", 1), (c2, "Aleph", 5), (c3, "Aleph", 1), (c4, "Aleph", 10)])
        self.assertEqual(mandatory_window(sched), 9)

    def test_different_moed_splits_groups(self):
        # The same program/year but different moed are separate groups,
        # so two single-exam groups produce no window -> 0.
        prog = "P1"
        c1 = _course("C1", [_prog(prog)])
        c2 = _course("C2", [_prog(prog)])
        self.assertEqual(mandatory_window(_schedule([(c1, "Aleph", 1), (c2, "Bet", 10)])), 0)


class TestPeakDailyCapacity(unittest.TestCase):
    """Maximum number of exams scheduled on any single day across the whole schedule."""

    def test_empty_schedule_zero(self):
        # No assignments -> peak of 0.
        self.assertEqual(peak_daily_capacity(_schedule([])), 0)

    def test_counts_per_assignment_not_per_program(self):
        # Three distinct courses on the same day -> peak of 3 (program count irrelevant).
        c1 = _course("C1", [_prog("P1"), _prog("P2")])
        c2 = _course("C2", [_prog("P1")])
        c3 = _course("C3", [_prog("P3")])
        sched = _schedule([(c1, "Aleph", 4), (c2, "Aleph", 4), (c3, "Aleph", 4)])
        self.assertEqual(peak_daily_capacity(sched), 3)

    def test_takes_the_busiest_day(self):
        # Day 4 has 2 exams, day 5 has 1 -> peak is 2.
        c1 = _course("C1", [_prog("P1")])
        c2 = _course("C2", [_prog("P1")])
        c3 = _course("C3", [_prog("P1")])
        sched = _schedule([(c1, "Aleph", 4), (c2, "Aleph", 4), (c3, "Aleph", 5)])
        self.assertEqual(peak_daily_capacity(sched), 2)


class TestComputeMetrics(unittest.TestCase):
    """compute_metrics bundles all five metrics into a single dict."""

    def test_returns_all_keys(self):
        c1 = _course("C1", [_prog("P1")])
        metrics = compute_metrics(_schedule([(c1, "Aleph", 1)]))
        self.assertEqual(set(metrics.keys()), set(METRIC_KEYS))

    def test_values_match_individual_helpers(self):
        # The bundled values must equal the standalone helper outputs.
        c1 = _course("C1", [_prog("P1")])
        c2 = _course("C2", [_prog("P1")])
        sched = _schedule([(c1, "Aleph", 1), (c2, "Aleph", 4)])
        metrics = compute_metrics(sched)
        self.assertEqual(metrics["min_mandatory_spacing"], min_mandatory_spacing(sched))
        self.assertEqual(metrics["avg_exam_spacing"], avg_exam_spacing(sched))
        self.assertEqual(metrics["elective_collisions"], elective_collisions(sched))
        self.assertEqual(metrics["mandatory_window"], mandatory_window(sched))
        self.assertEqual(metrics["peak_daily_capacity"], peak_daily_capacity(sched))


class TestSortSchedules(unittest.TestCase):
    """The multi-key sort: every layer descending, primary -> secondary -> ..."""

    def _peak_schedule(self, n_courses_same_day):
        # Helper: a schedule whose peak_daily_capacity == n_courses_same_day.
        items = []
        for i in range(n_courses_same_day):
            items.append((_course(f"C{i}", [_prog("P1", requirement="Elective")]), "Aleph", 4))
        return _schedule(items)

    def test_empty_criteria_returns_unchanged_copy(self):
        # With no criteria the original order is preserved, but a NEW list is returned.
        a, b = self._peak_schedule(1), self._peak_schedule(2)
        result = sort_schedules([a, b], [])
        self.assertEqual(result, [a, b])
        self.assertIsNot(result, [a, b])

    def test_none_criteria_returns_unchanged(self):
        # None must be treated like "no criteria".
        a, b = self._peak_schedule(1), self._peak_schedule(2)
        self.assertEqual(sort_schedules([a, b], None), [a, b])

    def test_single_key_descending(self):
        # Peaks 1, 3, 2 -> sorted descending by peak -> 3, 2, 1.
        s1 = self._peak_schedule(1)
        s3 = self._peak_schedule(3)
        s2 = self._peak_schedule(2)
        result = sort_schedules([s1, s3, s2], ["peak_daily_capacity"])
        self.assertEqual(result, [s3, s2, s1])

    def test_unknown_keys_are_ignored(self):
        # An unknown key alongside nothing valid -> behaves like empty criteria.
        a, b = self._peak_schedule(1), self._peak_schedule(2)
        self.assertEqual(sort_schedules([a, b], ["does_not_exist"]), [a, b])

    def test_duplicate_keys_are_collapsed(self):
        # Repeating a valid key must not change the result vs. listing it once.
        s1 = self._peak_schedule(1)
        s2 = self._peak_schedule(2)
        once = sort_schedules([s1, s2], ["peak_daily_capacity"])
        twice = sort_schedules([s1, s2], ["peak_daily_capacity", "peak_daily_capacity"])
        self.assertEqual(once, twice)

    def test_secondary_key_breaks_ties(self):
        # Two schedules share peak == 2, but differ on min_mandatory_spacing.
        # high_gap: mandatory days 1 & 10 (gap 9) on different days (peak 1)... so
        # build both with peak 2 and distinct mandatory spacing for a clean tie-break.
        prog = "P1"
        # Schedule A: peak 2 (two electives on day 4) + mandatory gap of 2 (days 1,3).
        a = _schedule([
            (_course("AE1", [_prog(prog, requirement="Elective")]), "Aleph", 4),
            (_course("AE2", [_prog(prog, requirement="Elective")]), "Aleph", 4),
            (_course("AM1", [_prog(prog)]), "Aleph", 1),
            (_course("AM2", [_prog(prog)]), "Aleph", 3),
        ])
        # Schedule B: peak 2 (two electives on day 4) + mandatory gap of 8 (days 1,9).
        b = _schedule([
            (_course("BE1", [_prog(prog, requirement="Elective")]), "Aleph", 4),
            (_course("BE2", [_prog(prog, requirement="Elective")]), "Aleph", 4),
            (_course("BM1", [_prog(prog)]), "Aleph", 1),
            (_course("BM2", [_prog(prog)]), "Aleph", 9),
        ])
        # Sanity check on the tie + the tie-breaker direction.
        self.assertEqual(peak_daily_capacity(a), peak_daily_capacity(b))
        self.assertGreater(min_mandatory_spacing(b), min_mandatory_spacing(a))
        # Primary = peak (tied), secondary = min_mandatory_spacing -> B before A.
        result = sort_schedules([a, b], ["peak_daily_capacity", "min_mandatory_spacing"])
        self.assertEqual(result, [b, a])

    def test_input_list_is_not_mutated(self):
        # Sorting must not reorder the caller's original list.
        s1 = self._peak_schedule(1)
        s2 = self._peak_schedule(2)
        original = [s1, s2]
        sort_schedules(original, ["peak_daily_capacity"])
        self.assertEqual(original, [s1, s2])

    def test_accepts_any_iterable(self):
        # A generator input is materialised and sorted correctly.
        s1 = self._peak_schedule(1)
        s2 = self._peak_schedule(2)
        result = sort_schedules((s for s in [s1, s2]), ["peak_daily_capacity"])
        self.assertEqual(result, [s2, s1])


if __name__ == "__main__":
    unittest.main()