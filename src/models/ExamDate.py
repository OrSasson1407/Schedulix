class ExamDate:
    """
    Represents a specific, valid date for an exam.
    Holds both the datetime object and contextual data (Semester/Moed) for sorting.
    """
    def __init__(self, date_obj, semester="Unknown", moed="Unknown"):
        self.date = date_obj
        self.weekday = date_obj.strftime("%A")  # Automatically extracts the day of the week (e.g., "Monday")
        self.semester = semester
        self.moed = moed

    def __repr__(self):
        """Formats the date in a readable European format: DD-MM-YYYY (Day)"""
        return self.date.strftime("%d-%m-%Y (%a)")