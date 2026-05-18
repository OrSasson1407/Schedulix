import unittest
import sys
import os
import tempfile
from datetime import datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parser.PeriodParser import PeriodParser as TargetPeriodParser

class PeriodParser(unittest.TestCase):

    def setUp(self):
        self.parser = TargetPeriodParser()
        self.valid_record = (
            "$$$$\n"
            "FALL, Aleph\n"
            "29-01-2026, 31-01-2026\n"
            "- 30-01-2026 Shabat"
        )

    def test_parse_valid_record(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(self.valid_record)
            temp_path = f.name
            
        periods = self.parser.parse(temp_path)
        os.remove(temp_path)
        
        self.assertEqual(len(periods), 1)
        self.assertEqual(periods[0].semester, "FALL")
        self.assertEqual(periods[0].moed, "Aleph")
        self.assertEqual(len(periods[0].excluded_dates), 1)
        self.assertIn(datetime(2026, 1, 30).date(), periods[0].excluded_dates)

    def test_parse_exclusion_range(self):
        dates = self.parser._parse_exclusion_line("02-03-2026, 04-03-2026 Purim")
        self.assertEqual(len(dates), 3)
        self.assertEqual(dates[0], datetime(2026, 3, 2))
        self.assertEqual(dates[-1], datetime(2026, 3, 4))

if __name__ == '__main__':
    unittest.main()
