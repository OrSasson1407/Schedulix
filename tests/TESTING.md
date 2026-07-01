# Schedulix Testing Documentation

## Goal

This document explains the testing strategy for Schedulix and directly addresses the professor's testing comments:

1. UI tests are not full browser-click tests.
2. Automatic and manual GUI tests must both be documented.
3. The page should not jump back to the top after same-page changes.
4. Manual GUI tests must be recorded.
5. End-to-end/system evidence is required.
6. Stress tests should check large numbers of schedules.
7. CI/CD should run tests automatically.

---

## Testing Levels

| Level | Purpose | Automated Files | Manual Evidence Needed? |
|---|---|---|---|
| Unit tests | Test isolated models, parsers, constraints, schedule logic | `tests/test_course.py`, `tests/test_program.py`, `tests/test_exam_date.py`, `tests/test_exam_period.py`, `tests/test_schedule.py`, `tests/test_constraints.py`, `tests/test_schedule_sorter.py` | No |
| Integration tests | Test components working together | `tests/test_backtrack_scheduler.py`, `tests/test_backtrack_scheduler_extended.py`, `tests/test_output_writer.py`, parser tests | No |
| System tests | Test parser → scheduler → output flow | `tests/test_system.py` | Optional screenshots |
| End-to-end tests | Test complete user workflows | `tests/e2e/e2e_test_checklist.md`, partial automation in system/CLI tests | Yes for GUI browser flow |
| UI view tests | Test rendered HTML and UI structure | `tests/test_ui_views.py` | Yes, because these do not click in a real browser |
| Manual UI tests | Test browser behavior, buttons, scroll, popups, what-if actions | `tests/manual/manual_ui_test_plan.md` | Yes |
| Stress/performance tests | Test large synthetic workloads and early scheduler yield | `tests/test_stress.py`, `tests/test_large_input_performance.py` | Optional GUI screenshot/video |
| CI/CD | Run tests automatically on PR/push | `.github/workflows/ci.yml` | Screenshot of passing workflow recommended |

---

## Important Clarification About UI Testing

The current automated UI tests check HTML rendering and view content. They verify that pages contain expected forms, messages, selected program cards, flash messages, branding, and layout elements.

However, these tests do **not** fully automate a browser and do **not** physically click buttons like a user. Therefore, browser interaction must be checked manually using the manual UI test plan.

This is why the project includes both:

- automatic UI view tests in `tests/test_ui_views.py`, and
- manual GUI tests in `tests/manual/manual_ui_test_plan.md`.

---

## Scroll Position Requirement

Professor comment: after changes on a page, the page should not return to the top and force the user to scroll back down.

### How this is tested
- Manual test `M-07` checks this in a real browser.
- The tester should capture before/after screenshots showing that the scroll position remains near the same place after an action.

### Actions to check
- Selecting or unselecting a program.
- Changing a setting or checkbox.
- Applying sorting.
- Restoring generation history.
- Editing schedule options.

### Expected result
The user stays near the same location and does not lose context.

---

## Stress Testing Requirement

Professor comment: add an extended stress test for large numbers of schedules.

### Automated stress tests
`tests/test_stress.py` creates synthetic large data in memory and checks that:

- generation starts successfully,
- valid schedules are produced,
- the scheduler yields early instead of waiting for all schedules,
- the test is bounded so CI does not freeze.

### Why the stress test samples schedules
The number of possible valid schedules can be extremely large. A stress test should not enumerate every possible schedule because that can hang CI. Instead, it verifies that the scheduler can produce a valid sample quickly and safely.

---

## Manual Test Evidence Format

For each manual test, record:

```text
Test ID:
Date:
Tester:
Browser:
Input files used:
Steps executed:
Expected result:
Actual result:
Pass/Fail:
Evidence screenshot/video name:
Notes/bugs:
```

---

## CI/CD

The project includes a GitHub Actions workflow at `.github/workflows/ci.yml`.

It should run on pull requests and pushes to main, install dependencies, run lint checks, run the automated tests, and print a coverage report.

Recommended evidence for submission:

- Screenshot of the GitHub Actions workflow passing.
- Terminal output showing local tests passed.

---

## Recommended Commands

Run all tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q
```

Run the main required groups:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_ui_views.py tests/test_system.py tests/test_stress.py tests/test_cli.py -q
```

Run stress tests only:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_stress.py -q
```