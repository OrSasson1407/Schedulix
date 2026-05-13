class Schedule:
    """
    The master object that holds a proposed mapping of Courses to ExamDates.
    """
    def __init__(self):
        # Dictionary mapping (Course, Moed) tuples to ExamDate objects
        self.assignments = {}

    def add_assignment(self, course, moed, exam_date):
        """Assigns a specific moed requirement for a course to a date in the schedule."""
        self.assignments[(course, moed)] = exam_date

    def is_valid(self):
        """
        Validates the entire schedule against Version 1.0 constraints:
        No two exams from the same program and the same year can be on the same date,
        UNLESS both of those exams are "Elective" courses.
        """
        seen = {}  # Tracks what we've already scheduled: {(date, program_id, year): requirement_type}

        for (course, moed), exam_date in self.assignments.items():
            date_key = exam_date.date.date()

            for prog in course.programs:
                # Create a unique key for the specific date, program, and study year
                key = (date_key, prog.program_id, prog.year)

                if key in seen:
                    # We found two courses mapped to the exact same date, program, and year!
                    previous_req = seen[key]
                    current_req = prog.requirement
                    
                    # If AT LEAST ONE of them is "Obligatory", the schedule is invalid.
                    if previous_req == "Obligatory" or current_req == "Obligatory":
                        return False

                # Save the requirement type in our tracker. 
                # If we encounter an "Obligatory" course, we save that strictly over an "Elective"
                if key not in seen or prog.requirement == "Obligatory":
                    seen[key] = prog.requirement

        return True  # If we get through all assignments without returning False, the schedule is valid.

    def __str__(self):
        """
        Generates a readable, formatted text output of the schedule.
        Groups exams first by Semester, then by Moed, and finally sorts chronologically by Date.
        """
        groups = {}
        
        # 1. Group the assignments by (Semester, Moed) tuple
        for (course, target_moed), exam_date in self.assignments.items():
            group_key = (exam_date.semester, exam_date.moed)
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append((course, exam_date))
            
        res = "=== Exam Schedule ===\n\n"
        
        # 2. Define a strict sorting order for Semesters and Moeds so FALL always prints before SPRI
        sem_order = {"FALL": 1, "SPRI": 2, "SUMM": 3, "Unknown": 4}
        moed_order = {"Aleph": 1, "Bet": 2, "Gimel": 3, "Unknown": 4}
        
        # 3. Sort the group headers
        sorted_groups = sorted(
            groups.keys(), 
            key=lambda k: (sem_order.get(k[0], 9), moed_order.get(k[1], 9))
        )
        
        # 4. Print out the sorted groups and their courses
        for sem, moed in sorted_groups:
            res += f"--- Semester: {sem} | Moed: {moed} ---\n"
            
            # Sort the individual courses within this specific group chronologically by date
            sorted_items = sorted(groups[(sem, moed)], key=lambda x: x[1].date)
            
            for course, date in sorted_items:
                res += f"  {date}: {course.name} (Instructor: {course.instructor})\n"
            
            res += "\n"
            
        return res