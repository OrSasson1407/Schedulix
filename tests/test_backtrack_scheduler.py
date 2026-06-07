import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scheduler.BacktrackScheduler import BacktrackScheduler as TargetBacktrackScheduler
from src.models.Course import Course
from src.models.Program import Program
from src.models.ExamPeriod import ExamPeriod

class BacktrackScheduler(unittest.TestCase):

    def setUp(self):
        self.scheduler = TargetBacktrackScheduler()
        p1 = Program("83101", 1, "FALL", "Obligatory")
        self.course1 = Course("Calculus 1", "83112", "Dr. Erez", [p1], "Exam")
        self.course2 = Course("Physics 1", "83102", "Prof. Some", [p1], "Exam")
        self.period = ExamPeriod("FALL", "Aleph", "29-01-2026", "30-01-2026")

    def test_generate_schedules(self):
        schedules = list(self.scheduler.generate([self.course1, self.course2], [self.period]))
        self.assertTrue(len(schedules) > 0, "Scheduler should find at least one valid schedule.")
        
        # Verify conflict resolution: Obligatory courses for the same program must be on different days
        first_schedule = schedules[0]
        dates = [ed.date for ed in first_schedule.assignments.values()]
        self.assertNotEqual(dates[0], dates[1], "Exams for the same program/year cannot share a date.")

    def test_no_exam_courses(self):
        p1 = Program("83101", 1, "FALL", "Obligatory")
        project_course = Course("Project", "83533", "Dr. Bell", [p1], "Project")
        schedules = list(self.scheduler.generate([project_course], [self.period]))
        self.assertEqual(len(schedules), 0, "Should return empty list for non-exam courses.")

    def test_not_enough_dates_for_conflicting_obligatory_courses(self):
        p1 = Program("83101", 1, "FALL", "Obligatory")
        c1 = Course("Math 1", "11111", "Dr. A", [p1], "Exam")
        c2 = Course("Physics 1", "22222", "Dr. B", [p1], "Exam")

        one_day_period = ExamPeriod("FALL", "Aleph", "29-01-2026", "29-01-2026")

        schedules = list(self.scheduler.generate([c1, c2], [one_day_period]))

        self.assertEqual(len(schedules), 0)


    def test_scheduler_ignores_non_exam_courses(self):
        p1 = Program("83101", 1, "FALL", "Obligatory")
        project_course = Course("Project", "33333", "Dr. C", [p1], "Project")

        period = ExamPeriod("FALL", "Aleph", "29-01-2026", "31-01-2026")

        schedules = list(self.scheduler.generate([project_course], [period]))

        self.assertEqual(len(schedules), 0)


    def test_scheduler_handles_empty_periods(self):
        p1 = Program("83101", 1, "FALL", "Obligatory")
        c1 = Course("Math 1", "11111", "Dr. A", [p1], "Exam")

        schedules = list(self.scheduler.generate([c1], []))

        self.assertEqual(len(schedules), 0)
    
if __name__ == '__main__':
    unittest.main()
