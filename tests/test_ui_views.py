import unittest
import sys
import os
from datetime import datetime

"""They test the new UI screens that the requirements ask for: 
input screen, output screen, calendar configuration, program selection,
file loading, browsing/exporting interface, and usability improvements."""

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ui.views import (
    render_page,
    format_generate_result,
    render_gen_history_html,
)


class TestUIViews(unittest.TestCase):

    def test_input_page_renders_basic_layout(self):
        ctx = {
            "screen": "input",
            "courses_count": 0,
            "periods_count": 0,
            "selected_programs": [],
            "programs": [],
        }

        html = render_page(ctx)

        self.assertIn("Schedulix", html)
        self.assertIn("Input", html)
        self.assertIn("File Loading", html)
        self.assertIn("Courses File", html)
        self.assertIn("Dates File", html)
        self.assertIn("Study Program Selection", html)
        self.assertIn("Generate Schedules", html)

    def test_input_page_shows_program_cards(self):
        ctx = {
            "screen": "input",
            "courses_count": 2,
            "periods_count": 1,
            "selected_programs": [],
            "programs": [
                {"id": "83101", "name": "Computer Engineering"},
                {"id": "83102", "name": "Electrical Engineering"},
            ],
        }

        html = render_page(ctx)

        self.assertIn("Computer Engineering", html)
        self.assertIn("Electrical Engineering", html)
        self.assertIn('data-prog-id="83101"', html)
        self.assertIn('data-prog-id="83102"', html)

    def test_input_page_shows_selected_program_count(self):
        ctx = {
            "screen": "input",
            "courses_count": 2,
            "periods_count": 1,
            "selected_programs": ["83101", "83102"],
            "programs": [
                {"id": "83101", "name": "Computer Engineering"},
                {"id": "83102", "name": "Electrical Engineering"},
            ],
        }

        html = render_page(ctx)

        self.assertIn('id="sel-count"', html)
        self.assertIn(">2</span> / 5", html)

    def test_input_page_empty_program_state(self):
        ctx = {
            "screen": "input",
            "courses_count": 0,
            "periods_count": 0,
            "selected_programs": [],
            "programs": [],
        }

        html = render_page(ctx)

        self.assertIn("Load a courses file first", html)

    def test_calendar_page_renders_basic_layout(self):
        ctx = {
            "screen": "calendar",
            "aleph_periods": [],
            "bet_periods": [],
        }

        html = render_page(ctx)

        self.assertIn("Calendar", html)
        self.assertIn("Holiday presets", html)
        self.assertIn("Rosh Hashana", html)
        self.assertIn("Yom Kippur", html)
        self.assertIn("Sukkot", html)
        self.assertIn("MOED ALEPH", html)
        self.assertIn("MOED BET", html)

    def test_calendar_page_empty_periods(self):
        ctx = {
            "screen": "calendar",
            "aleph_periods": [],
            "bet_periods": [],
        }

        html = render_page(ctx)

        self.assertIn("No Moed Aleph periods found", html)
        self.assertIn("No Moed Bet periods found", html)

    def test_calendar_page_with_period(self):
        ctx = {
            "screen": "calendar",
            "aleph_periods": [
                {
                    "semester": "FALL",
                    "moed": "Aleph",
                    "start": "2026-01-29",
                    "end": "2026-01-31",
                    "all_dates": ["2026-01-29", "2026-01-30", "2026-01-31"],
                    "available": ["2026-01-29", "2026-01-31"],
                    "start_shift": 0,
                    "end_shift": 0,
                }
            ],
            "bet_periods": [],
        }

        html = render_page(ctx)

        self.assertIn("FALL", html)
        self.assertIn("Available", html)
        self.assertIn("Excluded", html)
        self.assertIn("January 2026", html)

    def test_output_page_renders_basic_layout(self):
        ctx = {
            "screen": "output",
            "schedule": None,
            "aleph_page": 0,
            "bet_page": 0,
            "aleph_total": 0,
            "bet_total": 0,
        }

        html = render_page(ctx)

        self.assertIn("Output", html)
        self.assertIn("Schedulix", html)

    def test_flash_message_is_rendered(self):
        ctx = {
            "screen": "input",
            "flash": {
                "type": "ok",
                "msg": "Saved successfully",
            },
            "courses_count": 0,
            "periods_count": 0,
            "selected_programs": [],
            "programs": [],
        }

        html = render_page(ctx)

        self.assertIn("Saved successfully", html)
        self.assertIn("toast", html)

    def test_format_generate_result_with_counts(self):
        result = format_generate_result(3, 2)

        self.assertEqual(result, "✓ 3 Aleph · 2 Bet schedules")

    def test_format_generate_result_empty(self):
        result = format_generate_result(0, 0)

        self.assertEqual(result, "")

    def test_generation_history_empty(self):
        html = render_gen_history_html([])

        self.assertEqual(html, "")

    def test_generation_history_with_current_and_restore(self):
        history = [
            {
                "ts": datetime(2026, 1, 29, 10, 30),
                "aleph_count": 3,
                "bet_count": 2,
                "programs": ["83101"],
            },
            {
                "ts": datetime(2026, 1, 29, 11, 0),
                "aleph_count": 4,
                "bet_count": 1,
                "programs": ["83101", "83102"],
            },
        ]

        html = render_gen_history_html(history)

        self.assertIn("Generation history", html)
        self.assertIn("current", html)
        self.assertIn("Restore", html)
        self.assertIn("3 Aleph", html)
        self.assertIn("4 Aleph", html)
        self.assertIn("83101", html)
        self.assertIn("83102", html)

    def test_html_escaping_prevents_script_injection(self):
        ctx = {
            "screen": "input",
            "courses_count": 1,
            "periods_count": 1,
            "selected_programs": [],
            "programs": [
                {
                    "id": "83101",
                    "name": "<script>alert('bad')</script>",
                }
            ],
        }

        html = render_page(ctx)

        self.assertNotIn("<script>alert('bad')</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_page_includes_custom_stylesheet_and_fonts(self):
        ctx = {
            "screen": "input",
            "courses_count": 0,
            "periods_count": 0,
            "selected_programs": [],
            "programs": [],
        }

        html = render_page(ctx)

        self.assertIn('/static/style.css', html)
        self.assertIn('fonts.googleapis.com', html)
        self.assertIn('Space+Mono', html)
        self.assertIn('DM+Sans', html)

    def test_page_includes_logo_and_branding(self):
        ctx = {
            "screen": "input",
            "courses_count": 0,
            "periods_count": 0,
            "selected_programs": [],
            "programs": [],
        }

        html = render_page(ctx)

        self.assertIn("Schedulix", html)
        self.assertIn("Version 34.0", html)
        self.assertIn("Schedulix logo", html)
        self.assertIn("/public/SchedulixLogo.jpeg", html)


    def test_main_layout_contains_sidebar_topbar_and_content(self):
        ctx = {
            "screen": "input",
            "courses_count": 0,
            "periods_count": 0,
            "selected_programs": [],
            "programs": [],
        }

        html = render_page(ctx)

        self.assertIn('class="shell"', html)
        self.assertIn('class="sidebar"', html)
        self.assertIn('class="main"', html)
        self.assertIn('class="topbar"', html)
        self.assertIn('class="content"', html)


    def test_navigation_links_for_all_main_screens_exist(self):
        ctx = {
            "screen": "input",
            "courses_count": 0,
            "periods_count": 0,
            "selected_programs": [],
            "programs": [],
        }

        html = render_page(ctx)

        self.assertIn("Input", html)
        self.assertIn("Calendar", html)
        self.assertIn("Output", html)
        self.assertIn("/?screen=input", html)
        self.assertIn("/?screen=calendar", html)
        self.assertIn("/?screen=output", html)

    def test_ui_handles_very_long_program_name(self):
        long_name = "Very Long Engineering Program Name " * 20

        ctx = {
            "screen": "input",
            "courses_count": 1,
            "periods_count": 1,
            "selected_programs": [],
            "programs": [
                {"id": "99999", "name": long_name},
            ],
        }

        html = render_page(ctx)

        self.assertIn("99999", html)
        self.assertIn("Very Long Engineering Program Name", html)
        self.assertIn('class="program-card', html)


    def test_ui_escapes_special_characters_in_program_names(self):
        ctx = {
            "screen": "input",
            "courses_count": 1,
            "periods_count": 1,
            "selected_programs": [],
            "programs": [
                {"id": "83101", "name": "AI & Data <Engineering>"},
            ],
        }

        html = render_page(ctx)

        self.assertIn("AI &amp; Data", html)
        self.assertIn("&lt;Engineering&gt;", html)
        self.assertNotIn("AI & Data <Engineering>", html)
        
    def test_input_page_has_courses_upload_form(self):
        ctx = {
            "screen": "input",
            "courses_count": 0,
            "periods_count": 0,
            "selected_programs": [],
            "programs": [],
        }

        html = render_page(ctx)

        self.assertIn('action="/upload/courses"', html)
        self.assertIn('enctype="multipart/form-data"', html)
        self.assertIn('type="file"', html)
        self.assertIn('name="file"', html)
        self.assertIn('accept=".txt"', html)


    def test_input_page_has_periods_upload_form(self):
        ctx = {
            "screen": "input",
            "courses_count": 0,
            "periods_count": 0,
            "selected_programs": [],
            "programs": [],
        }

        html = render_page(ctx)

        self.assertIn('action="/upload/periods"', html)
        self.assertIn("Dates File", html)
        self.assertIn('accept=".txt"', html)


    def test_input_page_has_overwrite_and_append_modes(self):
        ctx = {
            "screen": "input",
            "file_mode": "overwrite",
            "courses_count": 0,
            "periods_count": 0,
            "selected_programs": [],
            "programs": [],
        }

        html = render_page(ctx)

        self.assertIn('value="overwrite"', html)
        self.assertIn('value="append"', html)
        self.assertIn("Overwrite", html)
        self.assertIn("Append", html)


    def test_upload_forms_include_current_file_mode_hidden_field(self):
        ctx = {
            "screen": "input",
            "file_mode": "append",
            "courses_count": 0,
            "periods_count": 0,
            "selected_programs": [],
            "programs": [],
        }

        html = render_page(ctx)

        self.assertIn('name="mode"', html)
        self.assertIn('value="append"', html)
    
    def test_input_page_displays_five_selected_programs_limit(self):
        ctx = {
            "screen": "input",
            "courses_count": 10,
            "periods_count": 2,
            "selected_programs": ["83101", "83102", "83104", "83107", "83108"],
            "programs": [
                {"id": "83101", "name": "Computer Engineering"},
                {"id": "83102", "name": "Electrical Engineering"},
                {"id": "83104", "name": "Industrial Engineering"},
                {"id": "83107", "name": "Data Engineering"},
                {"id": "83108", "name": "Software Engineering"},
            ],
        }

        html = render_page(ctx)

        self.assertIn(">5</span> / 5", html)


    def test_all_selected_program_cards_are_marked_selected(self):
        ctx = {
            "screen": "input",
            "courses_count": 10,
            "periods_count": 2,
            "selected_programs": ["83101", "83102"],
            "programs": [
                {"id": "83101", "name": "Computer Engineering"},
                {"id": "83102", "name": "Electrical Engineering"},
            ],
        }

        html = render_page(ctx)

        self.assertIn('data-prog-id="83101"', html)
        self.assertIn('data-prog-id="83102"', html)
        self.assertGreaterEqual(html.count("selected"), 2)
        
        
if __name__ == "__main__":
    unittest.main()