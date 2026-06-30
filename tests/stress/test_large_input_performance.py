import unittest
import time
from datetime import datetime, timedelta

from src.models import Course, Program, Schedule, ExamDate, SchedulingConstraints
from src.scheduler.reschedule.ConstraintEvaluator import ConstraintEvaluator

def _course(cid, name, program_id="P", year=1, requirement="Obligatory"):
    return Course(
        name,
        cid,
        "Dr",
        [Program(program_id, year, "FALL", requirement)],
        "Exam",
    )


class TestLargeInputPerformance(unittest.TestCase):
    """
    Stress tests for large scheduling input.

    These tests are automatic and safe:
    - They do not change project files.
    - They do not require GUI interaction.
    - They use generated in-memory data only.
    - They verify that the system can evaluate a large schedule without crashing.
    """

    def test_large_schedule_constraint_evaluation_finishes_quickly(self):
        number_of_courses = 300

        schedule = Schedule()
        start_date = datetime(2026, 2, 1)

        for i in range(number_of_courses):
            course = _course(str(i), f"Course {i}")
            exam_date = ExamDate(start_date + timedelta(days=i), "FALL", "Aleph")
            schedule.add_assignment(course, "Aleph", exam_date)

        constraints = SchedulingConstraints(
            {
                "mandatory_spacing": {
                    "enabled": True,
                    "k": 1,
                }
            }
        )

        evaluator = ConstraintEvaluator(constraints)

        start_time = time.perf_counter()
        report = evaluator.evaluate(schedule)
        duration = time.perf_counter() - start_time

        self.assertTrue(report.is_legal)
        self.assertLess(
            duration,
            2.0,
            f"Large schedule evaluation took too long: {duration:.3f} seconds",
        )


if __name__ == "__main__":
    unittest.main()