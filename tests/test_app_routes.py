"""
Integration tests for Flask routes in app.py.

Covers professor feedback items that require server behaviour beyond HTML view tests:
  - 5-program selection limit enforcement
  - Overwrite vs append file loading
  - Generation history fingerprint filtering and restore guard
  - Live generation status endpoint
"""

import copy
import os
import sys
import unittest
from io import BytesIO

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import (
    app,
    state,
    relevant_gen_history,
    input_fingerprint,
)
from src.models.Course import Course
from src.models.Program import Program
from src.models.Constraints import SchedulingConstraints


def _fresh_state():
    """Reset in-memory app state between tests."""
    template = {
        "courses": [],
        "periods": [],
        "period_overrides": {},
        "selected_programs": [],
        "aleph_schedules": [],
        "bet_schedules": [],
        "courses_file_hash": None,
        "periods_file_hash": None,
        "file_mode": "overwrite",
        "active_aleph": 0,
        "active_bet": 0,
        "preset_target_aleph": True,
        "preset_target_bet": True,
        "gen_history": [],
        "flash": None,
        "active_semester": "",
        "pagination": {},
        "constraints": SchedulingConstraints.default_config(),
        "sort_criteria": [],
        "locked_exams": set(),
        "locked_exam_dates": {},
        "schedule_backup": None,
        "custom_events": [],
        "edit_history": [],
        "gen_job": {
            "running": False,
            "done": False,
            "timed_out": False,
            "error": None,
        },
    }
    state.clear()
    for key, value in template.items():
        if isinstance(value, set):
            state[key] = set()
        elif isinstance(value, dict):
            state[key] = copy.deepcopy(value)
        elif isinstance(value, list):
            state[key] = []
        else:
            state[key] = value


COURSE_RECORD = (
    "$$$$\n"
    "Calculus 1\n"
    "83112\n"
    "Dr. Erez\n"
    "83101,1,FALL,Obligatory\n"
    "Exam\n"
)

PERIOD_RECORD = (
    "$$$$\n"
    "FALL, Aleph\n"
    "29-01-2026, 31-01-2026\n"
)


