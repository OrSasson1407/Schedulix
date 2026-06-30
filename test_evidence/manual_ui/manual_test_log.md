# Manual UI Test Evidence Log — Schedulix

## M-07 — Page Should Not Jump Back to Top After Changes

Tester: Pillar Ghandour
Browser: Chrome/Safari
Status: Pass

Steps:
1. Opened the Calendar screen.
2. Scrolled to the middle/bottom of the page.
3. Clicked a date to toggle its availability.
4. Checked the scroll position after the action.

Expected Result:
The page should not jump back to the top.

Actual Result:
The page returned to the same scroll area after the change.

Evidence:
- M-07-before-action.png
- M-07-after-action-no-jump.png


## M-08 — Generate Schedules

Tester: Pillar Ghandour
Browser: Chrome/Safari
Status: Pass

Steps:
1. Loaded course and exam date files.
2. Selected study programs.
3. Clicked Generate.
4. Checked that the GUI displayed a result or moved to the Output screen.

Expected Result:
Schedules are generated or a clear result message appears.

Actual Result:
The system completed the generation flow and displayed the result.

Evidence:
- M-08-generation-result.png


## M-10 — What-If Move Flow

Tester: Pillar Ghandour
Browser: Chrome/Safari
Status: Pass

Steps:
1. Opened the Output screen after schedule generation.
2. Dragged an exam to another valid date.
3. Applied the valid What-If move.
4. Tried an invalid move or locked-exam move.
5. Checked the system messages.

Expected Result:
Valid moves are accepted. Invalid moves are rejected with a clear warning.

Actual Result:
The valid move was applied, and the invalid move showed a warning/error.

Evidence:
- M-10-valid-move-applied.png
- M-10-invalid-move-warning.png


