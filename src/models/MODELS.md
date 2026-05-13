# models explanation

## Course.py

this file defines the Course class. basically it represents one course in the system.

### __init__
gets the course name, id, instructor, list of programs and the evaluation type.
the only tricky part is the evaluation check - has to be one of: Exam, Project or Attendance. anything else throws a ValueError.

```python
valid_evaluations = {"Exam", "Project", "Attendance"}
if evaluation not in valid_evaluations:
    raise ValueError("Invalid evaluation type")
```

### is_exam_required
super simple. returns True if evaluation is "Exam", otherwise False.
the scheduler uses this to skip courses that dont need an exam date (like project based ones).

### __repr__
just for printing. returns something like `[CS101] Algorithms`.

### __hash__
needed because Course objects are used as dictionary keys in Schedule.
python requires __hash__ for that. it just hashes the course_id.

### __eq__
two courses are equal if they have the same course_id.
works together with __hash__ so dictionary lookups work correctly.

---

## ExamDate.py

small class that wraps a date and adds some extra info to it.

### __init__
gets a datetime object and optionally semester + moed.
automatically figures out the weekday name using strftime - so you dont have to do it manually.

### __repr__
formats the date as DD-MM-YYYY (Mon). used when printing the schedule.

---

## ExamPeriod.py

represents a time window where exams can happen, for example FALL Aleph from Jan 1 to Jan 20.
also handles excluded dates like holidays.

### __init__
validates semester (FALL/SPRI/SUMM) and moed (Aleph/Bet/Gimel).
converts date strings from DD-MM-YYYY into actual datetime objects.
excluded dates are stored as a SET not a list - checking membership in a set is much faster.

### get_available_dates
the main function here. loops from start_date to end_date day by day and returns all dates NOT in the excluded list.
each valid date gets wrapped in an ExamDate with the semester and moed already filled in.

```python
while current <= self.end_date:
    if current.date() not in self.excluded_dates:
        available.append(ExamDate(current, self.semester, self.moed))
    current += timedelta(days=1)
```

---

## Program.py

represents the connection between a study program and a course.
like "CS year 2 takes this course in FALL as obligatory".
one course can belong to multiple programs so this is basically a descriptor for each one.

### __init__
takes program_id, year, semester and requirement.
year is cast to int() just in case it comes in as a string from a file.
requirement has to be either Obligatory or Elective, nothing else.

### __repr__
returns a readable string like: `CS-BSc (Year 2, FALL, Obligatory)`

---

## Schedule.py

the main class of the whole project. holds all the exam assignments and checks if everything is valid.

### __init__
just creates an empty dictionary called assignments.
keys are (Course, moed) tuples, values are ExamDate objects.
the key is a tuple because the same course can have both Moed Aleph and Moed Bet.

### add_assignment
adds one assignment to the dictionary. pretty straightforward.
calling it twice with the same course+moed just overwrites the previous one.

### is_valid
checks if the schedule breaks the main rule:
no two exams from the same program AND same year can be on the same date... unless both are Elective.

how it works:
- goes through all assignments one by one
- for each course checks all the programs it belongs to
- builds a key: (date, program_id, year)
- if that key already exists, checks if either course is Obligatory
- if yes -> return False (invalid schedule)
- if both Elective -> its fine, keep going

### __str__
generates the final readable schedule text. does it in a few steps:
- groups all assignments by (semester, moed)
- sorts groups so FALL comes before SPRI before SUMM, Aleph before Bet before Gimel
- inside each group sorts courses by date
- builds and returns the string

---

## __init__.py

makes the models folder a proper python package and exports all the classes.
because of this you can write:

```python
from src.models import Course, Schedule
```

instead of the full path for each class separately.
`__all__` controls what gets exported on `import *`.
