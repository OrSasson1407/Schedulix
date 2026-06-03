"""
OutputWriter.py
Responsible for writing the generated schedules to a human-readable output file.

Output format (per SRS §2.3):
  - All valid schedules are listed sequentially.
  - Each schedule is numbered and grouped by Semester → Moed → sorted by date.
  - FALL comes before SPRI; Aleph before Bet before Gimel.
  - Each entry shows: date, course name, instructor.

Designed to be easily extended for future output formats (HTML, CSV, etc.)
by subclassing or adding format strategies in v2.0+.
"""


class OutputWriter:
    """
    Writes a list of Schedule objects to a human-readable text file.
    """

    # Ordering maps for consistent semester/moed sorting
    SEMESTER_ORDER = {"FALL": 1, "SPRI": 2, "SUMM": 3}
    MOED_ORDER = {"Aleph": 1, "Bet": 2, "Gimel": 3}

    def write(self, schedules, output_path: str, selected_programs: list = None):
        """
        Writes all schedules to a text file.

        :param schedules: List of Schedule objects to output.
        :param output_path: File path for the output file.
        :param selected_programs: Optional list of selected program IDs for the header.
        """
        schedules = list(schedules) if schedules is not None else []
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(self._build_header(schedules, selected_programs))
            if not schedules:
                f.write("No valid schedules could be generated with the given constraints.\n")
                return

            for idx, schedule in enumerate(schedules, start=1):
                f.write(self._format_schedule(schedule, idx))
                f.write("\n")

        print(f"[OutputWriter] Wrote {len(schedules)} schedule(s) to '{output_path}'.")

    def _build_header(self, schedules: list, selected_programs: list) -> str:
        """Builds a summary header for the output file."""
        lines = []
        lines.append("=" * 70)
        lines.append("  SCHEDULIX — Exam Schedule Generator  |  Version 1.0")
        lines.append("=" * 70)
        if selected_programs:
            lines.append(f"  Selected Programs : {', '.join(str(p) for p in selected_programs)}")
        lines.append(f"  Total Schedules   : {len(schedules)}")
        lines.append("=" * 70)
        lines.append("")
        return "\n".join(lines) + "\n"

    def _format_schedule(self, schedule, number: int) -> str:
        """
        Formats a single Schedule object into a readable block of text.
        Groups exams by Semester then Moed, sorted chronologically within each group.
        """
        lines = []
        lines.append(f"{'─' * 70}")
        lines.append(f"  Schedule #{number}")
        lines.append(f"{'─' * 70}")

        # Group assignments by (semester, moed)
        groups = {}
        for (course, target_moed), exam_date in schedule.assignments.items():
            key = (exam_date.semester, exam_date.moed)
            groups.setdefault(key, []).append((course, exam_date))

        # Sort groups: FALL → SPRI → SUMM, Aleph → Bet → Gimel
        sorted_keys = sorted(
            groups.keys(),
            key=lambda k: (
                self.SEMESTER_ORDER.get(k[0], 9),
                self.MOED_ORDER.get(k[1], 9)
            )
        )

        for sem, moed in sorted_keys:
            lines.append(f"\n  [ Semester: {sem}  |  Moed: {moed} ]\n")
            # Sort courses within the group by date
            items = sorted(groups[(sem, moed)], key=lambda x: x[1].date)
            for course, exam_date in items:
                date_str = exam_date.date.strftime("%d-%m-%Y (%A)")
                lines.append(f"    {date_str:<28}  {course.name:<35}  {course.instructor}")

        lines.append("")
        return "\n".join(lines) + "\n"
