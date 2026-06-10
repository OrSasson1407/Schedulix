# 📅 Schedulix – Exam Scheduling System

## Overview

Schedulix is an exam scheduling system designed for the Faculty of Engineering.  
The system automatically generates valid exam timetables while preventing conflicts between mandatory courses belonging to the same academic program and study year.

As the number of academic programs and courses grows, manual scheduling becomes increasingly difficult. Schedulix simplifies this process by providing an efficient scheduling engine together with an interactive graphical interface for visualization and management.

---

# Features

## Version 1.0 – Core Scheduling Engine

The first version focuses on parsing input data and generating valid exam schedules.

### Core Capabilities

- Read course and exam period data from structured text files.
- Generate all valid exam schedules.
- Detect and prevent conflicts between mandatory courses.
- Allow collisions involving elective courses.
- Export generated schedules into a readable text file.
- Complete schedule generation within 30 seconds.

---

## Version 2.0 – Interactive User Interface

The second version introduces a graphical interface and advanced data management.

### Input Workspace

- Load course database files.
- Load exam period files.
- Replace existing data.
- Append new data without deleting current information.
- Smart caching to avoid unnecessary file reloads.

### Program Explorer

- Display available academic programs.
- Select up to five programs simultaneously.
- View:
  - Course number
  - Course name
  - Academic year
  - Semester
  - Requirement type
  - Evaluation method

### Exam Calendar Editor

- Display the exam period visually.
- Exclude unavailable dates (holidays, weekends, etc.).
- Restore excluded dates.
- Modify start and end dates of the exam period.

### Output Workspace

- Display schedules using a calendar view.
- Navigate between schedules using:
  - Previous
  - Next
- Display schedule index:
  ```
  Schedule X of Y
  ```
- Export the selected schedule to a file.

---

# Scheduling Rules

The scheduling engine follows the following constraints:

- Mandatory courses from the same academic program and study year **cannot** be assigned to the same exam date.
- Elective courses may overlap.
- Mandatory and elective courses may overlap.
- Courses without exams are ignored.
- All generated schedules satisfy every scheduling constraint.

---

# Input File Format

All files must be encoded in **UTF-8**.

Records are separated by:

```
$$$$
```

---

## Course Database

Contains information about each course.

Example:

```text
$$$$
Physics 1
83102
Prof. O. Some
83101,1,FALL,Obligatory
83102,1,FALL,Obligatory
Exam
```

Fields:

- Course Name
- Course ID
- Instructor
- Program mappings
- Evaluation method

---

## Exam Period

Defines the available dates for scheduling.

Example:

```text
$$$$
FALL, Aleph
29-01-2026,11-03-2026
31-01-2026 Saturday
02-03-2026,04-03-2026 Purim
```

Contains:

- Semester
- Exam session
- Start date
- End date
- Excluded dates

---

# Technical Architecture

- **Language:** Python / C++
- **Programming Paradigm:** Object-Oriented Programming (OOP)
- **Scheduling Model:** Constraint Satisfaction Problem (CSP)
- **Performance Goal:** Generate schedules within 30 seconds
- **UI Requirement:** Interface must remain responsive (no blocking longer than one second)

---

# Project Structure

```
Schedulix
│
├── src/
│   ├── models/
│   ├── scheduler/
│   ├── parser/
│   ├── ui/
│   └── utils/
│
├── tests/
│
├── input/
│
├── output/
│
└── README.md
```

---
**Start the application:**
    ```bash
    python app.py
# Technologies

- Python
- Css
- Object-Oriented Design
- CSP Backtracking Algorithm
- Git
- GitHub
- JIRA

---

# Performance

The scheduling algorithm is optimized to:

- Generate all valid schedules.
- Avoid invalid search branches early.
- Handle large course datasets efficiently.
- Finish execution within the project time requirements.

---

# Development Methodology

The project was developed using:

- Agile development methodology
- Git version control
- JIRA task management
- Incremental feature releases

---

# Authors

Schedulix was developed as part of a Software Engineering project for the Faculty of Engineering.
