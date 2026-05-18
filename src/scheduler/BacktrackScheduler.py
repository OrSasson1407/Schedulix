"""
BacktrackScheduler.py
Implements a backtracking algorithm to generate ALL valid exam schedules.

Key design decisions:
  - Each ExamPeriod (semester + moed combination) is an INDEPENDENT scheduling
    problem. A "schedule" in v1.0 means one valid assignment of all relevant
    exam courses to dates within ONE period. Moed Aleph and Moed Bet produce
    separate schedule lists — they are never cross-producted.
  - Within a period, courses are sorted to fail fast: obligatory courses that
    appear in more programs are tried first (hardest constraints first).
  - Constraint checking is incremental: only the new assignment is checked
    against existing ones — O(programs × placed) per step.
  - A time-limit guard (default 28 s) prevents exceeding the 30-second SRS
    requirement.

Version 1.0 conflict rule (from SRS §1.2):
  Two exams conflict if they share the same date AND belong to the same
  program AND the same study year, UNLESS BOTH are Elective courses.
"""

import time
from .Scheduler import Scheduler
from ..models.Schedule import Schedule


class BacktrackScheduler(Scheduler):
    """
    Generates all valid exam schedules using recursive backtracking.

    Each ExamPeriod (one moed of one semester) is solved independently.
    Results for all periods are concatenated into a single flat list of
    Schedule objects, each tagged with its semester+moed via the ExamDate
    objects it contains.
    """

    TIME_LIMIT_SECONDS = 28

    # ------------------------------------------------------------------ #
    #  Public entry point                                                  #
    # ------------------------------------------------------------------ #

    def generate(self, courses: list, exam_periods: list) -> list:
        """
        Entry point. For each ExamPeriod, independently generates all valid
        assignments of the relevant courses to the period's available dates.
        Results from all periods are concatenated.

        :param courses:      All Course objects (filtered to Exam-only here).
        :param exam_periods: List of ExamPeriod objects.
        :return:             Flat list of valid Schedule objects across all periods.
        """
        exam_courses = [c for c in courses if c.is_exam_required()]

        if not exam_courses:
            print("[Scheduler] No exam courses to schedule.")
            return []

        if not exam_periods:
            print("[Scheduler] No available exam periods found.")
            return []

        self._start_time = time.time()
        self._time_exceeded = False

        all_schedules = []

        for period in exam_periods:
            if self._time_exceeded:
                break

            available_dates = period.get_available_dates()
            if not available_dates:
                continue

            # Only include courses whose semester matches this period
            period_courses = [
                c for c in exam_courses
                if period.semester in {prog.semester for prog in c.programs}
            ]

            if not period_courses:
                continue

            # Hardest-to-place courses first (most program memberships)
            sorted_courses = sorted(period_courses, key=lambda c: -len(c.programs))

            period_solutions = []
            self._backtrack(sorted_courses, 0, {}, available_dates, period_solutions)

            # Convert each raw assignment dict into a proper Schedule object
            for assignment in period_solutions:
                schedule = Schedule()
                for course, exam_date in assignment.items():
                    schedule.add_assignment(course, period.moed, exam_date)
                all_schedules.append(schedule)

        if self._time_exceeded:
            print(f"[Scheduler] Time limit reached. "
                  f"Returning {len(all_schedules)} schedule(s) found so far.")

        return all_schedules

    # ------------------------------------------------------------------ #
    #  Backtracking core                                                   #
    # ------------------------------------------------------------------ #

    def _backtrack(self, courses: list, index: int, current: dict,
                   available_dates: list, results: list):
        """
        Recursive backtracking for one exam period.

        :param courses:         Ordered list of Course objects to place.
        :param index:           Index of the course currently being placed.
        :param current:         Dict {Course: ExamDate} built so far.
        :param available_dates: Valid ExamDate objects for this period.
        :param results:         Accumulated complete assignment dicts.
        """
        if time.time() - self._start_time > self.TIME_LIMIT_SECONDS:
            self._time_exceeded = True
            return

        if index == len(courses):
            results.append(dict(current))
            return

        course = courses[index]
        course_semesters = {prog.semester for prog in course.programs}

        for exam_date in available_dates:
            if self._time_exceeded:
                return

            if exam_date.semester not in course_semesters:
                continue

            if self._is_compatible(course, exam_date, current):
                current[course] = exam_date
                self._backtrack(courses, index + 1, current, available_dates, results)
                del current[course]

    # ------------------------------------------------------------------ #
    #  Conflict checking                                                   #
    # ------------------------------------------------------------------ #

    def _is_compatible(self, course, exam_date, current: dict) -> bool:
        """
        Returns True if placing `course` on `exam_date` creates no conflict
        with already-placed courses.

        Conflict rule (SRS §1.2): same date + shared (program_id, year) +
        at least one of the two courses is Obligatory in that program.
        """
        date_key = exam_date.date.date()

        for placed_course, placed_date in current.items():
            if placed_date.date.date() != date_key:
                continue
            if self._programs_conflict(course, placed_course):
                return False

        return True

    def _programs_conflict(self, course_a, course_b) -> bool:
        """
        Returns True if course_a and course_b share a (program_id, year) key
        where at least one is Obligatory.
        """
        a_map = {}
        for prog in course_a.programs:
            key = (prog.program_id, prog.year)
            if key not in a_map or prog.requirement == "Obligatory":
                a_map[key] = prog.requirement

        for prog in course_b.programs:
            key = (prog.program_id, prog.year)
            if key in a_map:
                if a_map[key] == "Obligatory" or prog.requirement == "Obligatory":
                    return True

        return False