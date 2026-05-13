"""
This file marks the 'models' directory as a Python package.
It exposes the core classes so they can be easily imported from outside the folder.
"""
from .Course import Course
from .Program import Program
from .ExamDate import ExamDate
from .ExamPeriod import ExamPeriod
from .Schedule import Schedule

# Define exactly what gets imported when someone uses 'from src.models import *'
__all__ = ["Course", "Program", "ExamDate", "ExamPeriod", "Schedule"]