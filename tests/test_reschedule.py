import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime
from src.models import Course, Program, Schedule, ExamDate, SchedulingConstraints
from src.scheduler.reschedule.ConstraintEvaluator import ConstraintEvaluator
from src.scheduler.reschedule.RescheduleEngine import RescheduleEngine
from src.scheduler.reschedule.CascadeResolver import CascadeResolver
from src.scheduler.reschedule.Move import Move
from src.scheduler.reschedule.ScheduleState import ScheduleState
from src.scheduler.reschedule.Violation import Violation, ViolationReport

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


class TestRescheduleEngine(unittest.TestCase):
    def setUp(self):
        self.a = _course("1", "Algo", "P", 1, "Obligatory")
        self.b = _course("2", "OS", "P", 1, "Obligatory")
        self.available = _dates([1, 2, 3, 4, 5])
        self.schedule = Schedule()
        self.schedule.add_assignment(self.a, "Aleph", self.available[0])  # 01-Feb
        self.schedule.add_assignment(self.b, "Aleph", self.available[3])  # 04-Feb
        self.cons = SchedulingConstraints({"mandatory_spacing": {"enabled": True, "k": 2}})

    def _engine(self):
        return RescheduleEngine(self.schedule, self.available, "Aleph", self.cons)

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


class TestConstraintEvaluatorExtended(unittest.TestCase):
    """Cover every hard-constraint branch in ConstraintEvaluator."""

    def _schedule(self, assignments):
        s = Schedule()
        for course, moed, day in assignments:
            s.add_assignment(course, moed, ExamDate(datetime(2026, 2, day), "FALL", moed))
        return s

    def test_general_spacing_violation(self):
        a = _course("1", "Algo", "P", 1, "Elective")
        b = _course("2", "DB", "P", 1, "Elective")
        s = self._schedule([(a, "Aleph", 1), (b, "Aleph", 2)])
        cons = SchedulingConstraints({"general_spacing": {"enabled": True, "k": 3}})
        report = ConstraintEvaluator(cons).evaluate(s)
        kinds = {v.kind for v in report.violations}
        self.assertIn("general_spacing", kinds)

    def test_mandatory_window_violation(self):
        a = _course("1", "Algo", "P", 1, "Obligatory")
        b = _course("2", "OS", "P", 1, "Obligatory")
        s = self._schedule([(a, "Aleph", 1), (b, "Aleph", 3)])
        cons = SchedulingConstraints({"mandatory_window": {"enabled": True, "k": 5}})
        report = ConstraintEvaluator(cons).evaluate(s)
        self.assertIn("mandatory_window", {v.kind for v in report.violations})

    def test_daily_capacity_violation(self):
        courses = [_course(str(i), f"C{i}", "P", 1, "Obligatory") for i in range(1, 4)]
        s = Schedule()
        d = ExamDate(datetime(2026, 2, 1), "FALL", "Aleph")
        for c in courses:
            s.add_assignment(c, "Aleph", d)
        cons = SchedulingConstraints({"daily_capacity": {"enabled": True, "k": 2}})
        report = ConstraintEvaluator(cons).evaluate(s)
        self.assertIn("daily_capacity", {v.kind for v in report.violations})

    def test_elective_collisions_exceed_limit_becomes_hard(self):
        a = _course("1", "Ele A", "P", 1, "Elective")
        b = _course("2", "Ele B", "P", 1, "Elective")
        c = _course("3", "Ele C", "P", 1, "Elective")
        s = Schedule()
        d = ExamDate(datetime(2026, 2, 1), "FALL", "Aleph")
        for course in (a, b, c):
            s.add_assignment(course, "Aleph", d)
        cons = SchedulingConstraints({"elective_collisions": {"enabled": True, "k": 1}})
        report = ConstraintEvaluator(cons).evaluate(s)
        self.assertFalse(report.is_legal)
        self.assertIn("elective_collisions", {v.kind for v in report.violations})

    def test_null_constraints_still_checks_baseline(self):
        a = _course("1", "Algo", "P", 1, "Obligatory")
        b = _course("2", "OS", "P", 1, "Obligatory")
        s = Schedule()
        d = ExamDate(datetime(2026, 2, 1), "FALL", "Aleph")
        s.add_assignment(a, "Aleph", d)
        s.add_assignment(b, "Aleph", d)
        report = ConstraintEvaluator(None).evaluate(s)
        self.assertFalse(report.is_legal)


