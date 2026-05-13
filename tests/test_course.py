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
        c = Course("Math", "MATH01", "Dr. Levi", [self.prog], "Project")
        self.assertEqual(c.evaluation, "Project")

    def test_invalid_evaluation_raises_error(self):
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

    # --- NEW TESTS BELOW ---

    def test_multiple_programs(self):
        prog2 = Program("SE-BSc", 2, "FALL", "Elective")
        c = Course("Multi", "MUL01", "Dr. Z", [self.prog, prog2], "Exam")
        self.assertEqual(len(c.programs), 2)

    def test_equality_different_type(self):
        self.assertFalse(self.course == "Not a course string")

    def test_equality_different_id(self):
        other = Course("Algorithms", "CS102", "Dr. Cohen", [self.prog], "Exam")
        self.assertNotEqual(self.course, other)

    def test_hash_different_id(self):
        other = Course("Algorithms", "CS102", "Dr. Cohen", [self.prog], "Exam")
        self.assertNotEqual(hash(self.course), hash(other))

if __name__ == "__main__":
    unittest.main()