class AppRouteTests(unittest.TestCase):
    def setUp(self):
        _fresh_state()
        self.client = app.test_client()
        app.config["TESTING"] = True

    def test_program_toggle_blocks_sixth_program(self):
        state["selected_programs"] = ["83101", "83102", "83104", "83107", "83108"]
        rv = self.client.post(
            "/programs/toggle",
            data={"prog_id": "83109"},
            headers={"X-Requested-With": "Schedulix"},
        )
        self.assertEqual(rv.status_code, 400)
        data = rv.get_json()
        self.assertIn("Max 5 programs", data["error"])
        self.assertEqual(len(state["selected_programs"]), 5)

    def test_program_toggle_allows_fifth_selection(self):
        state["selected_programs"] = ["83101", "83102", "83104", "83107"]
        rv = self.client.post(
            "/programs/toggle",
            data={"prog_id": "83108"},
            headers={"X-Requested-With": "Schedulix"},
        )
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(len(state["selected_programs"]), 5)

    def test_upload_courses_overwrite_replaces_and_clears_selection(self):
        state["courses"] = [
            Course("Old", "11111", "Dr. Old", [Program("83101", 1, "FALL", "Obligatory")], "Exam")
        ]
        state["selected_programs"] = ["83101"]
        rv = self.client.post(
            "/upload/courses",
            data={
                "file": (BytesIO(COURSE_RECORD.encode("utf-8")), "courses.txt"),
                "mode": "overwrite",
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(rv.status_code, 302)
        self.assertEqual(len(state["courses"]), 1)
        self.assertEqual(state["courses"][0].name, "Calculus 1")
        self.assertEqual(state["selected_programs"], [])

    def test_upload_courses_append_keeps_existing_and_adds_new(self):
        existing = Course(
            "Existing", "11111", "Dr. X",
            [Program("83101", 1, "FALL", "Obligatory")], "Exam",
        )
        state["courses"] = [existing]
        state["selected_programs"] = ["83101"]
        rv = self.client.post(
            "/upload/courses",
            data={
                "file": (BytesIO(COURSE_RECORD.encode("utf-8")), "courses.txt"),
                "mode": "append",
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(rv.status_code, 302)
        self.assertEqual(len(state["courses"]), 2)
        ids = {c.course_id for c in state["courses"]}
        self.assertEqual(ids, {"11111", "83112"})
        self.assertEqual(state["selected_programs"], ["83101"])

    def test_upload_periods_overwrite_clears_overrides(self):
        state["period_overrides"] = {"FALL|Aleph": {"start_shift": 1}}
        state["selected_programs"] = ["83101"]
        rv = self.client.post(
            "/upload/periods",
            data={
                "file": (BytesIO(PERIOD_RECORD.encode("utf-8")), "periods.txt"),
                "mode": "overwrite",
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(rv.status_code, 302)
        self.assertEqual(len(state["periods"]), 1)
        self.assertEqual(state["period_overrides"], {})
        self.assertEqual(state["selected_programs"], [])

    def test_relevant_gen_history_hides_mismatched_fingerprints(self):
        state["courses_file_hash"] = "courses-a"
        state["periods_file_hash"] = "periods-b"
        state["period_overrides"] = {}
        current_fp = input_fingerprint()
        state["gen_history"] = [
            {
                "input_fingerprint": current_fp,
                "programs": ["83101"],
                "aleph_count": 3,
                "bet_count": 1,
            },
            {
                "input_fingerprint": ("old-courses", "old-periods", "old-overrides"),
                "programs": ["99999"],
                "aleph_count": 1,
                "bet_count": 0,
            },
        ]
        visible = relevant_gen_history()
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]["programs"], ["83101"])

    def test_history_restore_rejects_mismatched_fingerprint(self):
        state["courses_file_hash"] = "current"
        state["periods_file_hash"] = "current"
        state["gen_history"] = [
            {
                "input_fingerprint": ("other", "other", "other"),
                "programs": ["83101"],
                "aleph_schedules": [],
                "bet_schedules": [],
                "period_overrides": {},
            }
        ]
        rv = self.client.post(
            "/history/restore",
            data={"index": "0"},
            headers={"X-Requested-With": "Schedulix"},
        )
        self.assertEqual(rv.status_code, 400)
        self.assertIn("does not match", rv.get_json()["error"])

    def test_generate_status_returns_json_counts(self):
        state["gen_job"] = {"running": True, "done": False, "timed_out": False, "error": None}
        rv = self.client.get(
            "/generate/status",
            headers={"X-Requested-With": "Schedulix"},
        )
        self.assertEqual(rv.status_code, 200)
        data = rv.get_json()
        self.assertIn("aleph_count", data)
        self.assertIn("bet_count", data)
        self.assertTrue(data["running"])
        self.assertIn("gen_progress_html", data)

    def test_generate_requires_loaded_data(self):
        rv = self.client.post(
            "/generate",
            headers={"X-Requested-With": "Schedulix"},
        )
        self.assertEqual(rv.status_code, 400)
        self.assertIn("No courses loaded", rv.get_json()["error"])


class AppRouteAppendDuplicateTests(unittest.TestCase):
    def setUp(self):
        _fresh_state()
        self.client = app.test_client()
        app.config["TESTING"] = True

    def test_upload_courses_append_skips_duplicate_ids(self):
        existing = Course(
            "Calculus 1", "83112", "Dr. Erez",
            [Program("83101", 1, "FALL", "Obligatory")], "Exam",
        )
        state["courses"] = [existing]
        rv = self.client.post(
            "/upload/courses",
            data={
                "file": (BytesIO(COURSE_RECORD.encode("utf-8")), "courses.txt"),
                "mode": "append",
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(rv.status_code, 302)
        self.assertEqual(len(state["courses"]), 1)
        self.assertEqual(state["courses"][0].course_id, "83112")


if __name__ == "__main__":
    unittest.main()
