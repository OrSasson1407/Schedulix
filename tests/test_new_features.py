import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime, date
from src.models import Course, Program, Schedule, ExamDate, SchedulingConstraints
from src.scheduler.whatif import WhatIfEngine, ConstraintEvaluator


def _course(cid, name, program_id, year, requirement):
    return Course(name, cid, "Dr", [Program(program_id, year, "FALL", requirement)], "Exam")


class TestMoedSpacingConstraint(unittest.TestCase):
    """Feature 1: Moed A <-> Moed B minimum spacing (model level)."""

    def _combined(self, aleph_day, bet_day):
        c = _course("1", "Algo", "P", 1, "Obligatory")
        s = Schedule()
        s.add_assignment(c, "Aleph", ExamDate(datetime(2026, 2, aleph_day), "FALL", "Aleph"))
        s.add_assignment(c, "Bet", ExamDate(datetime(2026, 2, bet_day), "FALL", "Bet"))
        return s

    def test_default_config_includes_moed_spacing(self):
        cfg = SchedulingConstraints.default_config()
        self.assertIn("moed_spacing", cfg)

    def test_too_close_is_disqualified(self):
        cons = SchedulingConstraints({"moed_spacing": {"enabled": True, "k": 10}})
        self.assertFalse(cons.is_satisfied_by(self._combined(1, 5)))  # 4 days < 10

    def test_far_enough_is_allowed(self):
        cons = SchedulingConstraints({"moed_spacing": {"enabled": True, "k": 10}})
        self.assertTrue(cons.is_satisfied_by(self._combined(1, 20)))  # 19 days >= 10

    def test_disabled_never_disqualifies(self):
        cons = SchedulingConstraints({"moed_spacing": {"enabled": False, "k": 10}})
        self.assertTrue(cons.is_satisfied_by(self._combined(1, 2)))

    def test_single_moed_schedule_is_noop(self):
        cons = SchedulingConstraints({"moed_spacing": {"enabled": True, "k": 30}})
        c = _course("1", "Algo", "P", 1, "Obligatory")
        s = Schedule()
        s.add_assignment(c, "Aleph", ExamDate(datetime(2026, 2, 1), "FALL", "Aleph"))
        self.assertTrue(cons.is_satisfied_by(s))


class TestMoedSpacingWhatIf(unittest.TestCase):
    """Feature 1: enforced interactively via companion dates while editing one moed."""

    def setUp(self):
        self.c = _course("1", "Algo", "P", 1, "Obligatory")
        self.available = [ExamDate(datetime(2026, 2, d), "FALL", "Aleph") for d in range(1, 21)]
        self.schedule = Schedule()
        self.schedule.add_assignment(self.c, "Aleph", self.available[14])  # 15-Feb
        self.cons = SchedulingConstraints({"moed_spacing": {"enabled": True, "k": 7}})

    def test_companion_too_close_flags_violation(self):
        # Bet exam fixed at 18-Feb; moving Aleph to 15-Feb leaves only 3 days < 7.
        engine = WhatIfEngine(
            self.schedule, self.available, "Aleph", self.cons,
            companion_dates={"1": date(2026, 2, 18)},
        )
        report = engine.preview("1", "2026-02-15")
        self.assertIn("moed_spacing", {v.kind for v in report.violations})

    def test_no_companion_means_no_moed_check(self):
        engine = WhatIfEngine(self.schedule, self.available, "Aleph", self.cons)
        report = engine.preview("1", "2026-02-15")
        self.assertNotIn("moed_spacing", {v.kind for v in report.violations})


class TestExamLocking(unittest.TestCase):
    """Feature 2: locked exams cannot be dragged and are never moved by a cascade."""

    def setUp(self):
        self.a = _course("1", "Algo", "P", 1, "Obligatory")
        self.b = _course("2", "OS", "P", 1, "Obligatory")
        self.available = [ExamDate(datetime(2026, 2, d), "FALL", "Aleph") for d in range(1, 6)]
        self.schedule = Schedule()
        self.schedule.add_assignment(self.a, "Aleph", self.available[0])  # 01-Feb
        self.schedule.add_assignment(self.b, "Aleph", self.available[3])  # 04-Feb
        self.cons = SchedulingConstraints({"mandatory_spacing": {"enabled": True, "k": 2}})

    def test_moving_a_locked_exam_is_rejected(self):
        engine = WhatIfEngine(self.schedule, self.available, "Aleph", self.cons, locked={"1"})
        with self.assertRaises(ValueError):
            engine.resolve("1", "2026-02-04")

    def test_locked_exam_is_not_used_by_cascade(self):
        # Lock OS(2). Dragging Algo onto OS's day must NOT be solvable by moving OS.
        engine = WhatIfEngine(self.schedule, self.available, "Aleph", self.cons, locked={"2"})
        res = engine.resolve("1", "2026-02-04")
        moved = {m["course_id"] for m in res["plan"]}
        self.assertNotIn("2", moved)


if __name__ == "__main__":
    unittest.main()