import unittest
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.ExamDate import ExamDate as TargetExamDate

class ExamDate(unittest.TestCase):

    def setUp(self):
        self.test_date = datetime(2026, 1, 29) # 29-Jan-2026 is a Thursday

    def test_initialization(self):
        ed = TargetExamDate(self.test_date, "FALL", "Aleph")
        self.assertEqual(ed.date, self.test_date)
        self.assertEqual(ed.semester, "FALL")
        self.assertEqual(ed.moed, "Aleph")
        self.assertEqual(ed.weekday, "Thursday")

    def test_string_representation(self):
        ed = TargetExamDate(self.test_date, "FALL", "Aleph")
        self.assertEqual(repr(ed), "29-01-2026 (Thu)")

if __name__ == '__main__':
    unittest.main()
