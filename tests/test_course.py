import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models import Course, Program

class TestCourse(unittest.TestCase):

    def setUp(self):
        self.prog = Program("CS-BSc", 2, "FALL", "Obligatory")
        self.course = Course("Algorithms", "CS101", "Dr. Cohen", [self.prog], "Exam")

    def test_valid_evaluation(self):
        # should work fine with valid evaluation
        c = Course("Math", "MATH01", "Dr. Levi", [self.prog], "Project")
        self.assertEqual(c.evaluation, "Project")

    def test_invalid_evaluation_raises_error(self):
        # should throw ValueError for bad evaluation
        with self.assertRaises(ValueError):
            Course("Bad Course", "BAD01", "Dr. X", [self.prog], "Whatever")

    def test_is_exam_required_true(self):
        self.assertTrue(self.course.is_exam_required())

    def test_is_exam_required_false(self):
        c = Course("Art", "ART01", "Dr. Y", [self.prog], "Attendance")
        self.assertFalse(c.is_exam_required())

    def test_repr(self):
        self.assertEqual(repr(self.course), "[CS101] Algorithms")

    def test_equality(self):
        same = Course("Algorithms", "CS101", "someone else", [self.prog], "Exam")
        self.assertEqual(self.course, same)

    def test_hash_same_id(self):
        same = Course("Algorithms", "CS101", "someone else", [self.prog], "Exam")
        self.assertEqual(hash(self.course), hash(same))

if __name__ == "__main__":
    unittest.main()
