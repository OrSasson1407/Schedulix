"""
PeriodParser.py
Responsible for reading and parsing the exam periods file (V1.0 ExamDates.txt).

Each period record is separated by "$$$$" and contains:
  - Line 1: Semester, Moed   (e.g. "FALL, Aleph")
  - Line 2: Start date, End date  (e.g. "29-01-2026, 11-03-2026")
  - Remaining lines: excluded dates, each starting with "- "
    Format: "- DD-MM-YYYY [comment]"
         or "- DD-MM-YYYY, DD-MM-YYYY [comment]"  (a range of excluded dates)
"""

from datetime import datetime, timedelta
from ..models.ExamPeriod import ExamPeriod


class PeriodParser:
    """
    Parses the exam-dates text file into a list of ExamPeriod objects.
    """

    RECORD_SEPARATOR = "$$$$"

    def parse(self, filepath: str) -> list:
        """
        Reads the exam-dates file and returns a list of ExamPeriod objects.
        :param filepath: Path to the exam dates text file.
        :return: List of ExamPeriod objects.
        """
        with open(filepath, encoding="utf-8") as f:
            raw = f.read()

        records = self._split_records(raw)
        periods = []

        for record in records:
            period = self._parse_record(record)
            if period is not None:
                periods.append(period)

        return periods

    def _split_records(self, raw_text: str) -> list:
        """Splits the raw file content by '$$$$' into individual record blocks."""
        parts = raw_text.split(self.RECORD_SEPARATOR)
        return [p.strip() for p in parts if p.strip()]

    def _parse_record(self, record: str):
        """
        Parses a single exam-period record.
        Returns an ExamPeriod or None on failure.
        """
        lines = [line.strip() for line in record.splitlines() if line.strip()]

        if len(lines) < 2:
            print(f"[PeriodParser] WARNING: Skipping malformed record:\n{record}")
            return None

        # --- Line 0: Semester and Moed ---
        sem_moed = [x.strip() for x in lines[0].split(",")]
        if len(sem_moed) != 2:
            print(f"[PeriodParser] WARNING: Cannot parse semester/moed from: '{lines[0]}'")
            return None
        semester, moed = sem_moed

        # --- Line 1: Start and End dates ---
        date_parts = [x.strip() for x in lines[1].split(",")]
        if len(date_parts) != 2:
            print(f"[PeriodParser] WARNING: Cannot parse date range from: '{lines[1]}'")
            return None
        start_str, end_str = date_parts

        try:
            start_date = datetime.strptime(start_str, "%d-%m-%Y")
            end_date = datetime.strptime(end_str, "%d-%m-%Y")
        except ValueError:
            print(f"[PeriodParser] WARNING: Invalid date format in: '{lines[1]}'")
            return None

        # --- Remaining lines: excluded dates ---
        excluded_dates = []
        for exc_line in lines[2:]:
            # Each exclusion line starts with "- "
            if exc_line.startswith("-"):
                exc_line = exc_line[1:].strip()
            excluded_dates.extend(self._parse_exclusion_line(exc_line))

        try:
            return ExamPeriod(semester=semester, moed=moed,
                              start_date=start_date.strftime("%d-%m-%Y"),
                              end_date=end_date.strftime("%d-%m-%Y"),
                              excluded_dates=excluded_dates)
        except ValueError as e:
            print(f"[PeriodParser] WARNING: Could not create ExamPeriod: {e}")
            return None

    def _parse_exclusion_line(self, line: str) -> list:
        """
        Parses an exclusion line into a list of excluded datetime objects.

        Supported formats (optional comment after the date part):
          DD-MM-YYYY [comment]
          DD-MM-YYYY, DD-MM-YYYY [comment]   (inclusive date range)
        """
        # Strip any trailing comment (non-date text after the date section)
        # We split by space and try to grab at most two date tokens.
        tokens = [t.strip().rstrip(",") for t in line.split()]
        dates = []

        def try_parse(s: str):
            try:
                return datetime.strptime(s, "%d-%m-%Y")
            except ValueError:
                return None

        if not tokens:
            return []

        first = try_parse(tokens[0])
        if first is None:
            return []

        # Check if second token is also a date (range case)
        second = try_parse(tokens[1]) if len(tokens) > 1 else None

        if second is not None and second > first:
            # Expand the range into individual dates
            current = first
            while current <= second:
                dates.append(current)
                current += timedelta(days=1)
        else:
            dates.append(first)

        return dates
