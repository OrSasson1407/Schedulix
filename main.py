"""
main.py
Entry point for the Schedulix exam scheduling system (Version 1.0).

Usage:
    python main.py

The program reads three data files:
  1. Course database    (data/V1.0CourseDB.txt)
  2. Exam periods       (data/V1.0 ExamDates.txt)
  3. Selected programs  (data/Programs.txt)

It then generates all valid exam schedules (no prohibited conflicts) and
writes them to an output file in output_results/.

All paths are relative to the project root. To customise them, edit the
PATHS section near the top of this file.
"""

import os
import sys

# ---------------------------------------------------------------------------
# Ensure the project root is on the Python path so relative imports work
# when running  `python main.py`  from the project root directory.
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.parser.CourseParser import CourseParser
from src.parser.PeriodParser import PeriodParser
from src.scheduler.BacktrackScheduler import BacktrackScheduler
from src.output.OutputWriter import OutputWriter, console_print

# ---------------------------------------------------------------------------
# PATHS — edit these if your files are located elsewhere
# ---------------------------------------------------------------------------
COURSE_DB_PATH   = os.path.join(PROJECT_ROOT, "data", "V1.0CourseDB.txt")
EXAM_DATES_PATH  = os.path.join(PROJECT_ROOT, "data", "V1.0 ExamDates.txt")
PROGRAMS_PATH    = os.path.join(PROJECT_ROOT, "data", "Programs.txt")
OUTPUT_DIR       = os.path.join(PROJECT_ROOT, "output_results")
OUTPUT_FILE      = os.path.join(OUTPUT_DIR, "schedules.txt")


def load_selected_programs(filepath: str) -> list:
    """
    Reads the programs file and returns a list of selected program ID strings.
    Expected format: comma-separated 5-digit IDs on one or more lines.
    Example: 83101, 83102, 83108
    """
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    program_ids = []
    for part in content.replace("\n", ",").split(","):
        pid = part.strip()
        if pid:
            program_ids.append(pid)

    return program_ids


def filter_courses_by_programs(courses: list, selected_ids: list) -> list:
    """
    Returns only courses that belong to at least one of the selected programs.
    Also filters the course's program list to contain only the selected programs
    (so the conflict checker only considers relevant programs).
    """
    selected_set = set(selected_ids)
    filtered = []

    for course in courses:
        matching_programs = [p for p in course.programs if p.program_id in selected_set]
        if matching_programs:
            course.programs = matching_programs
            filtered.append(course)

    return filtered


def main():
    print("=" * 60)
    print("  Schedulix — Exam Schedule Generator  |  Version 1.0")
    print("=" * 60)

    # 1. Parse input files
    print("\n[1/4] Parsing course database...")
    course_parser = CourseParser()
    all_courses = course_parser.parse(COURSE_DB_PATH)
    print(f"      Loaded {len(all_courses)} course(s).")

    print("\n[2/4] Parsing exam periods...")
    period_parser = PeriodParser()
    exam_periods = period_parser.parse(EXAM_DATES_PATH)
    print(f"      Loaded {len(exam_periods)} exam period(s).")

    print("\n[3/4] Loading selected programs...")
    selected_programs = load_selected_programs(PROGRAMS_PATH)
    print(f"      Selected programs: {selected_programs}")

    # Filter courses to only those relevant to the selected programs
    relevant_courses = filter_courses_by_programs(all_courses, selected_programs)
    exam_courses = [c for c in relevant_courses if c.is_exam_required()]
    print(f"      {len(relevant_courses)} relevant course(s), {len(exam_courses)} with exams.")

    if not exam_courses:
        print("\n[!] No exam courses found for the selected programs. Exiting.")
        return

    # 2. Generate schedules
    print("\n[4/4] Generating all valid schedules (this may take a moment)...")
    scheduler = BacktrackScheduler()
    schedules = list(scheduler.generate(relevant_courses, exam_periods))
    print(f"      Found {len(schedules)} valid schedule(s).")

    # 3. Write output
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    writer = OutputWriter()
    writer.write(schedules, OUTPUT_FILE, selected_programs)

    console_print(f"\n  Output written to: {OUTPUT_FILE}")
    print("  Done.\n")


if __name__ == "__main__":
    main()