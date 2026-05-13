import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime
from src.models import Course, Program, Schedule, ExamDate

class TestSchedule(unittest.TestCase):

    def setUp(self):
        self.prog1 = Program("CS-BSc", 2, "FALL", "Obligatory")
        self.prog2 = Program("CS-BSc", 2, "FALL", "Obligatory")

        self.course1 = Course("Algorithms", "CS101", "Dr. Cohen", [self.prog1], "Exam")
        self.course2 = Course("Data Structures", "CS102", "Dr. Levi", [self.prog2], "Exam")

        self.date1 = ExamDate(datetime(2026, 1, 14), "FALL", "Aleph")
        self.date2 = ExamDate(datetime(2026, 1, 16), "FALL", "Aleph")

    def test_valid_schedule_different_dates(self):
        # two obligatory courses on different dates - should be valid
        s = Schedule()
        s.add_assignment(self.course1, "Aleph", self.date1)
        s.add_assignment(self.course2, "Aleph", self.date2)
        self.assertTrue(s.is_valid())

    def test_invalid_schedule_same_date_obligatory(self):
        # two obligatory courses from same program+year on same date - should be invalid
        s = Schedule()
        s.add_assignment(self.course1, "Aleph", self.date1)
        s.add_assignment(self.course2, "Aleph", self.date1)
        self.assertFalse(s.is_valid())

    def test_valid_schedule_both_elective(self):
        # two elective courses on same date - should be valid
        prog_e1 = Program("CS-BSc", 2, "FALL", "Elective")
        prog_e2 = Program("CS-BSc", 2, "FALL", "Elective")
        c1 = Course("Sport", "SP01", "Dr. A", [prog_e1], "Exam")
        c2 = Course("Music", "MU01", "Dr. B", [prog_e2], "Exam")
        s = Schedule()
        s.add_assignment(c1, "Aleph", self.date1)
        s.add_assignment(c2, "Aleph", self.date1)
        self.assertTrue(s.is_valid())

    def test_add_assignment_overwrites(self):
        # adding same course+moed twice should overwrite
        s = Schedule()
        s.add_assignment(self.course1, "Aleph", self.date1)
        s.add_assignment(self.course1, "Aleph", self.date2)
        self.assertEqual(s.assignments[(self.course1, "Aleph")], self.date2)

    def test_empty_schedule_is_valid(self):
        s = Schedule()
        self.assertTrue(s.is_valid())

if __name__ == "__main__":
    unittest.main()
