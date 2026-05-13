class Course:
    """
    Represents a single course in the system.
    """
    def __init__(self, name, course_id, instructor, programs, evaluation):
        self.name = name
        self.course_id = course_id
        self.instructor = instructor
        self.programs = programs  # List of Program objects this course belongs to

        # Version 1.0 Constraint: Evaluation must be one of three specific types
        valid_evaluations = {"Exam", "Project", "Attendance"}
        if evaluation not in valid_evaluations:
            raise ValueError("Invalid evaluation type")

        self.evaluation = evaluation

    def is_exam_required(self):
        """
        Checks if the course actually requires scheduling.
        Courses evaluated by Project or Attendance do not need an exam date.
        """
        return self.evaluation == "Exam"

    def __repr__(self):
        """Returns a clean string representation for printing and debugging."""
        return f"[{self.course_id}] {self.name}"

    def __hash__(self):
        """Allows the Course object to be used as a key in dictionaries (like Schedule.assignments)."""
        return hash(self.course_id)

    def __eq__(self, other):
        """Defines that two Course objects are 'equal' if they share the same course_id."""
        return isinstance(other, Course) and self.course_id == other.course_id