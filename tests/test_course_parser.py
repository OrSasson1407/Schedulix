import unittest
import sys
import os
import tempfile
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parser.CourseParser import CourseParser as TargetCourseParser

class CourseParser(unittest.TestCase):

    def setUp(self):
        self.parser = TargetCourseParser()
        self.valid_record = (
            "$$$$\n"
            "Physics 1\n"
            "83102\n"
            "Prof. O. Some\n"
            "83101,1,FALL,Obligatory\n"
            "Exam"
        )

    def test_parse_valid_file(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(self.valid_record)
            temp_path = f.name
        
        courses = self.parser.parse(temp_path)
        os.remove(temp_path)
        
        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0].name, "Physics 1")
        self.assertEqual(courses[0].course_id, "83102")
        self.assertEqual(courses[0].evaluation, "Exam")
        self.assertEqual(len(courses[0].programs), 1)

    def test_parse_malformed_record(self):
        malformed_record = "$$$$\nPhysics 1\n83102"
        courses = self.parser._split_records(malformed_record)
        course = self.parser._parse_record(courses[0])
        self.assertIsNone(course, "Malformed records should return None.")
        
    def test_parse_empty_file_returns_empty_list(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write("")
            temp_path = f.name

        courses = self.parser.parse(temp_path)
        os.remove(temp_path)

        self.assertEqual(courses, [])


    def test_parse_file_with_only_separators_returns_empty_list(self):
        content = "$$$$\n$$$$\n$$$$\n"

        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write(content)
            temp_path = f.name

        courses = self.parser.parse(temp_path)
        os.remove(temp_path)

        self.assertEqual(courses, [])


    def test_parse_mixed_valid_and_invalid_records_keeps_valid_only(self):
        content = (
            "$$$$\n"
            "Bad Course\n"
            "12345\n"
            "$$$$\n"
            "Good Course\n"
            "54321\n"
            "Dr. Good\n"
            "83101,1,FALL,Obligatory\n"
            "Exam\n"
        )

        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write(content)
            temp_path = f.name

        courses = self.parser.parse(temp_path)
        os.remove(temp_path)

        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0].name, "Good Course")
        self.assertEqual(courses[0].course_id, "54321")


    def test_parse_corrected_file_after_bad_file(self):
        bad_content = (
            "$$$$\n"
            "Physics 1\n"
            "83102\n"
        )

        corrected_content = (
            "$$$$\n"
            "Physics 1\n"
            "83102\n"
            "Prof. Some\n"
            "83101,1,FALL,Obligatory\n"
            "Exam\n"
        )

        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write(bad_content)
            temp_path = f.name

        bad_courses = self.parser.parse(temp_path)
        self.assertEqual(len(bad_courses), 0)

        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(corrected_content)

        corrected_courses = self.parser.parse(temp_path)
        os.remove(temp_path)

        self.assertEqual(len(corrected_courses), 1)
        self.assertEqual(corrected_courses[0].name, "Physics 1")
        self.assertEqual(corrected_courses[0].course_id, "83102")

    def test_parse_record_with_no_valid_programs_returns_none(self):
        record = (
            "$$$$\n"
            "Lonely Course\n"
            "99999\n"
            "Dr. Nobody\n"
            "bad,line,here\n"
            "Exam"
        )
        courses = self.parser._split_records(record)
        self.assertIsNone(self.parser._parse_record(courses[0]))

    def test_parse_invalid_program_line_is_skipped(self):
        record = (
            "$$$$\n"
            "Mixed Course\n"
            "88888\n"
            "Dr. Mix\n"
            "83101,1,FALL,Obligatory\n"
            "only,three,parts\n"
            "Exam"
        )
        courses = self.parser._split_records(record)
        parsed = self.parser._parse_record(courses[0])
        self.assertEqual(len(parsed.programs), 1)

    def test_parse_invalid_program_values_returns_none(self):
        line = "83101,not-a-year,FALL,Obligatory"
        self.assertIsNone(self.parser._parse_program_line(line))

if __name__ == '__main__':
    unittest.main()
