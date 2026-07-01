# Schedulix – Exam Scheduling System

**Software version: 34.0** (extension of Version 3.0 per course SRS)

Schedulix is a planning tool for exam timetables at the Faculty of Engineering. It helps schedule exams for selected study programs while reducing same-day conflicts and supporting additional spacing and capacity rules. The system finds valid schedules and lets users browse, sort, export, and manually adjust results.

Implementation: **Python**, object-oriented design, Flask web UI (`app.py`) and file-based CLI (`main.py`).

---

## Quick start

### Requirements

- Python 3.11+ (CI uses 3.12)
- Flask (web application only)

```bash
pip install flask
```

### Web application (GUI — Version 2.0 + 34.0)

```bash
python app.py
```

Open **http://127.0.0.1:5000**

Sample data loads from `data/V1.0CourseDB.txt` and `data/V1.0 ExamDates.txt`. Parsed data may be reused from `data/.cache.pkl` when source files are unchanged (SRS §6.1).

### File-based CLI (Version 1.0)

```bash
python main.py
```

| Input | Default path |
|-------|----------------|
| Course database | `data/V1.0CourseDB.txt` |
| Exam periods | `data/V1.0 ExamDates.txt` |
| Selected programs | `data/Programs.txt` |

Output: `output_results/schedules.txt` (paths configurable at the top of `main.py`).

The CLI runs **baseline** schedule generation (mandatory same-day conflicts). Threshold constraints (SRS §2) and sorting (SRS §3) are configured in the **web UI**. The shared `BacktrackScheduler` engine supports threshold filtering when constraints are passed; `main.py` does not expose a Settings or sort workflow.

### Tests

```bash
set PYTHONPATH=src        # Windows
export PYTHONPATH=src     # Linux / macOS

python -m unittest discover -s tests -p "test_*.py" -v
python -m unittest discover -s tests/stress -v
```

---

## Version history

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

### Version 34.0 — Threshold constraints, optimal sorting, and value-add features

Per **SRS Version 34.0**:

#### SRS §2 — Threshold constraints

Configured on the **Settings** screen. Each can be enabled or disabled independently with its own integer parameter **k**. A schedule that violates an **active** threshold is **disqualified** during generation (not yielded). Day differences count **calendar days** (weekends and holidays included).

| SRS | Setting | Rule |
|-----|---------|------|
| §2.1 | Mandatory exam spacing | Minimum days between two **obligatory** exams (same program & year) ≥ **k** (k ≥ 1) |
| §2.2 | General exam spacing | Minimum days between any two exams, obligatory or elective (same program & year) ≥ **k** (k ≥ 1) |
| §2.3 | Elective collisions limit | Number of same-day elective pairs (same program) ≤ **k** (k ≥ 0) |
| §2.4 | Mandatory exam window | Days between first and last **obligatory** exam (program, year, moed) ≥ **k** (k ≥ 1) |
| §2.5 | Daily global capacity | Maximum exams on any single day ≤ **k** (k ≥ 1) |

Baseline mandatory same-day conflicts from earlier versions always apply.

#### SRS §3 — Multi-criteria sorting (“שיבוץ מיטבי”)

On the **Output** screen, sort schedules that passed all active thresholds **without re-generating**. User picks one or more criteria and their **priority order**. Each criterion sorts in **descending** order (higher metric = better rank):

| SRS | Criterion |
|-----|-----------|
| §3.1 | Minimum days between two obligatory exams (same program & year) |
| §3.2 | Average days between any two exams, obligatory or elective (same program & year) |
| §3.3 | Count of elective same-day collisions (same program) |
| §3.4 | Days between first and last obligatory exam (program, year, moed) |
| §3.5 | Peak number of exams on the busiest day |

Sort order may be changed after generation; threshold settings are not changed during a run.

#### SRS §4 — Custom value-add features (team-defined)

| Feature | Description |
|---------|-------------|
| **Moed A → Moed B spacing** | Optional hard constraint: minimum calendar days between a course’s Aleph and Bet exam (Settings). Enforced across moeds during generation and interactive reschedule. |
| **Exam Reschedule** | Post-generation editing on the Output screen: drag an exam to another day, preview violations, apply an automatic cascade that moves other exams, or **place on same day anyway**; lock exams; undo edits. |