class TestViolationReport(unittest.TestCase):
    def test_components_groups_linked_violations(self):
        report = ViolationReport(violations=[
            Violation("baseline", "a-b", ("1", "2")),
            Violation("mandatory_spacing", "b-c", ("2", "3")),
            Violation("daily_capacity", "d-e", ("4", "5")),
        ])
        self.assertEqual(len(report.components()), 2)
        self.assertEqual(report.involved_courses(), {"1", "2", "3", "4", "5"})

    def test_to_dict_serialises_legal_flag(self):
        report = ViolationReport()
        self.assertTrue(report.to_dict()["legal"])


class TestMove(unittest.TestCase):
    def test_inverse_swaps_ordinals(self):
        mv = Move("1", "Aleph", 2, 5)
        inv = mv.inverse()
        self.assertEqual(inv.from_ordinal, 5)
        self.assertEqual(inv.to_ordinal, 2)


class TestCascadeResolver(unittest.TestCase):
    def test_returns_empty_plan_when_already_legal(self):
        state = ScheduleState(frozenset({(("1", "Aleph"), 0)}), frozenset())
        resolver = CascadeResolver()
        plan = resolver.resolve(state, lambda _s: ViolationReport(), lambda _s, _r: [])
        self.assertEqual(plan, [])

    def test_returns_none_when_unsolvable_within_depth(self):
        state = ScheduleState(frozenset({(("1", "Aleph"), 0)}), frozenset())
        illegal = ViolationReport(violations=[
            Violation("baseline", "clash", ("1", "2")),
        ])

        def evaluate(_s):
            return illegal

        def successors(_s, _r):
            yield Move("2", "Aleph", 1, 2)

        resolver = CascadeResolver(max_cascade=1, time_budget_ms=50)
        self.assertIsNone(resolver.resolve(state, evaluate, successors))


class TestRescheduleEngineExtended(unittest.TestCase):
    def setUp(self):
        self.a = _course("1", "Algo", "P", 1, "Obligatory")
        self.b = _course("2", "OS", "P", 1, "Obligatory")
        self.available = _dates([1, 2, 3, 4, 5])
        self.schedule = Schedule()
        self.schedule.add_assignment(self.a, "Aleph", self.available[0])
        self.schedule.add_assignment(self.b, "Aleph", self.available[3])
        self.cons = SchedulingConstraints({"mandatory_spacing": {"enabled": True, "k": 2}})

    def test_unknown_exam_raises(self):
        engine = RescheduleEngine(self.schedule, self.available, "Aleph", self.cons)
        with self.assertRaises(ValueError):
            engine.preview("999", "2026-02-02")

    def test_unsolvable_cascade_returns_solved_false(self):
        # Lock OS so dragging Algo onto OS's day cannot be fixed by moving OS.
        engine = RescheduleEngine(
            self.schedule, self.available, "Aleph", self.cons, locked={"2"},
        )
        res = engine.resolve("1", "2026-02-04")
        self.assertFalse(res["solved"])

    def test_apply_without_cascade_still_mutates(self):
        engine = RescheduleEngine(self.schedule, self.available, "Aleph", self.cons)
        result = engine.apply("1", "2026-02-02", self.schedule)
        self.assertTrue(result["ok"])
        self.assertEqual(result["forced_move"]["to_date"], "2026-02-02")


if __name__ == "__main__":
    unittest.main()
