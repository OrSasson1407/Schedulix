"""
Scheduler.py
Defines the abstract Scheduler base class.
All concrete scheduling strategies must inherit from this class and implement generate().
This design satisfies the OOP requirement and makes it easy to swap in new algorithms
(e.g. a SAT-solver or optimized scheduler) in future versions without changing callers.
"""

from abc import ABC, abstractmethod


class Scheduler(ABC):
    """
    Abstract base class for all scheduling strategies.
    Concrete subclasses must implement the generate() method.
    """

    @abstractmethod
    def generate(self, courses: list, exam_periods: list, constraints=None) -> list:
        """
        Generates all valid exam schedules for the given courses within the given exam periods.

        :param courses: List of Course objects that require scheduling (exam-only).
        :param exam_periods: List of ExamPeriod objects defining valid date windows.
        :param constraints: Optional SchedulingConstraints object. Any schedule that
                            violates an active hard constraint is dropped before being
                            returned. When None, no extra hard constraints are applied.
        :return: A list of Schedule objects, each representing one valid assignment.
        """
        pass
