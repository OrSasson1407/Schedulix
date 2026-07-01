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
        
    def test_parse_empty_period_file_returns_empty_list(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write("")
            temp_path = f.name

        periods = self.parser.parse(temp_path)
        os.remove(temp_path)

        self.assertEqual(periods, [])


    def test_parse_corrected_period_file_after_bad_file(self):
        bad_content = (
            "$$$$\n"
            "FALL, Aleph\n"
        )

        corrected_content = (
            "$$$$\n"
            "FALL, Aleph\n"
            "29-01-2026, 31-01-2026\n"
        )

        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write(bad_content)
            temp_path = f.name

        bad_periods = self.parser.parse(temp_path)
        self.assertEqual(len(bad_periods), 0)

        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(corrected_content)

        corrected_periods = self.parser.parse(temp_path)
        os.remove(temp_path)

        self.assertEqual(len(corrected_periods), 1)
        self.assertEqual(corrected_periods[0].semester, "FALL")
        self.assertEqual(corrected_periods[0].moed, "Aleph")


    def test_parse_period_with_exclusion_range(self):
        content = (
            "$$$$\n"
            "FALL, Aleph\n"
            "29-01-2026, 05-02-2026\n"
            "30-01-2026, 01-02-2026 Holiday\n"
        )

        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write(content)
            temp_path = f.name

        periods = self.parser.parse(temp_path)
        os.remove(temp_path)

        self.assertEqual(len(periods), 1)
        self.assertEqual(len(periods[0].excluded_dates), 3)

    def test_parse_invalid_semester_moed_line(self):
        record = "$$$$\nFALL\n29-01-2026, 31-01-2026"
        periods = self.parser._split_records(record)
        self.assertIsNone(self.parser._parse_record(periods[0]))

    def test_parse_invalid_date_range_line(self):
        record = "$$$$\nFALL, Aleph\nonly-one-date"
        periods = self.parser._split_records(record)
        self.assertIsNone(self.parser._parse_record(periods[0]))

    def test_parse_invalid_date_format(self):
        record = "$$$$\nFALL, Aleph\n99-99-2026, 31-01-2026"
        periods = self.parser._split_records(record)
        self.assertIsNone(self.parser._parse_record(periods[0]))

    def test_parse_exclusion_empty_line_returns_empty(self):
        self.assertEqual(self.parser._parse_exclusion_line(""), [])

    def test_parse_exclusion_unparseable_token_returns_empty(self):
        self.assertEqual(self.parser._parse_exclusion_line("not-a-date"), [])

if __name__ == '__main__':
    unittest.main()
