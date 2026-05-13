class Program:
    """
    Represents a study program's specific requirements for a course.
    """
    def __init__(self, program_id, year, semester, requirement):
        self.program_id = program_id
        self.year = int(year)  # Cast to integer in case a string is passed from a file
        
        # Validate semester input
        valid_semesters = {"FALL", "SPRI", "SUMM"}
        if semester not in valid_semesters:
            raise ValueError(f"Invalid semester: {semester}")
        self.semester = semester

        # Validate whether the course is a must-take or optional for this specific program
        valid_requirements = {"Obligatory", "Elective"}
        if requirement not in valid_requirements:
            raise ValueError("Invalid requirement type")
        self.requirement = requirement

    def __repr__(self):
        """Readable representation of the program requirement."""
        return f"{self.program_id} (Year {self.year}, {self.semester}, {self.requirement})"