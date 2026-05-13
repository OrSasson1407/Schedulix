from datetime import datetime, timedelta
from .ExamDate import ExamDate

class ExamPeriod:
    """
    Represents a block of time where exams can be scheduled, handling holidays and excluded dates.
    """
    def __init__(self, semester, moed, start_date, end_date, excluded_dates=None):
        # Strict validation according to the SRS specification
        valid_semesters = {"FALL", "SPRI", "SUMM"}
        valid_moeds = {"Aleph", "Bet", "Gimel"}
        
        if semester not in valid_semesters:
            raise ValueError(f"Invalid semester: {semester}")
        if moed not in valid_moeds:
            raise ValueError(f"Invalid moed: {moed}")
            
        self.semester = semester
        self.moed = moed
        # Convert string dates (DD-MM-YYYY) into actual Python datetime objects
        self.start_date = datetime.strptime(start_date, "%d-%m-%Y")
        self.end_date = datetime.strptime(end_date, "%d-%m-%Y")

        # Convert the list of excluded datetimes into a Set of pure 'date' objects. 
        # Sets are used because checking 'if x in set' is much faster than checking a list.
        self.excluded_dates = set(d.date() for d in (excluded_dates or []))

    def get_available_dates(self):
        """
        Generates a list of all valid ExamDate objects between the start and end dates,
        skipping any dates found in the excluded_dates set.
        """
        available = []
        current = self.start_date

        # Loop day by day from start to end
        while current <= self.end_date:
            if current.date() not in self.excluded_dates:
                # Inject the semester and moed context into the new ExamDate
                available.append(ExamDate(current, self.semester, self.moed))
            # Move forward by exactly 1 day
            current += timedelta(days=1)

        return available