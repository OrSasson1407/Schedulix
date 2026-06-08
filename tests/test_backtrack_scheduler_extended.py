import unittest
import sys
import os
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scheduler.BacktrackScheduler import BacktrackScheduler, _courses_conflict
from src.models.Course import Course
from src.models.Program import Program
from src.models.ExamPeriod import ExamPeriod
from src.models.Schedule import Schedule


def make_course(cid, prog_id, year="1", semester="FALL", req="Obligatory", evaluation="Exam"):
    p = Program(prog_id, year, semester, req)
    return Course(f"Course {cid}", cid, "Dr. Test", [p], evaluation)

def make_period(start, end, semester="FALL", moed="Aleph", excluded=None):
    return ExamPeriod(semester, moed, start, end, excluded or [])


class TestBacktrackSchedulerExtended(unittest.TestCase):

    def setUp(self):
        self.scheduler = BacktrackScheduler()

    # -------------------------------------------------------------------------
    # 1. 28-second hard deadline — millions of combos, must stop at limit
    # -------------------------------------------------------------------------
    def test_deadline_28_seconds_stops_and_has_millions(self):
        """
        12 fully independent courses over 90 days = 90^12 theoretical combinations.
        Scheduler must:
          - stop within 28.5 seconds
          - have produced millions of schedules before stopping
          - report _time_exceeded = True
        """
        courses = []
        for i in range(12):
            p = Program(f"831{i:02d}", 1, "FALL", "Obligatory")
            courses.append(Course(f"Course {i}", f"C{i:04d}", "Dr. X", [p], "Exam"))

        period = make_period("01-01-2026", "31-03-2026")  # 90 available days

        start = time.time()
        count = sum(1 for _ in self.scheduler.generate(courses, [period]))
        elapsed = time.time() - start

        self.assertLessEqual(elapsed, 28.5,
            f"Scheduler ran {elapsed:.1f}s — exceeded the 28s hard limit")
        self.assertTrue(self.scheduler._time_exceeded,
            "Scheduler should have set _time_exceeded=True on a near-infinite problem")
        self.assertGreater(count, 1_000_000,
            f"Expected millions of schedules before cutoff, got only {count}")

    # -------------------------------------------------------------------------
    # 2. Single course → exactly one schedule per available date
    # -------------------------------------------------------------------------
    def test_single_course_produces_one_schedule_per_date(self):
        """One exam course over N available days → N schedules."""
        c = make_course("10001", "83101")
        period = make_period("01-02-2026", "03-02-2026")  # 3 days
        schedules = list(self.scheduler.generate([c], [period]))
        self.assertEqual(len(schedules), 3)

    # -------------------------------------------------------------------------
    # 3. Two obligatory courses, same program/year — no date collision allowed
    # -------------------------------------------------------------------------
    def test_obligatory_same_program_no_collision(self):
        """All generated schedules must place obligatory same-program courses on different days."""
        p = Program("83101", 1, "FALL", "Obligatory")
        c1 = Course("Math", "10001", "Dr. A", [p], "Exam")
        c2 = Course("Physics", "10002", "Dr. B", [p], "Exam")
        period = make_period("01-02-2026", "05-02-2026")
        schedules = list(self.scheduler.generate([c1, c2], [period]))
        self.assertGreater(len(schedules), 0)
        for s in schedules:
            dates = [ed.date.date() for ed in s.assignments.values()]
            self.assertEqual(len(dates), len(set(dates)), "Obligatory exams share a date")

    # -------------------------------------------------------------------------
    # 4. Two elective courses, same program/year — collision IS allowed
    # -------------------------------------------------------------------------
    def test_elective_same_program_collision_allowed(self):
        """Elective courses in the same program/year may share a date."""
        p = Program("83101", 1, "FALL", "Elective")
        c1 = Course("Elective A", "20001", "Dr. A", [p], "Exam")
        c2 = Course("Elective B", "20002", "Dr. B", [p], "Exam")
        period = make_period("01-02-2026", "01-02-2026")  # only 1 day
        schedules = list(self.scheduler.generate([c1, c2], [period]))
        # With only 1 day and 2 elective courses, there should be exactly 1 valid schedule
        self.assertEqual(len(schedules), 1)

    # -------------------------------------------------------------------------
    # 5. Obligatory + elective same day → invalid
    # -------------------------------------------------------------------------
    def test_obligatory_elective_same_program_same_day_invalid(self):
        """An obligatory and elective course for the same program/year cannot share a date."""
        p_obl = Program("83101", 1, "FALL", "Obligatory")
        p_elc = Program("83101", 1, "FALL", "Elective")
        c1 = Course("Obligatory Math", "30001", "Dr. A", [p_obl], "Exam")
        c2 = Course("Elective Art", "30002", "Dr. B", [p_elc], "Exam")
        period = make_period("01-02-2026", "01-02-2026")  # only 1 day → forced same date
        schedules = list(self.scheduler.generate([c1, c2], [period]))
        self.assertEqual(len(schedules), 0, "Should produce no valid schedule")

    # -------------------------------------------------------------------------
    # 6. Different programs — no conflict, courses may share a date
    # -------------------------------------------------------------------------
    def test_different_programs_no_conflict(self):
        """Courses from entirely different programs have no constraint between them."""
        c1 = make_course("40001", "83101", req="Obligatory")
        c2 = make_course("40002", "83102", req="Obligatory")
        period = make_period("01-02-2026", "01-02-2026")  # 1 day
        schedules = list(self.scheduler.generate([c1, c2], [period]))
        self.assertEqual(len(schedules), 1, "One schedule expected — no conflict between programs")

    # -------------------------------------------------------------------------
    # 7. Different years, same program — no conflict
    # -------------------------------------------------------------------------
    def test_different_years_same_program_no_conflict(self):
        """Year 1 and Year 2 obligatory courses in the same program don't conflict."""
        p1 = Program("83101", 1, "FALL", "Obligatory")
        p2 = Program("83101", 2, "FALL", "Obligatory")
        c1 = Course("Year1 Math", "50001", "Dr. A", [p1], "Exam")
        c2 = Course("Year2 Physics", "50002", "Dr. B", [p2], "Exam")
        period = make_period("01-02-2026", "01-02-2026")
        schedules = list(self.scheduler.generate([c1, c2], [period]))
        self.assertEqual(len(schedules), 1)

    # -------------------------------------------------------------------------
    # 8. Excluded dates are respected
    # -------------------------------------------------------------------------
    def test_excluded_dates_not_used(self):
        """Scheduler must not assign exams to excluded (holiday) dates."""
        excluded_day = datetime(2026, 2, 2)
        period = ExamPeriod("FALL", "Aleph", "01-02-2026", "03-02-2026", [excluded_day])
        c = make_course("60001", "83101")
        schedules = list(self.scheduler.generate([c], [period]))
        for s in schedules:
            for ed in s.assignments.values():
                self.assertNotEqual(ed.date.date(), excluded_day.date(), "Exam on excluded date")
        # Only 2 days available (Feb 1 and Feb 3)
        self.assertEqual(len(schedules), 2)

    # -------------------------------------------------------------------------
    # 9. Correctness: every generated schedule passes Schedule.is_valid()
    # -------------------------------------------------------------------------
    def test_all_schedules_pass_is_valid(self):
        """Every schedule yielded by the scheduler must pass the built-in validator."""
        p = Program("83101", 1, "FALL", "Obligatory")
        courses = [Course(f"C{i}", f"7000{i}", "Dr. X", [p], "Exam") for i in range(1, 5)]
        period = make_period("01-02-2026", "10-02-2026")
        for s in self.scheduler.generate(courses, [period]):
            self.assertTrue(s.is_valid(), "Scheduler yielded an invalid schedule")

    # -------------------------------------------------------------------------
    # 10. Multiple periods — schedules are generated per period
    # -------------------------------------------------------------------------
    def test_multiple_periods_produce_schedules(self):
        """With two separate exam periods, schedules should come from both."""
        p_fall = Program("83101", 1, "FALL", "Obligatory")
        p_spri = Program("83101", 1, "SPRI", "Obligatory")
        c1 = Course("Fall Math", "80001", "Dr. A", [p_fall], "Exam")
        c2 = Course("Spring Physics", "80002", "Dr. B", [p_spri], "Exam")
        fall_period = make_period("01-02-2026", "03-02-2026", semester="FALL")
        spri_period = make_period("01-06-2026", "03-06-2026", semester="SPRI")
        schedules = list(self.scheduler.generate([c1, c2], [fall_period, spri_period]))
        self.assertGreater(len(schedules), 0)

    # -------------------------------------------------------------------------
    # 11. Non-exam courses are excluded from scheduling
    # -------------------------------------------------------------------------
    def test_project_and_attendance_courses_excluded(self):
        """Project and Attendance courses must not appear in any schedule."""
        p = Program("83101", 1, "FALL", "Obligatory")
        exam_course = Course("Exam Course", "90001", "Dr. A", [p], "Exam")
        proj_course = Course("Project", "90002", "Dr. B", [p], "Project")
        att_course  = Course("Lab", "90003", "Dr. C", [p], "Attendance")
        period = make_period("01-02-2026", "05-02-2026")
        schedules = list(self.scheduler.generate([exam_course, proj_course, att_course], [period]))
        for s in schedules:
            for (course, _) in s.assignments.keys():
                self.assertNotIn(course.evaluation, {"Project", "Attendance"})

    # -------------------------------------------------------------------------
    # 12. _courses_conflict correctness
    # -------------------------------------------------------------------------
    def test_courses_conflict_helper(self):
        """_courses_conflict must return True only when an Obligatory conflict exists."""
        p_obl = Program("83101", 1, "FALL", "Obligatory")
        p_elc = Program("83101", 1, "FALL", "Elective")
        p_other = Program("83102", 1, "FALL", "Obligatory")

        obl1 = Course("A", "AA001", "X", [p_obl], "Exam")
        obl2 = Course("B", "BB002", "X", [p_obl], "Exam")
        elc1 = Course("C", "CC003", "X", [p_elc], "Exam")
        elc2 = Course("D", "DD004", "X", [p_elc], "Exam")
        diff = Course("E", "EE005", "X", [p_other], "Exam")

        self.assertTrue(_courses_conflict(obl1, obl2),  "Obl vs Obl same program → conflict")
        self.assertTrue(_courses_conflict(obl1, elc1),  "Obl vs Elective same program → conflict")
        self.assertFalse(_courses_conflict(elc1, elc2), "Elective vs Elective → no conflict")
        self.assertFalse(_courses_conflict(obl1, diff), "Different programs → no conflict")

    # -------------------------------------------------------------------------
    # 13. Graph cache is reused (no crash on second identical call)
    # -------------------------------------------------------------------------
    def test_graph_cache_reuse(self):
        """Calling generate twice with the same courses must not crash or produce wrong results."""
        p = Program("83101", 1, "FALL", "Obligatory")
        c1 = Course("Math", "11111", "Dr. A", [p], "Exam")
        c2 = Course("Physics", "22222", "Dr. B", [p], "Exam")
        period = make_period("01-02-2026", "05-02-2026")
        first  = list(self.scheduler.generate([c1, c2], [period]))
        second = list(self.scheduler.generate([c1, c2], [period]))
        self.assertEqual(len(first), len(second))

    # -------------------------------------------------------------------------
    # 14. Period with all dates excluded → no schedules
    # -------------------------------------------------------------------------
    def test_all_dates_excluded_produces_no_schedules(self):
        """If every date in the period is excluded, the scheduler must return nothing."""
        excluded = [datetime(2026, 2, 1), datetime(2026, 2, 2), datetime(2026, 2, 3)]
        period = ExamPeriod("FALL", "Aleph", "01-02-2026", "03-02-2026", excluded)
        c = make_course("X0001", "83101")
        schedules = list(self.scheduler.generate([c], [period]))
        self.assertEqual(len(schedules), 0)

    # -------------------------------------------------------------------------
    # 15. Course spanning multiple programs — conflict applies to all of them
    # -------------------------------------------------------------------------
    def test_shared_course_multiple_programs_conflict(self):
        """A course taught in two programs conflicts with obligatory courses in both."""
        p1 = Program("83101", 1, "FALL", "Obligatory")
        p2 = Program("83102", 1, "FALL", "Obligatory")
        shared   = Course("Shared Math", "SS001", "Dr. Z", [p1, p2], "Exam")
        only_p1  = Course("Only P1",     "PP001", "Dr. A", [p1],     "Exam")
        # shared and only_p1 both in program 83101/year1 → must not share a date
        period = make_period("01-02-2026", "01-02-2026")  # 1 day → impossible
        schedules = list(self.scheduler.generate([shared, only_p1], [period]))
        self.assertEqual(len(schedules), 0)


if __name__ == "__main__":
    unittest.main()