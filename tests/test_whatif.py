import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime
from src.models import Course, Program, Schedule, ExamDate, SchedulingConstraints
from src.scheduler.whatif import WhatIfEngine, ConstraintEvaluator, Move, ScheduleState


def _course(cid, name, program_id, year, requirement):
    return Course(name, cid, "Dr", [Program(program_id, year, "FALL", requirement)], "Exam")


def _dates(days):
    return [ExamDate(datetime(2026, 2, d), "FALL", "Aleph") for d in days]


class TestConstraintEvaluator(unittest.TestCase):
    def setUp(self):
        self.cons = SchedulingConstraints(
            {"mandatory_spacing": {"enabled": True, "k": 2}}
        )
        self.eval = ConstraintEvaluator(self.cons)

    def test_baseline_clash_detected(self):
        a = _course("1", "Algo", "P", 1, "Obligatory")
        b = _course("2", "OS", "P", 1, "Obligatory")
        s = Schedule()
        d = ExamDate(datetime(2026, 2, 1), "FALL", "Aleph")
        s.add_assignment(a, "Aleph", d)
        s.add_assignment(b, "Aleph", d)
        report = self.eval.evaluate(s)
        self.assertFalse(report.is_legal)
        kinds = {v.kind for v in report.violations}
        self.assertIn("baseline", kinds)
        self.assertIn("mandatory_spacing", kinds)

    def test_elective_collision_is_info_not_illegal(self):
        a = _course("1", "Ele A", "P", 1, "Elective")
        b = _course("2", "Ele B", "P", 1, "Elective")
        s = Schedule()
        d = ExamDate(datetime(2026, 2, 1), "FALL", "Aleph")
        s.add_assignment(a, "Aleph", d)
        s.add_assignment(b, "Aleph", d)
        report = self.eval.evaluate(s)
        self.assertTrue(report.is_legal)            # collisions don't break legality here
        self.assertEqual(len(report.collisions), 1) # but they are reported

    def test_legal_schedule_has_no_violations(self):
        a = _course("1", "Algo", "P", 1, "Obligatory")
        b = _course("2", "OS", "P", 1, "Obligatory")
        s = Schedule()
        s.add_assignment(a, "Aleph", ExamDate(datetime(2026, 2, 1), "FALL", "Aleph"))
        s.add_assignment(b, "Aleph", ExamDate(datetime(2026, 2, 4), "FALL", "Aleph"))
        self.assertTrue(self.eval.evaluate(s).is_legal)


class TestWhatIfEngine(unittest.TestCase):
    def setUp(self):
        self.a = _course("1", "Algo", "P", 1, "Obligatory")
        self.b = _course("2", "OS", "P", 1, "Obligatory")
        self.available = _dates([1, 2, 3, 4, 5])
        self.schedule = Schedule()
        self.schedule.add_assignment(self.a, "Aleph", self.available[0])  # 01-Feb
        self.schedule.add_assignment(self.b, "Aleph", self.available[3])  # 04-Feb
        self.cons = SchedulingConstraints({"mandatory_spacing": {"enabled": True, "k": 2}})

    def _engine(self):
        return WhatIfEngine(self.schedule, self.available, "Aleph", self.cons)

    def test_preview_reports_violation_on_clash(self):
        report = self._engine().preview("1", "2026-02-04")  # Algo onto OS day
        self.assertFalse(report.is_legal)

    def test_resolve_finds_minimal_cascade(self):
        res = self._engine().resolve("1", "2026-02-04")
        self.assertTrue(res["solved"])
        self.assertEqual(len(res["plan"]), 1)        # one move is minimal
        self.assertTrue(res["after"]["legal"])
        # The dragged exam (Algo) is pinned, so the cascade must move OS, not Algo.
        self.assertEqual(res["plan"][0]["course_id"], "2")

    def test_resolve_legal_move_needs_no_cascade(self):
        res = self._engine().resolve("1", "2026-02-02")  # still 2 days from OS@04
        self.assertTrue(res["solved"])
        self.assertEqual(len(res["plan"]), 0)

    def test_apply_mutates_schedule_to_legal_state(self):
        engine = self._engine()
        engine.apply("1", "2026-02-04", self.schedule)
        # After applying, the live schedule must be legal again.
        report = ConstraintEvaluator(self.cons).evaluate(self.schedule)
        self.assertTrue(report.is_legal)

    def test_unknown_date_raises(self):
        with self.assertRaises(ValueError):
            self._engine().preview("1", "2026-12-25")


class TestScheduleState(unittest.TestCase):
    def test_with_move_is_immutable_and_hashable(self):
        s = ScheduleState(frozenset({(("1", "Aleph"), 0)}), frozenset())
        s2 = s.with_move(Move("1", "Aleph", 0, 3))
        self.assertEqual(s.as_map()[("1", "Aleph")], 0)   # original unchanged
        self.assertEqual(s2.as_map()[("1", "Aleph")], 3)
        self.assertNotEqual(s.signature(), s2.signature())
        {s, s2}  # must be hashable for the visited-set


if __name__ == "__main__":
    unittest.main()
