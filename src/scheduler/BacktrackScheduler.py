"""
BacktrackScheduler.py
Implements a backtracking algorithm to generate ALL valid exam schedules.

Key design decisions:
  - Courses are sorted to fail fast: obligatory courses in more programs are tried first,
    giving the backtracker the hardest constraints early (reduces wasted exploration).
  - Constraint checking is incremental: we only check the new assignment against existing
    ones, not the whole schedule, keeping each step O(programs * existing_assignments).
  - A time-limit guard (default 28 seconds) prevents exceeding the 30-second SRS requirement.
  - The scheduler produces schedules grouped by ExamPeriod semester/moed, assigning
    each course to a date in the period that matches its program semester.

Version 1.0 conflict rule (from SRS §1.2):
  Two exams conflict if they share the same date AND belong to the same program AND
  the same study year, UNLESS BOTH are Elective courses.
"""

import time
from .Scheduler import Scheduler
from ..models.Schedule import Schedule


class BacktrackScheduler(Scheduler):
    """
    Generates all valid exam schedules using recursive backtracking.
    Respects the Version 1.0 constraint: no same-day, same-program, same-year
    conflicts unless both courses are Elective.
    """

    TIME_LIMIT_SECONDS = 28  # Stay under the 30-second SRS performance requirement

    def generate(self, courses: list, exam_periods: list) -> list:
        """
        Entry point. Filters to exam-only courses, builds the date pool,
        and launches the backtracking search.

        :param courses: All Course objects (will be filtered to Exam-only).
        :param exam_periods: List of ExamPeriod objects.
        :return: List of valid Schedule objects.
        """
        # Only schedule courses that have an actual exam
        exam_courses = [c for c in courses if c.is_exam_required()]

        if not exam_courses:
            print("[Scheduler] No exam courses to schedule.")
            return []

        # Build a flat pool of all valid ExamDate objects across all periods
        all_dates = []
        for period in exam_periods:
            all_dates.extend(period.get_available_dates())

        if not all_dates:
            print("[Scheduler] No available exam dates found.")
            return []

        # Convert courses into (Course, Moed) scheduling requirements
        courses_to_schedule = []
        for course in exam_courses:
            courses_to_schedule.append((course, "Aleph"))
            courses_to_schedule.append((course, "Bet"))

        # Sort requirements to improve backtracking efficiency:
        # Courses that belong to more programs (harder to place) go first.
        sorted_requirements = sorted(courses_to_schedule, key=lambda req: -len(req[0].programs))

        self._start_time = time.time()
        self._time_exceeded = False
        results = []

        self._backtrack(sorted_requirements, 0, {}, all_dates, results)

        if self._time_exceeded:
            print(f"[Scheduler] Time limit reached. Returning {len(results)} schedules found so far.")

        return results

    def _backtrack(self, requirements: list, index: int, current_assignments: dict,
                   available_dates: list, results: list):
        """
        Recursive backtracking core.

        :param requirements: Full ordered list of (Course, Target_Moed) tuples.
        :param index: Index of the requirement currently being placed.
        :param current_assignments: Dict of {(Course, Moed): ExamDate} built so far.
        :param available_dates: All available ExamDate objects to try.
        :param results: Accumulated list of complete valid schedules.
        """
        # Stop if we've exceeded the time limit
        if time.time() - self._start_time > self.TIME_LIMIT_SECONDS:
            self._time_exceeded = True
            return

        # Base case: all requirements have been placed — record this valid schedule
        if index == len(requirements):
            schedule = Schedule()
            for (course, moed), exam_date in current_assignments.items():
                schedule.add_assignment(course, moed, exam_date)
            results.append(schedule)
            return

        course, target_moed = requirements[index]

        # Only place this course on dates matching its semester (FALL/SPRI/SUMM)
        course_semesters = {prog.semester for prog in course.programs}

        for exam_date in available_dates:
            # Check for correct semester AND the correct Moed for this requirement
            if exam_date.semester not in course_semesters or exam_date.moed != target_moed:
                continue
            
            # Check time limit inside the inner loop too (tight loop for large date sets)
            if self._time_exceeded:
                return

            # Check if placing this course on this date causes any conflict with
            # already-placed courses. If not, recurse.
            if self._is_compatible(course, exam_date, current_assignments):
                current_assignments[(course, target_moed)] = exam_date
                self._backtrack(requirements, index + 1, current_assignments, available_dates, results)
                del current_assignments[(course, target_moed)]  # Undo (backtrack)

    def _is_compatible(self, course, exam_date, current_assignments: dict) -> bool:
        """
        Checks whether placing `course` on `exam_date` conflicts with any
        already-assigned course in `current_assignments`.

        Conflict rule (SRS §1.2):
          Two courses conflict if they are on the same date AND share at least one
          (program_id, year) pair AND at least one of them is Obligatory in that program.
        """
        date_key = exam_date.date.date()

        for (placed_course, placed_moed), placed_date in current_assignments.items():
            if placed_date.date.date() != date_key:
                continue  # Different date — no conflict possible

            # Same date: check for program+year overlap
            if self._programs_conflict(course, placed_course):
                return False

        return True

    def _programs_conflict(self, course_a, course_b) -> bool:
        """
        Returns True if course_a and course_b share a (program_id, year) combination
        where at least one of them is Obligatory.

        We build a lookup from course_a's programs for O(1) lookup.
        """
        # Map (program_id, year) -> requirement for course_a
        a_map = {}
        for prog in course_a.programs:
            key = (prog.program_id, prog.year)
            # If we encounter Obligatory anywhere, keep it (stricter)
            if key not in a_map or prog.requirement == "Obligatory":
                a_map[key] = prog.requirement

        for prog in course_b.programs:
            key = (prog.program_id, prog.year)
            if key in a_map:
                req_a = a_map[key]
                req_b = prog.requirement
                # Conflict only if at least one is Obligatory
                if req_a == "Obligatory" or req_b == "Obligatory":
                    return True

        return False