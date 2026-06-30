import io
import unittest
import sys
import os
import tempfile
from datetime import datetime
from unittest.mock import patch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.output.OutputWriter import OutputWriter as TargetOutputWriter, console_print
from src.models.Schedule import Schedule
from src.models.Course import Course
from src.models.Program import Program
from src.models.ExamDate import ExamDate

class OutputWriter(unittest.TestCase):

    def setUp(self):
        self.writer = TargetOutputWriter()
        self.schedule = Schedule()
        p = Program("83101", 1, "FALL", "Obligatory")
        c = Course("Math 1", "101", "Dr. A", [p], "Exam")
        ed = ExamDate(datetime(2026, 1, 29), "FALL", "Aleph")
        self.schedule.add_assignment(c, "Aleph", ed)

    def test_write_schedule(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            temp_path = f.name
            
        self.writer.write([self.schedule], temp_path, ["83101"])
        
        with open(temp_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        os.remove(temp_path)
        
        self.assertIn("SCHEDULIX", content)
        self.assertIn("Selected Programs : 83101", content)
        self.assertIn("Schedule #1", content)
        self.assertIn("Math 1", content)
        
    def test_write_empty_schedule_list(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            temp_path = f.name

        self.writer.write([], temp_path, ["83101"])

        with open(temp_path, "r", encoding="utf-8") as f:
            content = f.read()

        os.remove(temp_path)

        self.assertIn("SCHEDULIX", content)
        self.assertIn("Selected Programs", content)


    def test_write_schedule_with_multiple_selected_programs(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            temp_path = f.name

        self.writer.write([self.schedule], temp_path, ["83101", "83102", "83104"])

        with open(temp_path, "r", encoding="utf-8") as f:
            content = f.read()

        os.remove(temp_path)

        self.assertIn("83101", content)
        self.assertIn("83102", content)
        self.assertIn("83104", content)

    def test_console_print_handles_unicode_paths_on_cp1252_console(self):
        buffer = io.BytesIO()
        limited_stdout = io.TextIOWrapper(buffer, encoding="cp1252", line_buffering=True)
        with patch("sys.stdout", limited_stdout):
            console_print("Output written to: שולחן העבודה\\schedules.txt")
        self.assertTrue(buffer.getvalue())

if __name__ == '__main__':
    unittest.main()