Additional UX (not in SRS): light/dark theme, custom calendar event exclusion bar.

---

## File loading: Overwrite vs Append

Choose mode on the **Input** screen before upload.

### Courses

| Mode | Effect |
|------|--------|
| **Overwrite** | Replace all courses; clear selected programs, schedules, history, manual edits, locks |
| **Append** | Add courses whose `course_id` is new; keep existing courses and selected programs; clear schedules/history/edits |

Saved to `data/uploaded_courses.txt`.

### Exam periods

| Mode | Effect |
|------|--------|
| **Overwrite** | Replace all periods; clear calendar overrides, selected programs, schedules, history |
| **Append** | Add new `(semester, moed)` entries only; keep overrides; clear schedules/history |

Saved to `data/uploaded_periods.txt`.

Uploading courses or periods always clears generated results so stale schedules are not shown.

---

## Generation history

Stores up to **2** recent runs: programs, schedule snapshots, calendar overrides, and an input fingerprint (course file + period file + calendar overrides).

- **Restore** recovers programs, calendar overrides, and schedules from a prior run (matching fingerprint only).
- Entries that do not match the current files/calendar are hidden.
- Uploading new input files clears history.

---

## Exam Reschedule (Output)

1. Drag an exam within the same moed.
2. Review threshold violations and elective collisions.
3. **Move other exam(s) away** — apply move + minimal cascade.
4. **Place on same day anyway** — move only the dragged exam (shown when another exam already occupies the target date).
5. **↶ Undo** manual edits; **🔒** lock exams against moves.

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

Fields: name, 5-digit course ID, instructor, program lines (`programId,year,semester,Obligatory|Elective`), evaluation method (`Exam`, `Project`, `Attendance`, …).

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

Fields: semester, moed (Aleph/Bet), date range, excluded dates.

Samples: `data/`.

---

## Terminology (SRS §C)

| Term | Meaning |
|------|---------|
| **Course** | 5-digit ID, instructor, program memberships (year, semester, obligatory/elective), evaluation type |
| **Exam period** | Date range for a semester and moed in which exams may be placed |
| **Exam assignment** | Placing one course’s exam on a date within the period |
| **Exam schedule** | A complete assignment of all selected programs’ exam courses |

---

## Project structure

```text
Schedulix/
├── app.py              # Web UI (V2 + V34)
├── main.py             # CLI (V1 baseline)
├── data/               # Input samples, uploads, cache
├── output_results/     # CLI export
├── static/style.css    # UI styling (light/dark)
├── src/
│   ├── models/         # Course, Schedule, Constraints, …
│   ├── parser/
│   ├── scheduler/      # BacktrackScheduler, SchedulerSorter, reschedule/
│   ├── output/
│   └── ui/views.py
└── tests/              # Unit, system, UI view, stress, manual/e2e docs
```

---

## Testing & quality

- **Automated:** 240+ unit/system/UI/app-route tests; CI runs flake8 + unittest (`.github/workflows/ci.yml`)
- **Stress:** `tests/test_stress.py`, `tests/stress/test_large_input_performance.py`
- **Manual / E2E:** `tests/manual/manual_ui_test_plan.md` — execute in browser; **record results** in `tests/manual/manual_test_results.md`
- **E2E checklist:** `tests/e2e/e2e_test_checklist.md`
- **Code review:** `CODE_REVIEW.md`
- **Process (SRS §7):** Git, JIRA, Agile

---

## Performance

- Scheduler internal time limit: **28 seconds** per moed search; partial results kept if exceeded
- Web UI: Aleph and Bet generated in parallel; counts update during search
- Parsed file cache avoids reload when inputs unchanged (SRS §6.1)

---

## Export

- **GUI:** Output → **↓ Export All Semesters** (current browsed schedules)
- **CLI:** all valid schedules → `output_results/schedules.txt`

---

## Authors

Schedulix was developed as part of a Software Engineering project for the Faculty of Engineering.
