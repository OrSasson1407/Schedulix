# End-to-End Test Checklist

## Purpose

This checklist verifies the complete Schedulix user flow from input loading to final schedule review.

These tests are partly manual because the current project does not fully automate GUI interaction.

---

## E2E Flow 1 — File-Based Scheduling Flow

### Steps
1. Start the file-based version of the system.
2. Load courses input file.
3. Load exam period/date input file.
4. Run scheduling.
5. Apply constraints.
6. Apply sorting.
7. Generate final schedule output.

### Expected Result
- Input files are parsed correctly.
- Schedules are generated.
- Invalid schedules are rejected according to constraints.
- Valid schedules are sorted correctly.
- Output file or printed result is readable and correct.

### Status
Not run yet.

---

## E2E Flow 2 — GUI Scheduling Flow

### Steps
1. Start GUI.
2. Load required data.
3. Open constraints/settings screen.
4. Enable constraints and set k values.
5. Open sorting screen.
6. Select6. Select6. Select6. Select6. Select6. Sele sc6. Select6. Select6. Sedule r6. Ses.
9. M9. M9. M9. M9. M9. M9. M9. M9. M9. M9. M9. M9. M9. M9. M9. M9. M9. M9. M9. M9. M9. M9. the complete user workflow.
- The screen does not reset unexpectedly.
- The page does not jump back to the top after changes.
- User receives clear feedback for valid - User rli- User receives clear feedback for valid - Usec- User receives clear feedet- User receives clear feedback forle Scheduling Scenario

### Steps
1. Load a dataset with many conflicting courses.
2. Enable strict constraints.
3. Try to generate schedules.

### Expected Result
- System does not crash.
- System clearly reports that no valid schedule was- System clearly reports that no v resul- System clearly reports that no valid schedule was- Syints and try again.

### Status
NNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNN — What-If SchedNNNNNNNNNNNN### Steps
1. Open a generated schedule.
2. Move an exam to a new date.
3. Preview the change.
4. Check violations.
5. Apply a valid move.
6. Try an invalid move.
7. Try a move involving a locked exam.

### Expected Res### Expected Res### Expected Res### Expected Res### Expected Res### Expected Res### Expected Res### Expected Res### Eid### Expected Res### Expected Res### Expeotected.

### Status
Not run yet.
