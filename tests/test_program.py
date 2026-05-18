import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.Program import Program as TargetProgram

class Program(unittest.TestCase):

    def test_valid_initialization(self):
        p = TargetProgram("83101", "1", "FALL", "Obligatory")
        self.assertEqual(p.program_id, "83101")
        self.assertEqual(p.year, 1)
        self.assertEqual(p.semester, "FALL")
        self.assertEqual(p.requirement, "Obligatory")

    def test_invalid_semester(self):
        with self.assertRaises(ValueError):
            TargetProgram("83101", "1", "WINTER", "Obligatory")

    def test_invalid_requirement(self):
        with self.assertRaises(ValueError):
            TargetProgram("83101", "1", "FALL", "Optional")

    def test_repr(self):
        p = TargetProgram("83101", "1", "FALL", "Obligatory")
        self.assertEqual(repr(p), "83101 (Year 1, FALL, Obligatory)")

if __name__ == '__main__':
    unittest.main()
