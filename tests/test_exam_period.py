import unittest
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.ExamPeriod import ExamPeriod as TargetExamPeriod

class ExamPeriod(unittest.TestCase):

    def setUp(self):
        self.start = "29-01-2026"
        self.end = "31-01-2026"
        self.excluded = [datetime(2026, 1, 30)]

    def test_initialization(self):
        ep = TargetExamPeriod("FALL", "Aleph", self.start, self.end, self.excluded)
        self.assertEqual(ep.semester, "FALL")
        self.assertEqual(ep.moed, "Aleph")
        self.assertEqual(ep.start_date, datetime(2026, 1, 29))
        self.assertIn(datetime(2026, 1, 30).date(), ep.excluded_dates)

    def test_invalid_semester(self):
        with self.assertRaises(ValueError):
            TargetExamPeriod("WINTER", "Aleph", self.start, self.end)

    def test_get_available_dates(self):
        ep = TargetExamPeriod("FALL", "Aleph", self.start, self.end, self.excluded)
        available = ep.get_available_dates()
        
        self.assertEqual(len(available), 2, "Should exclude 30-01-2026")
        self.assertEqual(available[0].date.day, 29)
        self.assertEqual(available[1].date.day, 31)

if __name__ == '__main__':
    unittest.main()
