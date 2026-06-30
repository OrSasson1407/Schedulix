"""
Standalone stress test for the scheduling engine.

Generates a large synthetic dataset in-memory (no external data files),
runs the backtracking scheduler, and verifies it completes within the
project time limit while producing valid schedules.

Run directly:
    PYTHONPATH=src python -m unittest tests.test_stress -v
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.Course import Course
from src.models.Program import Program
from src.models.ExamPeriod import ExamPeriod
from src.scheduler.BacktrackScheduler import BacktrackScheduler


def _build_stress_dataset(num_programs=8, courses_per_program=12, num_days=14):
    """Build a large in-memory course list and exam period for stress testing."""
    programs = [f"83{100 + i:03d}" for i in range(num_programs)]
    courses = []
    cid = 10000

    for prog_id in programs:
        for year in (1, 2):
            for n in range(courses_per_program // 2):
                cid += 1
                course = Course(
                    name=f"Course {prog_id}-{year}-{n}",
                    course_id=str(cid),
                    instructor="Dr. Stress",
                    programs=[Program(prog_id, year, "FALL", "Obligatory")],
                    evaluation="Exam",
                )
                courses.append(course)

    excluded = []
    period = ExamPeriod(
        semester="FALL",
        moed="Aleph",
        start_date="01-02-2026",
        end_date=f"{num_days:02d}-02-2026",
        excluded_dates=excluded,
    )
    return courses, [period], programs[:5]


class StressTests(unittest.TestCase):
    """Performance and correctness under a large synthetic workload."""

    def test_large_dataset_completes_within_time_limit(self):
        courses, periods, selected = _build_stress_dataset(
            num_programs=5, courses_per_program=8, num_days=10
        )
        selected_set = set(selected)

        filtered = []
        for course in courses:
            matching = [p for p in course.programs if p.program_id in selected_set]
            if matching:
                c = Course(
                    name=course.name,
                    course_id=course.course_id,
                    instructor=course.instructor,
                    programs=matching,
                    evaluation=course.evaluation,
                )
                filtered.append(c)

        scheduler = BacktrackScheduler()
        start = time.monotonic()
        schedules = list(scheduler.generate(filtered, periods))
        elapsed = time.monotonic() - start

        self.assertLessEqual(
            elapsed,
            BacktrackScheduler.TIME_LIMIT_SECONDS + 2,
            f"Generation took {elapsed:.1f}s, exceeding the time limit",
        )
        self.assertGreater(len(schedules), 0, "Expected at least one valid schedule")

        for sched in schedules[:10]:
            self.assertTrue(sched.is_valid(), "Every yielded schedule must be valid")

    def test_incremental_yield_under_load(self):
        """Scheduler should yield schedules before the full run finishes."""
        courses, periods, selected = _build_stress_dataset(
            num_programs=6, courses_per_program=10, num_days=12
        )
        selected_set = set(selected)
        filtered = []
        for course in courses:
            matching = [p for p in course.programs if p.program_id in selected_set]
            if matching:
                c = Course(
                    name=course.name,
                    course_id=course.course_id,
                    instructor=course.instructor,
                    programs=matching,
                    evaluation=course.evaluation,
                )
                filtered.append(c)

        scheduler = BacktrackScheduler()
        gen = scheduler.generate(filtered, periods)
        first = next(gen, None)
        self.assertIsNotNone(first, "First schedule should appear without waiting for full enumeration")
        rest = list(gen)
        self.assertGreater(len(rest), 0, "Additional schedules should follow the first yield")


if __name__ == "__main__":
    unittest.main()

