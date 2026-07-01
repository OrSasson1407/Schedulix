"""
Standalone stress tests for the Schedulix scheduling engine.

Purpose:
- Verify that the scheduler can handle a large synthetic workload.
- Verify that valid schedules are produced without waiting for full enumeration.
- Keep the tests bounded so CI does not hang while trying to enumerate every possible schedule.

Run:
    PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_stress.py -q
"""

import os
import sys
import time
import unittest
from itertools import islice

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
                courses.append(
                    Course(
                        name=f"Course {prog_id}-{year}-{n}",
                        course_id=str(cid),
                        instructor="Dr. Stress",
                        programs=[Program(prog_id, year, "FALL", "Obligatory")],
                        evaluation="Exam",
                    )
                )

    period = ExamPeriod(
        semester="FALL",
        moed="Aleph",
        start_date="01-02-2026",
        end_date=f"{num_days:02d}-02-2026",
        excluded_dates=[],
    )
    return courses, [period], programs[:5]


def _filter_selected_courses(courses, selected_programs):
    """Keep only courses that belong to the selected programs."""
    selected_set = set(selected_programs)
    filtered = []
    for course in courses:
        matching = [p for p in course.programs if p.program_id in selected_set]
        if matching:
            filtered.append(
                Course(
                    name=course.name,
                    course_id=course.course_id,
                    instructor=course.instructor,
                    programs=matching,
                    evaluation=course.evaluation,
                )
            )
    return filtered


class StressTests(unittest.TestCase):
    """Performance and correctness checks under large synthetic workloads."""

    def test_large_dataset_completes_within_time_limit(self):
        courses, periods, selected = _build_stress_dataset(
            num_programs=5, courses_per_program=8, num_days=10
        )
        filtered = _filter_selected_courses(courses, selected)

        scheduler = BacktrackScheduler()
        start = time.monotonic()
        schedules = list(islice(scheduler.generate(filtered, periods), 10))
        elapsed = time.monotonic() - start

        self.assertLessEqual(
            elapsed,
            BacktrackScheduler.TIME_LIMIT_SECONDS + 2,
            f"Generation took {elapsed:.1f}s, exceeding the time limit",
        )
        self.assertGreater(len(schedules), 0, "Expected at least one valid schedule")

        for sched in schedules:
            self.assertTrue(sched.is_valid(), "Every yielded schedule must be valid")

    def test_incremental_yield_under_load(self):
        """
        Scheduler should yield partial schedules before full enumeration finishes.

        Important: this test intentionally consumes only a small bounded sample.
        Enumerating every valid schedule in a stress scenario can be enormous and
        would make CI appear frozen.
        """
        courses, periods, selected = _build_stress_dataset(
            num_programs=6, courses_per_program=10, num_days=12
        )
        filtered = _filter_selected_courses(courses, selected)

        scheduler = BacktrackScheduler()
        start = time.monotonic()
        sample = list(islice(scheduler.generate(filtered, periods), 6))
        elapsed = time.monotonic() - start

        self.assertGreater(len(sample), 0, "Expected at least one yielded schedule")
        self.assertLess(elapsed, 5, "Scheduler should yield early under load")
        for sched in sample:
            self.assertTrue(sched.is_valid(), "Every yielded schedule must be valid")


if __name__ == "__main__":
    unittest.main()