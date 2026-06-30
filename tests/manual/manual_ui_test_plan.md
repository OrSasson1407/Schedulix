# Manual UI Test Plan — Schedulix

## Purpose

The automated UI tests in this project verify rendered HTML views and server responses, but they do **not** fully click buttons inside a real browser. Therefore, browser behavior such as scrolling, popups, button clicks, and full GUI interaction must also be checked manually.

This document records the manual GUI tests required for the professor's feedback.

## Manual UI Test Summary

| ID | Area | Type | Status | Evidence to Save |
|---|---|---|---|---|
| M-01 | Application launch | Manual UI | Not run | Screenshot of home screen |
| M-02 | Load input files | Manual UI | Not run | Screenshot after courses and periods load |
| M-03 | Program selection | Manual UI | Not run | Screenshot showing selected programs counter |
| M-04 | Calendar editing | Manual UI | Not run | Screenshot after excluding/restoring dates |
| M-05 | Constraint settings | Manual UI | Not run | Screenshot of chosen constraints and k values |
| M-06 | Sorting settings | Manual UI | Not run | Screenshot of sorted schedule order |
| M-07 | Scroll position after changes | Manual UI | Not run | Before/after screenshots showing same scroll position |
| M-08 | Generate schedules | Manual UI + E2E | Not run | Screenshot of generation result |
| M-09 | Generation history restore | Manual UI | Not run | Screenshot before and after restore |
| M-10 | What-if move | Manual UI | Not run | Screenshot of valid and invalid move feedback |
| M-11 | Large dataset responsiveness | Manual UI + Stress | Not run | Screenshot/video showing loading feedback and result |
| M-12 | Export output | Manual UI + E2E | Not run | Exported schedule file |

---

## M-01 — Open Application Successfully

### Steps
1. Start the application with `python app.py`.
2. Open the local browser address shown by Flask.
3. Confirm that the Schedulix interface appears.

### Expected Result
- The page loads without crashing.
- Sidebar, topbar, logo, and main content are visible.
- The user can navigate between pages.

### Status
Not run.

---

## M-02 — Load Course and Exam Period Data

### Steps
1. Open the input page.
2. Upload or load the course database file.
3. Upload or load the exam period/date file.
4. Confirm that courses, programs, and exam dates appear in the UI.

### Expected Result
- Files load successfully.
- Courses and programs are displayed.
- Exam period dates are displayed.
- Invalid files show clear error messages instead of crashing.

### Status
Not run.

---

## M-03 — Program Selection

### Steps
1. Scroll to the program selection area.
2. Select one program.
3. Select several programs, up to the allowed limit.
4. Try selecting more than five programs.

### Expected Result
- Selected program cards are visually marked.
- Selected program counter updates correctly.
- More than five programs are blocked with a clear message.
- The page remains usable after each selection.

### Status
Not run.

---

## M-04 — Calendar Editing

### Steps
1. Open the calendar page.
2. Exclude an available date.
3. Restore the excluded date.
4. Change the start or end date of the exam period if the UI allows it.

### Expected Result
- Excluded dates are removed from the available dates.
- Restored dates return to the available dates.
- The calendar view updates clearly.
- No crash occurs.

### Status
Not run.

---

## M-05 — Constraint Settings

### Steps
1. Open the settings or constraints page.
2. Enable and disable every available constraint.
3. Change each relevant `k` value.
4. Enter invalid values, such as negative numbers or non-numeric text.
5. Apply the settings.

### Expected Result
- Valid settings are saved.
- Invalid values are rejected, clamped, or handled with a clear message.
- The system does not crash.
- The chosen constraints affect generated schedules.

### Status
Not run.

---

## M-06 — Sorting Settings

### Steps
1. Open the sorting area.
2. Select one sorting criterion.
3. Select multiple sorting criteria.
4. Change the priority/order between criteria.
5. Generate or refresh schedules.

### Expected Result
- Sorting criteria are selectable.
- Priority/order is applied correctly.
- Schedules are displayed according to the selected sorting order.
- No crash occurs.

### Status
Not run.

---

## M-07 — Page Should Not Jump Back to Top After Changes

### Reason for Test
The professor specifically noted that some windows jump back to the top after changes. This test verifies that the user does not lose their place while working on a long page.

### Steps
1. Open a page with enough content to scroll, such as program selection, output schedules, or settings.
2. Scroll to the middle or bottom of the page.
3. Perform an action on the same page, for example:
   - select/unselect a program,
   - change a checkbox,
   - apply sorting,
   - restore generation history,
   - edit a schedule option.
4. Observe the scroll position after the action.

### Expected Result
- The page remains near the same scroll position.
- The page does **not** jump back to the top.
- The user does not need to scroll back down to continue working.

### Status
Not run.

---

## M-08 — Generate Schedules

### Steps
1. Load valid course and period files.
2. Select valid programs.
3. Click Generate Schedules.
4. Wait for generation to finish.
5. Open the output page.

### Expected Result
- The generate button gives visible feedback while running.
- The user does not wait with a completely empty screen.
- A result message appears.
- Generated schedules are shown or a clear “no schedules found” message appears.

### Status
Not run.

---

## M-09 — Generation History Restore

### Steps
1. Generate schedules for one set of selected programs.
2. Change the selected programs.
3. Generate again.
4. Use Generation History to restore a previous run.

### Expected Result
- Previous selected programs are restored.
- History panel updates correctly.
- The current run is clearly marked.
- Irrelevant history should be hidden or treated carefully when different input files are loaded.

### Status
Not run.

---

## M-10 — What-If Move Flow

### Steps
1. Open a generated schedule.
2. Move an exam to a different date.
3. Preview the change.
4. Try a legal move.
5. Try an illegal move that creates a conflict.
6. Try a move involving a locked exam if locking is supported.

### Expected Result
- Legal moves are accepted.
- Illegal moves are rejected with clear violation messages.
- Cascade suggestions appear when relevant.
- Locked exams are not moved by manual or automatic changes.

### Status
Not run.

---

## M-11 — Large Dataset Responsiveness

### Steps
1. Load a large course dataset or use a stress dataset.
2. Select several programs.
3. Generate schedules.
4. Observe the screen while generation is running.

### Expected Result
- The system does not crash.
- The user receives feedback that generation is running.
- The system completes within the required project limit or clearly reports a timeout/partial result.
- After generation, the UI remains usable.

### Status
Not run.

---

## M-12 — Export Final Schedule

### Steps
1. Generate schedules.
2. Select a schedule.
3. Export or view the final output.
4. Open the exported file.

### Expected Result
- Output file is created.
- Output includes the selected programs and scheduled exams.
- Output is readable and understandable.

### Status
Not run.
