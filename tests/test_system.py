import unittest
import sys
import os
import tempfile

# Ensure the project root is on the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parser.CourseParser import CourseParser
from src.parser.PeriodParser import PeriodParser
from src.scheduler.BacktrackScheduler import BacktrackScheduler
from src.output.OutputWriter import OutputWriter

class SystemTests(unittest.TestCase):

    def setUp(self):
        # Initialize the system components
        self.course_parser = CourseParser()
        self.period_parser = PeriodParser()
        self.scheduler = BacktrackScheduler()
        self.writer = OutputWriter()

        # Helper logic from main.py to filter courses
        self.filter_courses = lambda courses, selected: [
            c for c in courses if any(p.program_id in selected for p in c.programs)
        ]

    def test_system_happy_path(self):
        """
        System Test 1: Full Pipeline Success
        Simulates valid input files, runs the full scheduling process, and verifies output generation.
        """
        # 1. Setup mock data files
        mock_course_data = (
            "$$$$\n"
            "Calculus 1\n"
            "83112\n"
            "Dr. Erez\n"
            "83101,1,FALL,Obligatory\n"
            "Exam\n"
            "$$$$\n"
            "Physics 1\n"
            "83102\n"
            "Prof. Some\n"
            "83101,1,FALL,Obligatory\n"
            "Exam\n"
        )
        mock_period_data = (
            "$$$$\n"
            "FALL, Aleph\n"
            "29-01-2026, 31-01-2026\n"
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            course_file = os.path.join(temp_dir, "CourseDB.txt")
            period_file = os.path.join(temp_dir, "ExamDates.txt")
            output_file = os.path.join(temp_dir, "schedules.txt")

            with open(course_file, "w", encoding="utf-8") as f:
                f.write(mock_course_data)
            with open(period_file, "w", encoding="utf-8") as f:
                f.write(mock_period_data)

            # 2. Execute System Flow
            courses = self.course_parser.parse(course_file)
            periods = self.period_parser.parse(period_file)
            selected_programs = ["83101"]

            relevant_courses = self.filter_courses(courses, selected_programs)
            exam_courses = [c for c in relevant_courses if c.is_exam_required()]
            
            schedules = list(self.scheduler.generate(exam_courses, periods))
            self.writer.write(schedules, output_file, selected_programs)

            # 3. Assertions — count, header, and per-schedule formatting
            self.assertTrue(os.path.exists(output_file), "System should generate an output file.")
            self.assertEqual(len(schedules), 6, "Two obligatory courses on 3 days → 6 schedules.")
            
            with open(output_file, "r", encoding="utf-8") as f:
                output_content = f.read()
                self.assertIn("SCHEDULIX", output_content)
                self.assertIn("Total Schedules   : 6", output_content)
                self.assertIn("Selected Programs : 83101", output_content)
                self.assertIn("Schedule #1", output_content)
                self.assertIn("Schedule #6", output_content)
                self.assertIn("Calculus 1", output_content)
                self.assertIn("Physics 1", output_content)
                self.assertIn("Dr. Erez", output_content)

    def test_system_no_matching_programs(self):
        """
        System Test 2: Edge Case (No Matching Data)
        Simulates a user selecting programs that don't match any exam courses in the DB.
        Verifies system doesn't crash and returns empty schedules.
        """
        mock_course_data = (
            "$$$$\n"
            "Art History\n"
            "10101\n"
            "Dr. Art\n"
            "99999,1,FALL,Elective\n"
            "Exam\n"
        )
        mock_period_data = (
            "$$$$\n"
            "FALL, Aleph\n"
            "29-01-2026, 31-01-2026\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            course_file = os.path.join(temp_dir, "CourseDB.txt")
            period_file = os.path.join(temp_dir, "ExamDates.txt")
            
            with open(course_file, "w", encoding="utf-8") as f:
                f.write(mock_course_data)
            with open(period_file, "w", encoding="utf-8") as f:
                f.write(mock_period_data)

            # Execute System Flow
            courses = self.course_parser.parse(course_file)
            periods = self.period_parser.parse(period_file)
            selected_programs = ["83101"] # User selects 83101, but DB only has 99999

            relevant_courses = self.filter_courses(courses, selected_programs)
            exam_courses = [c for c in relevant_courses if c.is_exam_required()]
            
            # Assertions
            self.assertEqual(len(exam_courses), 0, "System should filter out non-matching courses.")
            
            # Running scheduler on empty list should return safely
            schedules = list(self.scheduler.generate(exam_courses, periods))
            self.assertEqual(len(schedules), 0, "System should generate 0 schedules gracefully.")
            
    def test_system_corrected_course_file_after_invalid_file(self):
        bad_course_data = (
            "$$$$\n"
            "Broken Course\n"
            "12345\n"
        )

        corrected_course_data = (
            "$$$$\n"
            "Corrected Course\n"
            "12345\n"
            "Dr. Correct\n"
            "83101,1,FALL,Obligatory\n"
            "Exam\n"
        )

        period_data = (
            "$$$$\n"
            "FALL, Aleph\n"
            "29-01-2026, 31-01-2026\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            course_file = os.path.join(temp_dir, "CourseDB.txt")
            period_file = os.path.join(temp_dir, "ExamDates.txt")
            output_file = os.path.join(temp_dir, "schedules.txt")

            with open(course_file, "w", encoding="utf-8") as f:
                f.write(bad_course_data)

            with open(period_file, "w", encoding="utf-8") as f:
                f.write(period_data)

            bad_courses = self.course_parser.parse(course_file)
            self.assertEqual(len(bad_courses), 0)

            with open(course_file, "w", encoding="utf-8") as f:
                f.write(corrected_course_data)

            courses = self.course_parser.parse(course_file)
            periods = self.period_parser.parse(period_file)

            selected_programs = ["83101"]
            relevant_courses = self.filter_courses(courses, selected_programs)
            exam_courses = [c for c in relevant_courses if c.is_exam_required()]

            schedules = list(self.scheduler.generate(exam_courses, periods))
            self.writer.write(schedules, output_file, selected_programs)

            self.assertTrue(os.path.exists(output_file))
            self.assertTrue(len(schedules) > 0)

            with open(output_file, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("Corrected Course", content)

if __name__ == '__main__':
    unittest.main()