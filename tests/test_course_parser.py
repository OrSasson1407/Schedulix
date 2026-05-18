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

if __name__ == '__main__':
    unittest.main()
