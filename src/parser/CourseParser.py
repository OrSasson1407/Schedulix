"""
CourseParser.py
Responsible for reading and parsing the course database file.
Each course record is separated by "$$$$" and contains:
  - Course name
  - Course ID (5 digits)
  - Instructor name
  - One or more program lines: program_id,year,semester,requirement
  - Evaluation type
"""

from ..models.Course import Course
from ..models.Program import Program


class CourseParser:
    """
    Parses the course database text file into a list of Course objects.
    The file format follows the spec in Appendix A of the SRS.
    """

    RECORD_SEPARATOR = "$$$$"

    def parse(self, filepath: str) -> list:
        """
        Reads the course file and returns a list of Course objects.
        :param filepath: Path to the courses text file.
        :return: List of Course objects parsed from the file.
        """
        with open(filepath, encoding="utf-8") as f:
            raw = f.read()

        records = self._split_records(raw)
        courses = []

        for record in records:
            course = self._parse_record(record)
            if course is not None:
                courses.append(course)

        return courses

    def _split_records(self, raw_text: str) -> list:
        """Splits the raw file content by '$$$$' into individual record blocks."""
        parts = raw_text.split(self.RECORD_SEPARATOR)
        return [p.strip() for p in parts if p.strip()]

    def _parse_record(self, record: str):
        """
        Parses a single course record block into a Course object.
        Lines:
          0: Course name
          1: Course ID
          2: Instructor name
          3..N-1: Program entries
          N: Evaluation type
        Returns None if the record is malformed.
        """
        lines = [line.strip() for line in record.splitlines() if line.strip()]

        if len(lines) < 5:
            print(f"[CourseParser] WARNING: Skipping malformed record (too few lines):\n{record}")
            return None

        name = lines[0]
        course_id = lines[1]
        instructor = lines[2]
        evaluation = lines[-1]
        program_lines = lines[3:-1]

        programs = []
        for prog_line in program_lines:
            prog = self._parse_program_line(prog_line)
            if prog is not None:
                programs.append(prog)

        if not programs:
            print(f"[CourseParser] WARNING: Course '{name}' has no valid program entries — skipping.")
            return None

        try:
            return Course(name=name, course_id=course_id, instructor=instructor,
                          programs=programs, evaluation=evaluation)
        except ValueError as e:
            print(f"[CourseParser] WARNING: Skipping course '{name}': {e}")
            return None

    def _parse_program_line(self, line: str):
        """
        Parses a program line: program_id,year,semester,requirement
        Returns None if the line cannot be parsed.
        """
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 4:
            print(f"[CourseParser] WARNING: Cannot parse program line: '{line}'")
            return None
        program_id, year, semester, requirement = parts
        try:
            return Program(program_id, year, semester, requirement)
        except ValueError as e:
            print(f"[CourseParser] WARNING: Invalid program entry '{line}': {e}")
            return None
