# Manual UI Test Plan

## Purpose

This document describes manual UI tests for the Schedulix exam scheduling system.

Some GUI behavior cannot be fully verified by the current automatic tests, so these tests are documented and should be executed manually before release.

The main goals are:
- Verify that the GUI works correctly from the user's perspective.
- Verify that new scheduling constraints are visible and usable.
- Verify that sorting and filtering actions do not break the page.
- Verify that the page does not jump back to the top after a user changes settings or schedule options.
- Verify that the system remains responsive and does not freeze during normal use.

---

## Manual Test 1 — Open Application Successfully

### Steps
1. Start the application.
2. Open the GUI.
3. Verify that the main screen loads.

### Expected Result
- Application opens successfully.
- No crash occurs.
- Main screen is visible.
- User can start using the system.

### Status
Not run yet.

---

## Manual Test 2 — Load Course and Exam Period Data

### Steps
111111111111111111111111111111111111111111111111111111111111111111111111111111111onfirm that the data appears in the system.

### Expected Result
- Files load successfully.
- Courses are displayed correctly.
- Exam dates are displayed correctly.
- No duplicate or missing records appear.

### Status
Not run yet.

---

## Manual Test 3 — Constraint Settings Screen

### Steps
1. Open the settings/constraints screen.
2. Enable and disable each available constraint.
3. Change the value of k for each relevant constraint.
4. Save/apply the settings.

### Expected Result
- User can enable and disable constraints.
- User can enter valid k values.
- Invalid k values are rejected or handled clearly.
- Settings are applied without crashing.

### Status
Not run yet.

---

## Manual Test 4 — Sorting Settings Scre## Manual Test 4 — Sorting Setg ## Manual Tesen.
2. Select one sorting criterion.
3. Select multiple sorting criteria.
4. Change the priority/order between criteria.
5. Apply the sorting settings.

### Expected Result
- Sorting criteria can be selected.
- Priority/order can be changed.
- Sorted schedules are displayed according to the selected order.
- No crash occurs.

### Stat### Stat### Stat### Sta# Manual Test 5 — Page Should Not Jump to Top Af### Stat### Stat### Stat### Sta# M Covered
### Stat#sh### Stat#setur##to ### Stat#sh### Stat#setur##to ### Stat#sh### SOpe### Stat with a scrollable list of schedules/courses/exams.
2. Scroll down to the middle or bottom o2. Scroll down to the middle or  checkbox, sorting opti2. Scroll down to the midd Observe the scroll position.

### Expected Result
- The page should remain near the same location.
- The user should not be forced back to the top of the page.
- The user should not lose context after making a change.

### Status
Not run yet.

---

## Manual Test 6 — Exam Reschedule Drag/Move Flow

### Steps
1. Open an existing schedule.
2. Select or drag an exam to a new date.
3. Preview the change.
4. Check whether the system shows violations or legal result.
5. Apply the change if legal.
6. Try a move that causes a conflict and check cascade suggesti6. Try a move that causes a conflictves are accepted.
- Illegal mo- Illegal mo- Illolations.
- Cascade suggestions are shown when relevant.
- Locked exams are not moved.
- User receives clear feedback.

### Sta### Sta### Sta### Sta### Sta### Sta### Sta### Sta### Sta### Sta### Sta### Sta### Sta### Sta### Sta### Sta### Sta### Sta### Sta### Sta### ly.
3. Try to move another exam in a way that would normally require moving the locked exam.

### Expected Result
- Locked exam cannot be moved manually.
- Locked exam is not moved by cascade resolution.
- The system shows a clear message if the move cannot be resolved.

### Status
Not run yet.

---

## Manual Test 8 — Large Dataset Responsiveness

### Steps
1. Load a 1. Load a 1. Load a 1. Load a 1. Load a 1. pe1. L/date dataset.
3. Generate schedules3. Generate schedules3. Generate scheduin3. Generate schedulete 3. Generate schedules3. Generate schedules3. Generate schedons3. Generate schedules3. Gene approximately one second during normal interactions.
- The system does not crash.
- User can continue working after large operations.

### Status
Not run yetNot run yetNot run yetNot run yetNot run yetN##Not run yetNot run yetNot rnvaNot run yetNot run yetNot ruemptyNot run yetNot run yetNot run yetNot run yetNot run yetN##Not run yetNot run yetNot rnvaNot run yetNot run yetNot ruemptyNot run yetNot run yetNotraNot run yetNot run yetNot run yetNot run yetNot run yetN##Not run yetNot run yetNot rnv

#################n yet.

---

## Manual Test 10 — End-to-End GUI Flow

### Steps
1. Start the application.
2. Load courses.
3. Load exam periods/dates.
4. Configure constraints.
5. Configure sorting.
6. Generate schedules.
7. Review generated schedules.
8. Use exam reschedule editing.
9. Export or view final schedule output.

### Expected Result
- Full user flow works from beginning to end.
- No crash occurs.
- Output is correct and understandable.
- User can complete a realistic scheduling task.

### Status
Not run yet.
