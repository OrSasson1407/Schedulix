# End-to-End and System Test Checklist — Schedulix

## Purpose

This checklist documents complete system flows from input loading to final output. Some parts are automated by `tests/test_system.py`, `tests/test_cli.py`, and related unit tests. Full browser clicking is still manual because the current UI tests render views but do not control a real browser.

## E2E Coverage Summary

| ID | Flow | Automated? | Manual? | Related Evidence |
|---|---|---:|---:|---|
| E2E-01 | File parser → scheduler → output writer | Yes | Optional | `tests/test_system.py` |
| E2E-02 | CLI startup does not break | Yes | Optional | `tests/test_cli.py` |
| E2E-03 | GUI input → generate → output | Partial | Yes | Manual screenshots/video |
| E2E-04 | Invalid input recovery | Yes | Yes | `tests/test_system.py` + manual error screenshot |
| E2E-05 | No matching programs | Yes | Optional | `tests/test_system.py` |
| E2E-06 | Large dataset / stress scenario | Yes | Yes | `tests/test_stress.py` + manual responsiveness check |
| E2E-07 | Scroll position after same-page action | Partial | Yes | Manual before/after screenshots |
| E2E-08 | CI/CD regression run | Yes | No | GitHub Actions run |

---

## E2E-01 — File-Based Scheduling Flow

### Steps
1. Parse course database file.
2. Parse exam period file.
3. Filter courses by selected programs.
4. Generate schedules.
5. Write schedules to output file.

### Expected Result
- Input files are parsed correctly.
- Only relevant exam courses are scheduled.
- Valid schedules are generated.
- Output file is created and contains readable schedule data.

### Automated Evidence
Covered by `tests/test_system.py::test_system_happy_path`.

### Status
Automated. Manual evidence optional.

---

## E2E-02 — CLI Startup Flow

### Steps
1. Run the CLI entry point.
2. Confirm the scheduler generator is consumed correctly before counting results.

### Expected Result
- CLI does not crash because of `len(generator)` or similar generator/list mistakes.

### Automated Evidence
Covered by `tests/test_cli.py`.

### Status
Automated.

---

## E2E-03 — Full GUI Scheduling Flow

### Steps
1. Start the Flask application.
2. Load course file.
3. Load exam period file.
4. Select programs.
5. Configure constraints.
6. Configure sorting.
7. Generate schedules.
8. Review output schedule.
9. Export or view final result.

### Expected Result
- User can complete the full scheduling process from the GUI.
- Buttons and forms work in the browser.
- User sees clear feedback messages.
- Output is correct and understandable.
- The page does not unexpectedly reset or jump to the top during same-page actions.

### Status
Manual browser test required.

---

## E2E-04 — Invalid Input Recovery

### Steps
1. Load an invalid or malformed course file.
2. Confirm that the system shows an error or loads zero valid records safely.
3. Replace it with a corrected file.
4. Generate schedules again.

### Expected Result
- Invalid input does not crash the system.
- Corrected input is accepted.
- Schedules can be generated after recovery.

### Automated Evidence
Covered by `tests/test_system.py::test_system_corrected_course_file_after_invalid_file`.

### Status
Automated. Manual error-message screenshot recommended.

---

## E2E-05 — No Matching Programs

### Steps
1. Load valid course and period files.
2. Select a program that has no matching exam courses.
3. Run generation.

### Expected Result
- System handles the empty selection result gracefully.
- No crash occurs.
- User receives a clear message that no schedules were generated.

### Automated Evidence
Covered by `tests/test_system.py::test_system_no_matching_programs`.

### Status
Automated.

---

## E2E-06 — Large Dataset / Stress Scenario

### Steps
1. Build or load a large dataset with many courses and dates.
2. Run the scheduling engine.
3. Confirm that the scheduler yields valid schedules without waiting for full enumeration.
4. Confirm that execution is bounded and does not freeze CI.

### Expected Result
- Scheduler returns valid sample schedules under load.
- Test does not enumerate all possible schedules.
- Test finishes in CI.

### Automated Evidence
Covered by `tests/test_stress.py`.

### Status
Automated. Manual GUI responsiveness check recommended.

---

## E2E-07 — Scroll Position Does Not Reset

### Steps
1. Open a long GUI page.
2. Scroll down.
3. Perform an action on the same page.
4. Check whether the page remains near the same location.

### Expected Result
- Page does not jump back to the top.
- User keeps their context.

### Status
Manual browser test required.

---

## E2E-08 — CI/CD Regression Run

### Steps
1. Push changes or open a pull request.
2. Confirm that GitHub Actions starts.
3. Confirm lint and tests run successfully.
4. Save a screenshot of the successful workflow.

### Expected Result
- CI/CD workflow runs on GitHub.
- All tests pass.
- Coverage report is printed.

### Automated Evidence
`.github/workflows/ci.yml`.

### Status
Automated in GitHub Actions.
