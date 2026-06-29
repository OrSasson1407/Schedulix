"""
app.py — Schedulix V2 (Python + CSS only)

All UI is built in Python (src/ui/views.py) and styled with static/style.css.
No separate HTML/JS frontend and no REST API for the browser — only form POSTs and links.

Run:  python app.py
"""

import os
import sys
import pickle
import hashlib
import json
import threading
import copy
import time
from datetime import datetime, timedelta

from urllib.parse import urlencode

from flask import Flask, request, redirect, Response, send_from_directory, jsonify

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.parser.CourseParser import CourseParser
from src.parser.PeriodParser import PeriodParser
from src.scheduler.BacktrackScheduler import BacktrackScheduler
from src.scheduler.SchedulerSorter import SORT_CRITERIA, METRIC_KEYS, sort_schedules
from src.scheduler.whatif import WhatIfEngine
from src.models.ExamPeriod import ExamPeriod
from src.models.Schedule import Schedule
from src.models.Constraints import SchedulingConstraints
from src.ui.views import (
    render_page,
    PROGRAM_NAMES,
    HOLIDAY_PRESETS,
    format_generate_result,
    render_gen_history_html,
    render_program_grid_html,
    render_output_live,
)

app = Flask(__name__, static_folder="static")

# ── In-memory state ──────────────────────────────────────────────────────────
state = {
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
    "pagination": {}, # Tracks saved pagination per semester
    # User-configurable hard constraints (5 toggles + their k parameters).
    "constraints": SchedulingConstraints.default_config(),
    # Ordered list of sort criteria keys (primary first). Empty = generation order.
    "sort_criteria": [],
    # Exams locked by the user: set of "semester|moed_key|course_id".
    "locked_exams": set(),
    # User-defined holiday/event exclusions (for display on the calendar screen).
    "custom_events": [],
    # Undo stack of manual post-generation edits (drag-and-drop applies).
    "edit_history": [],
    # Background generation job status (updated incrementally while running).
    "gen_job": {
        "running": False,
        "done": False,
        "timed_out": False,
        "error": None,
    },
}

CACHE_PATH = os.path.join(PROJECT_ROOT, "data", ".cache.pkl")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
PUBLIC_DIR = os.path.join(PROJECT_ROOT, "public")
_generation_lock = threading.Lock()


# ── Helpers ──────────────────────────────────────────────────────────────────

def file_hash(path):
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except OSError:
        return None


def save_cache():
    try:
        with open(CACHE_PATH, "wb") as f:
            pickle.dump(
                {
                    k: state[k]
                    for k in ("courses", "periods", "courses_file_hash", "periods_file_hash")
                },
                f,
            )
    except Exception as e:
        print(f"[Cache] Save failed: {e}")


def load_cache():
    try:
        with open(CACHE_PATH, "rb") as f:
            data = pickle.load(f)
        state.update(data)
        print("[Cache] Loaded from cache.")
        return True
    except OSError:
        return False


def set_flash(msg, kind="ok"):
    state["flash"] = {"msg": msg, "type": kind}


def pop_flash():
    flash = state.get("flash")
    state["flash"] = None
    return flash


def read_scroll_y():
    try:
        return max(0, int(request.form.get("scroll_y", 0)))
    except (TypeError, ValueError):
        return 0


def redirect_screen(screen, anchor=None, scroll=None, **params):
    q = {"screen": screen, **{k: v for k, v in params.items() if v is not None}}
    if scroll is None:
        scroll = read_scroll_y()
    if scroll is not None and int(scroll) > 0:
        q["scroll"] = int(scroll)
    url = "/?" + urlencode(q)
    if anchor:
        url += "#" + anchor.lstrip("#")
    return redirect(url)


def output_live_payload():
    """HTML fragments for the current Output screen (AJAX refresh without reload)."""
    sem = state.get("active_semester", "")
    query = f"/?screen=output&semester_view={sem}" if sem else "/?screen=output"
    with app.test_request_context(query):
        ctx = build_context("output")
    ctx["gen_running"] = False
    return render_output_live(ctx)


def input_fingerprint():
    """Stable key for the current courses, periods, and calendar overrides."""
    overrides_blob = json.dumps(state.get("period_overrides", {}), sort_keys=True)
    overrides_hash = hashlib.md5(overrides_blob.encode()).hexdigest()
    return (
        state.get("courses_file_hash"),
        state.get("periods_file_hash"),
        overrides_hash,
    )


def snapshot_schedules(schedules):
    """Copy schedule assignments so a history entry can restore prior results."""
    copies = []
    for sched in schedules:
        s = Schedule()
        s.assignments = dict(sched.assignments)
        copies.append(s)
    return copies


def relevant_gen_history():
    """History entries that match the currently loaded input files and calendar."""
    fp = input_fingerprint()
    result = []
    for i, entry in enumerate(state["gen_history"]):
        if entry.get("input_fingerprint") == fp:
            tagged = dict(entry)
            tagged["_index"] = i
            result.append(tagged)
    return result


def clear_generated_results():
    """Clear schedules, history, and manual edits after course/period data changes."""
    state["gen_history"] = []
    state["aleph_schedules"] = []
    state["bet_schedules"] = []
    state["edit_history"] = []
    state["locked_exams"] = set()
    state["pagination"] = {}
    state["gen_job"] = {
        "running": False,
        "done": False,
        "timed_out": False,
        "error": None,
    }


def append_gen_history(aleph_count, bet_count, timed_out):
    state["gen_history"].append(
        {
            "ts": datetime.now(),
            "programs": list(state["selected_programs"]),
            "aleph_count": aleph_count,
            "bet_count": bet_count,
            "timed_out": timed_out,
            "input_fingerprint": input_fingerprint(),
            "aleph_schedules": snapshot_schedules(state["aleph_schedules"]),
            "bet_schedules": snapshot_schedules(state["bet_schedules"]),
            "period_overrides": copy.deepcopy(state.get("period_overrides", {})),
        }
    )
    if len(state["gen_history"]) > 2:
        state["gen_history"].pop(0)


def get_effective_period(period):
    key = f"{period.semester}|{period.moed}"
    ov = state["period_overrides"].get(key, {})
    start = period.start_date + timedelta(days=ov.get("start_shift", 0))
    end = period.end_date + timedelta(days=ov.get("end_shift", 0))

    extra_excluded = set()
    for d in ov.get("excluded_extra", []):
        try:
            extra_excluded.add(datetime.strptime(d, "%Y-%m-%d").date())
        except ValueError:
            pass

    reincluded = set()
    for d in ov.get("reincluded", []):
        try:
            reincluded.add(datetime.strptime(d, "%Y-%m-%d").date())
        except ValueError:
            pass

    orig_excluded = {d for d in period.excluded_dates if d not in reincluded}
    merged = list(orig_excluded | extra_excluded)

    return ExamPeriod(
        semester=period.semester,
        moed=period.moed,
        start_date=start.strftime("%d-%m-%Y"),
        end_date=end.strftime("%d-%m-%Y"),
        excluded_dates=[
            datetime.combine(d, datetime.min.time())
            if hasattr(d, "year") and not hasattr(d, "hour")
            else d
            for d in merged
        ],
    )


def period_to_dict(period):
    key = f"{period.semester}|{period.moed}"
    ov = state["period_overrides"].get(key, {})
    effective = get_effective_period(period)
    available = [d.date.strftime("%Y-%m-%d") for d in effective.get_available_dates()]
    all_dates = []
    cur = effective.start_date
    while cur <= effective.end_date:
        all_dates.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return {
        "semester": period.semester,
        "moed": period.moed,
        "start": effective.start_date.strftime("%Y-%m-%d"),
        "end": effective.end_date.strftime("%Y-%m-%d"),
        "available": available,
        "all_dates": all_dates,
        "excluded": [d for d in all_dates if d not in available],
        "start_shift": ov.get("start_shift", 0),
        "end_shift": ov.get("end_shift", 0),
    }


def schedule_to_entries(schedule):
    entries = []
    for (course, moed), exam_date in schedule.assignments.items():
        req = course.programs[0].requirement if course.programs else "Unknown"
        prog_ids = list({p.program_id for p in course.programs})
        entries.append(
            {
                "date": exam_date.date.strftime("%Y-%m-%d"),
                "course_id": course.course_id,
                "course_name": course.name,
                "instructor": course.instructor,
                "semester": exam_date.semester,
                "moed": exam_date.moed,
                "requirement": req,
                "programs": prog_ids,
            }
        )
    entries.sort(key=lambda x: x["date"])
    return entries


def list_programs():
    programs = {}
    for course in state["courses"]:
        for p in course.programs:
            programs[p.program_id] = p.program_id
    return [
        {"id": pid, "name": PROGRAM_NAMES.get(pid, f"Program {pid}")}
        for pid in sorted(programs.keys())
    ]


def program_courses(prog_id, year_filter=None, sem_filter=None):
    courses = []
    for course in state["courses"]:
        for p in course.programs:
            if p.program_id != prog_id:
                continue
            if year_filter and str(p.year) != year_filter:
                continue
            if sem_filter and p.semester != sem_filter:
                continue
            courses.append(
                {
                    "course_id": course.course_id,
                    "name": course.name,
                    "instructor": course.instructor,
                    "year": p.year,
                    "semester": p.semester,
                    "requirement": p.requirement,
                    "evaluation": course.evaluation,
                }
            )
    courses.sort(key=lambda x: (x["year"], x["semester"], x["name"]))
    return courses


def _page_index(raw, total):
    try:
        page = int(raw)
    except (TypeError, ValueError):
        return 0
    if page >= 1:
        page -= 1
    if total <= 0:
        return 0
    return max(0, min(page, total - 1))


def build_context(screen=None):
    screen = screen or request.args.get("screen", "input")
    aleph_total = len(state["aleph_schedules"])
    bet_total = len(state["bet_schedules"])

    courses_count = len(state["courses"])
    periods_count = len(state["periods"])

    if courses_count:
        courses_status = f"✓ {courses_count} loaded"
    else:
        courses_status = "Not loaded"
    if periods_count:
        periods_status = f"✓ {periods_count} loaded"
    else:
        periods_status = "Not loaded"

    gen_result = ""
    if aleph_total or bet_total:
        gen_result = f"✓ {aleph_total} Aleph · {bet_total} Bet schedules"

    if request.args.get("active_aleph") is not None:
        try:
            state["active_aleph"] = int(request.args.get("active_aleph", 0))
        except ValueError:
            pass
    if request.args.get("active_bet") is not None:
        try:
            state["active_bet"] = int(request.args.get("active_bet", 0))
        except ValueError:
            pass

    scroll_y = 0
    if request.args.get("scroll") is not None:
        try:
            scroll_y = max(0, int(request.args.get("scroll")))
        except (TypeError, ValueError):
            pass

    ctx = {
        "screen": screen,
        "content_scroll_y": scroll_y,
        "flash": pop_flash(),
        "file_mode": state["file_mode"],
        "courses_count": courses_count,
        "periods_count": periods_count,
        "courses_status": courses_status,
        "periods_status": periods_status,
        "selected_programs": list(state["selected_programs"]),
        "programs": list_programs(),
        "generate_result": gen_result,
        "gen_history": relevant_gen_history(),
        "aleph_periods": [period_to_dict(p) for p in state["periods"] if p.moed == "Aleph"],
        "bet_periods": [period_to_dict(p) for p in state["periods"] if p.moed == "Bet"],
        "active_aleph": state["active_aleph"],
        "active_bet": state["active_bet"],
        "preset_target_aleph": state["preset_target_aleph"],
        "preset_target_bet": state["preset_target_bet"],
        "aleph_total": aleph_total,
        "bet_total": bet_total,
        "schedule": None,
        "constraints": state.get("constraints", SchedulingConstraints.default_config()),
        "sort_options": SORT_CRITERIA,
        "sort_criteria": list(state.get("sort_criteria", [])),
        "can_undo": len(state.get("edit_history", [])) > 0,
        "edit_count": len(state.get("edit_history", [])),
        "custom_events": list(state.get("custom_events", [])),
        "gen_running": bool(state.get("gen_job", {}).get("running"))
        or request.args.get("generating") == "1",
    }

    drilldown_id = request.args.get("drilldown")
    if drilldown_id and screen == "input":
        name = PROGRAM_NAMES.get(drilldown_id, f"Program {drilldown_id}")
        ctx["drilldown"] = {
            "prog_id": drilldown_id,
            "name": name,
            "year_filter": request.args.get("year", ""),
            "sem_filter": request.args.get("semester", ""),
            "courses": program_courses(
                drilldown_id,
                request.args.get("year") or None,
                request.args.get("semester") or None,
            ),
        }

    # Semester switching
    semesters = all_semesters()
    active_sem = request.args.get("semester_view", state.get("active_semester", ""))
    if active_sem and active_sem in semesters:
        state["active_semester"] = active_sem
    elif semesters and state.get("active_semester", "") not in semesters:
        state["active_semester"] = semesters[0]
    active_sem = state.get("active_semester", "")

    sem_aleph, sem_bet = schedules_for_semester(active_sem) if active_sem else (state["aleph_schedules"], state["bet_schedules"])
    sem_aleph_total = len(sem_aleph)
    sem_bet_total   = len(sem_bet)
    
    # Track Pagination per Semester
    if "pagination" not in state:
        state["pagination"] = {}
    if active_sem and active_sem not in state["pagination"]:
        state["pagination"][active_sem] = {"aleph": 0, "bet": 0}

    sem_aleph_page = 0
    sem_bet_page = 0

    if active_sem:
        req_a = request.args.get("aleph_page")
        req_b = request.args.get("bet_page")

        if req_a is not None:
            state["pagination"][active_sem]["aleph"] = _page_index(req_a, sem_aleph_total)
        else:
            state["pagination"][active_sem]["aleph"] = min(state["pagination"][active_sem]["aleph"], max(0, sem_aleph_total - 1)) if sem_aleph_total else 0

        if req_b is not None:
            state["pagination"][active_sem]["bet"] = _page_index(req_b, sem_bet_total)
        else:
            state["pagination"][active_sem]["bet"] = min(state["pagination"][active_sem]["bet"], max(0, sem_bet_total - 1)) if sem_bet_total else 0

        sem_aleph_page = state["pagination"][active_sem]["aleph"]
        sem_bet_page   = state["pagination"][active_sem]["bet"]

    ctx["semesters"]        = semesters
    ctx["active_semester"]  = active_sem
    ctx["aleph_total"]      = sem_aleph_total
    ctx["bet_total"]        = sem_bet_total
    ctx["aleph_page"]       = sem_aleph_page
    ctx["bet_page"]         = sem_bet_page

    if screen == "output" and (sem_aleph_total or sem_bet_total):
        aleph_entries = (
            schedule_to_entries(sem_aleph[sem_aleph_page]) if sem_aleph_total else []
        )
        bet_entries = (
            schedule_to_entries(sem_bet[sem_bet_page]) if sem_bet_total else []
        )
        locked = state.get("locked_exams", set())
        for e in aleph_entries:
            e["locked"] = f"{active_sem}|aleph|{e['course_id']}" in locked
        for e in bet_entries:
            e["locked"] = f"{active_sem}|bet|{e['course_id']}" in locked
        ctx["schedule"] = {
            "semester": active_sem,
            "aleph_entries": aleph_entries,
            "bet_entries": bet_entries,
        }

    return ctx


def toggle_day(semester, moed, date_str):
    key = f"{semester}|{moed}"
    if key not in state["period_overrides"]:
        state["period_overrides"][key] = {
            "excluded_extra": [],
            "reincluded": [],
            "start_shift": 0,
            "end_shift": 0,
        }
    ov = state["period_overrides"][key]
    period = next(
        (p for p in state["periods"] if p.semester == semester and p.moed == moed), None
    )
    if not period:
        return None
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None
    originally_excluded = d in period.excluded_dates
    currently_extra = date_str in ov["excluded_extra"]
    currently_rein = date_str in ov["reincluded"]
    if originally_excluded:
        if currently_rein:
            ov["reincluded"].remove(date_str)
            return "re-excluded"
        ov["reincluded"].append(date_str)
        return "re-included"
    if currently_extra:
        ov["excluded_extra"].remove(date_str)
        return "re-included"
    ov["excluded_extra"].append(date_str)
    return "excluded"


def run_generation():
    selected_set = set(state["selected_programs"])

    def _make_filtered():
        filtered = []
        for course in state["courses"]:
            matching = [p for p in course.programs if p.program_id in selected_set]
            if matching:
                c = copy.copy(course)
                c.programs = matching
                filtered.append(c)
        return filtered

    effective_periods = [get_effective_period(p) for p in state["periods"]]
    aleph_periods = [p for p in effective_periods if p.moed == "Aleph"]
    bet_periods = [p for p in effective_periods if p.moed == "Bet"]
    state["aleph_schedules"] = []
    state["bet_schedules"] = []
    # A fresh run resets any manual edits / locks tied to the previous results.
    state["edit_history"] = []
    state["locked_exams"] = set()

    # Build the active hard-constraint configuration once per generation run.
    constraints = SchedulingConstraints(state.get("constraints"))

    def _run_aleph():
        sched = BacktrackScheduler()
        for s in sched.generate(_make_filtered(), aleph_periods, constraints):
            if s.assignments:
                state["aleph_schedules"].append(s)

    def _run_bet():
        sched = BacktrackScheduler()
        for s in sched.generate(_make_filtered(), bet_periods, constraints):
            if s.assignments:
                state["bet_schedules"].append(s)

    def _infer_semesters():
        sems = set()
        for s in state["aleph_schedules"] + state["bet_schedules"]:
            for (course, moed), exam_date in s.assignments.items():
                sems.add(exam_date.semester)
        return sorted(sems)

    hard_timeout = BacktrackScheduler.TIME_LIMIT_SECONDS + 1
    with _generation_lock:
        t_a = threading.Thread(target=_run_aleph, daemon=True)
        t_b = threading.Thread(target=_run_bet, daemon=True)
        t_a.start()
        t_b.start()
        deadline = time.time() + hard_timeout
        while (t_a.is_alive() or t_b.is_alive()) and time.time() < deadline:
            job = state.get("gen_job")
            if job and job.get("running"):
                job["aleph_count"] = len(state["aleph_schedules"])
                job["bet_count"] = len(state["bet_schedules"])
            time.sleep(0.1)
        timed_out = t_a.is_alive() or t_b.is_alive()

    sems = _infer_semesters()
    if sems and state["active_semester"] not in sems:
        state["active_semester"] = sems[0]

    # Apply the current sort preferences to the freshly generated results.
    apply_sort()
    return len(state["aleph_schedules"]), len(state["bet_schedules"]), timed_out


def _run_generation_job():
    """Run generation in a background thread; updates gen_job for live polling."""
    state["gen_job"] = {
        "running": True,
        "done": False,
        "timed_out": False,
        "aleph_count": 0,
        "bet_count": 0,
        "error": None,
        "flash": None,
    }
    try:
        aleph_count, bet_count, timed_out = run_generation()
        append_gen_history(aleph_count, bet_count, timed_out)
        flash_msg, flash_type = _generation_flash_message(aleph_count, bet_count, timed_out)
        state["gen_job"].update(
            {
                "running": False,
                "done": True,
                "timed_out": timed_out,
                "aleph_count": aleph_count,
                "bet_count": bet_count,
                "flash": {"msg": flash_msg, "type": flash_type},
            }
        )
    except Exception as exc:
        state["gen_job"].update(
            {
                "running": False,
                "done": True,
                "error": str(exc),
                "flash": {"msg": str(exc), "type": "err"},
            }
        )


def apply_sort():
    """
    Re-orders the in-memory Aleph and Bet schedule lists according to the current
    sort criteria. Runs purely on the existing results — it never re-generates.
    """
    criteria = state.get("sort_criteria", [])
    state["aleph_schedules"] = sort_schedules(state["aleph_schedules"], criteria)
    state["bet_schedules"] = sort_schedules(state["bet_schedules"], criteria)


def schedules_for_semester(sem):
    """Return aleph/bet schedules that belong to a given semester."""
    def _matches(sched, sem):
        for (course, moed), exam_date in sched.assignments.items():
            if exam_date.semester == sem:
                return True
        return False
    aleph = [s for s in state["aleph_schedules"] if _matches(s, sem)]
    bet   = [s for s in state["bet_schedules"]   if _matches(s, sem)]
    return aleph, bet


def all_semesters():
    sems = set()
    for s in state["aleph_schedules"] + state["bet_schedules"]:
        for (course, moed), exam_date in s.assignments.items():
            sems.add(exam_date.semester)
    return sorted(sems)


def apply_holiday_preset(preset_key, target_aleph, target_bet):
    preset = HOLIDAY_PRESETS.get(preset_key)
    if not preset:
        return 0
    dates_to_exclude = []
    for from_d, to_d in preset["ranges"]:
        d = datetime.strptime(from_d, "%Y-%m-%d")
        end = datetime.strptime(to_d, "%Y-%m-%d")
        while d <= end:
            dates_to_exclude.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)

    periods = []
    if target_aleph:
        periods.extend(period_to_dict(p) for p in state["periods"] if p.moed == "Aleph")
    if target_bet:
        periods.extend(period_to_dict(p) for p in state["periods"] if p.moed == "Bet")

    excluded = 0
    for period in periods:
        avail_set = set(period["available"])
        all_set = set(period["all_dates"])
        for date in dates_to_exclude:
            if date not in all_set or date not in avail_set:
                continue
            toggle_day(period["semester"], period["moed"], date)
            excluded += 1
    return excluded


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


@app.route("/public/<path:filename>")
def public_files(filename):
    return send_from_directory(PUBLIC_DIR, filename)


@app.route("/")
def index():
    ctx = build_context()
    return render_page(ctx)


@app.route("/settings", methods=["POST"])
def update_settings():
    """Persists the 5 hard-constraint toggles and their integer k parameters."""
    config = SchedulingConstraints.default_config()
    for key in SchedulingConstraints.KEYS:
        config[key]["enabled"] = request.form.get(f"{key}_enabled") == "1"
        raw_k = request.form.get(f"{key}_k")
        if raw_k is not None and str(raw_k).strip() != "":
            try:
                config[key]["k"] = int(raw_k)
            except ValueError:
                pass

    # Normalise through the model so k values are clamped to their valid bounds.
    state["constraints"] = SchedulingConstraints(config).to_dict()
    set_flash("Constraint settings saved", "ok")
    return redirect_screen("settings")


@app.route("/sort", methods=["POST"])
def update_sort():
    """
    Updates the multi-criteria sort order and instantly re-orders the existing
    in-memory schedules (no re-generation). Criteria arrive as ordered priority
    slots: sort_1 (primary), sort_2 (secondary), sort_3 (tertiary), ...
    """
    criteria = []
    slot = 1
    while True:
        val = request.form.get(f"sort_{slot}")
        if val is None:
            break
        val = val.strip()
        if val and val in METRIC_KEYS and val not in criteria:
            criteria.append(val)
        slot += 1

    state["sort_criteria"] = criteria
    apply_sort()
    # Order changed, so reset pagination to show the new top-ranked schedules.
    state["pagination"] = {}

    if criteria:
        set_flash(f"Sorted by {len(criteria)} criterion(s)", "ok")
    else:
        set_flash("Sorting cleared — showing generation order", "ok")

    if _ajax_request():
        flash_msg = (
            f"Sorted by {len(criteria)} criterion(s)" if criteria
            else "Sorting cleared — showing generation order"
        )
        return jsonify({
            "ok": True,
            "flash": {"msg": flash_msg, "type": "ok"},
            **output_live_payload(),
        })
    return redirect_screen("output", semester_view=state.get("active_semester", ""))


def _displayed_schedule(scheds, active_sem, moed_key):
    page = state.get("pagination", {}).get(active_sem, {}).get(moed_key, 0)
    if not scheds or page >= len(scheds):
        return None
    return scheds[page]


def _companion_dates(companion_schedule):
    """Maps course_id -> exam date (date object) from the other moed's schedule."""
    out = {}
    if companion_schedule:
        for (course, _moed), exam_date in companion_schedule.assignments.items():
            raw = exam_date.date
            out[course.course_id] = raw.date() if hasattr(raw, "date") else raw
    return out


def _active_whatif_engine(moed_key):
    """
    Builds a WhatIfEngine for the schedule currently displayed on the Output screen
    for the given moed ('aleph'/'bet'). Returns (engine, schedule) or None.
    """
    active_sem = state.get("active_semester", "")
    if active_sem:
        aleph, bet = schedules_for_semester(active_sem)
    else:
        aleph, bet = state["aleph_schedules"], state["bet_schedules"]

    if moed_key == "aleph":
        scheds, moed, companion_key = aleph, "Aleph", "bet"
        companion_scheds = bet
    else:
        scheds, moed, companion_key = bet, "Bet", "aleph"
        companion_scheds = aleph

    schedule = _displayed_schedule(scheds, active_sem, moed_key)
    if schedule is None:
        return None

    period = next(
        (p for p in state["periods"] if p.moed == moed and p.semester == active_sem), None
    ) or next((p for p in state["periods"] if p.moed == moed), None)
    if not period:
        return None

    available = get_effective_period(period).get_available_dates()
    constraints = SchedulingConstraints(state.get("constraints"))

    companion = _companion_dates(_displayed_schedule(companion_scheds, active_sem, companion_key))
    locked = {
        key.split("|", 2)[2]
        for key in state.get("locked_exams", set())
        if key.startswith(f"{active_sem}|{moed_key}|")
    }

    engine = WhatIfEngine(
        schedule, available, moed, constraints,
        companion_dates=companion, locked=locked,
    )
    return engine, schedule


def _whatif_params():
    moed_key = (request.form.get("moed") or "aleph").lower()
    if moed_key not in ("aleph", "bet"):
        moed_key = "aleph"
    return moed_key, request.form.get("course_id", ""), request.form.get("new_date", "")


@app.route("/whatif/preview", methods=["POST"])
def whatif_preview():
    """Instant 'domino effect' view for a hypothetical drag (no changes applied)."""
    moed_key, course_id, new_date = _whatif_params()
    built = _active_whatif_engine(moed_key)
    if not built:
        return jsonify({"ok": False, "error": "No active schedule to edit"}), 400
    engine, _ = built
    try:
        report = engine.preview(course_id, new_date)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, **report.to_dict()})


@app.route("/whatif/resolve", methods=["POST"])
def whatif_resolve():
    """Returns the before/after violations and the minimal cascade plan."""
    moed_key, course_id, new_date = _whatif_params()
    built = _active_whatif_engine(moed_key)
    if not built:
        return jsonify({"ok": False, "error": "No active schedule to edit"}), 400
    engine, _ = built
    try:
        return jsonify(engine.resolve(course_id, new_date))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/whatif/apply", methods=["POST"])
def whatif_apply():
    """Commits the dragged move plus its resolved cascade onto the live schedule."""
    moed_key, course_id, new_date = _whatif_params()
    built = _active_whatif_engine(moed_key)
    if not built:
        return jsonify({"ok": False, "error": "No active schedule to edit"}), 400
    engine, schedule = built
    # Snapshot the schedule BEFORE mutating it so the change can be undone.
    snapshot = dict(schedule.assignments)
    try:
        result = engine.apply(course_id, new_date, schedule)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    state["edit_history"].append(
        {
            "schedule": schedule,
            "assignments": snapshot,
            "label": f"{course_id} → {new_date}",
            "ts": datetime.now(),
        }
    )

    moves = 1 + len(result.get("cascade", []))
    msg = f"Applied {moves} move(s)" + ("" if result["solved"] else " — issues remain")
    kind = "ok" if result["solved"] else "err"
    set_flash(msg, kind)
    result["ok"] = True
    result["can_undo"] = True
    result["flash"] = {"msg": msg, "type": kind}
    result.update(output_live_payload())
    return jsonify(result)


@app.route("/whatif/lock", methods=["POST"])
def whatif_lock():
    """Toggles the lock state of a single exam (locked exams cannot be moved)."""
    moed_key = (request.form.get("moed") or "aleph").lower()
    if moed_key not in ("aleph", "bet"):
        moed_key = "aleph"
    course_id = request.form.get("course_id", "")
    if not course_id:
        return jsonify({"ok": False, "error": "Missing course id"}), 400

    active_sem = state.get("active_semester", "")
    key = f"{active_sem}|{moed_key}|{course_id}"
    locked = state["locked_exams"]
    if key in locked:
        locked.discard(key)
        is_locked = False
    else:
        locked.add(key)
        is_locked = True
    return jsonify({"ok": True, "course_id": course_id, "locked": is_locked})


@app.route("/whatif/undo", methods=["POST"])
def whatif_undo():
    """Rolls back the most recent manual edit, one step at a time."""
    history = state["edit_history"]
    if not history:
        if _ajax_request():
            return jsonify({"ok": False, "error": "Nothing to undo"}), 400
        set_flash("Nothing to undo", "err")
        return redirect_screen("output", semester_view=state.get("active_semester", ""))

    entry = history.pop()
    entry["schedule"].assignments = entry["assignments"]
    flash_msg = f"Undid: {entry['label']}"
    set_flash(flash_msg, "ok")

    if _ajax_request():
        return jsonify({
            "ok": True,
            "remaining": len(history),
            "flash": {"msg": flash_msg, "type": "ok"},
            **output_live_payload(),
        })
    return redirect_screen("output", semester_view=state.get("active_semester", ""))


@app.route("/set_mode", methods=["POST"])
def set_mode():
    mode = request.form.get("mode", "overwrite")
    if mode in ("overwrite", "append"):
        state["file_mode"] = mode
    return redirect_screen("input", anchor="file-loading")


@app.route("/upload/courses", methods=["POST"])
def upload_courses():
    mode = request.form.get("mode", state["file_mode"])
    if "file" not in request.files or not request.files["file"].filename:
        set_flash("No file provided", "err")
        return redirect_screen("input", anchor="file-loading")
    path = os.path.join(DATA_DIR, "uploaded_courses.txt")
    request.files["file"].save(path)
    try:
        new_courses = CourseParser().parse(path)
        if mode == "append":
            existing_ids = {c.course_id for c in state["courses"]}
            state["courses"] += [c for c in new_courses if c.course_id not in existing_ids]
        else:
            state["courses"] = new_courses
            state["selected_programs"] = []
        state["courses_file_hash"] = file_hash(path)
        clear_generated_results()
        save_cache()
        msg = (
            f"Courses loaded — {len(state['courses'])} records. "
            "Generation history and schedules were cleared."
        )
        set_flash(msg, "ok")
        if _ajax_request():
            payload = _upload_status_payload()
            payload.update({"ok": True, "flash": {"msg": msg, "type": "ok"}})
            return jsonify(payload)
    except Exception as e:
        set_flash(str(e), "err")
        if _ajax_request():
            return jsonify({"ok": False, "error": str(e)}), 400
    return redirect_screen("input", anchor="program-selection")


@app.route("/upload/periods", methods=["POST"])
def upload_periods():
    mode = request.form.get("mode", state["file_mode"])
    if "file" not in request.files or not request.files["file"].filename:
        set_flash("No file provided", "err")
        return redirect_screen("input", anchor="file-loading")
    path = os.path.join(DATA_DIR, "uploaded_periods.txt")
    request.files["file"].save(path)
    try:
        new_periods = PeriodParser().parse(path)
        if mode == "append":
            existing = {(p.semester, p.moed) for p in state["periods"]}
            state["periods"] += [
                p for p in new_periods if (p.semester, p.moed) not in existing
            ]
        else:
            state["periods"] = new_periods
            state["period_overrides"] = {}
            state["selected_programs"] = []
        state["periods_file_hash"] = file_hash(path)
        clear_generated_results()
        save_cache()
        msg = (
            f"Periods loaded — {len(state['periods'])} records. "
            "Generation history and schedules were cleared."
        )
        set_flash(msg, "ok")
        if _ajax_request():
            payload = _upload_status_payload()
            payload.update({"ok": True, "flash": {"msg": msg, "type": "ok"}})
            return jsonify(payload)
    except Exception as e:
        set_flash(str(e), "err")
        if _ajax_request():
            return jsonify({"ok": False, "error": str(e)}), 400
    return redirect_screen("input", anchor="file-loading")


def _ajax_request():
    return request.headers.get("X-Requested-With") == "Schedulix"


@app.route("/programs/toggle", methods=["POST"])
def programs_toggle():
    prog_id = request.form.get("prog_id")
    ajax = _ajax_request()

    if not prog_id:
        if ajax:
            return jsonify({"ok": False, "error": "Missing program id"}), 400
        return redirect_screen("input")

    selected = list(state["selected_programs"])
    if prog_id in selected:
        selected.remove(prog_id)
        is_selected = False
    else:
        if len(selected) >= 5:
            if ajax:
                return jsonify({"ok": False, "error": "Max 5 programs allowed"}), 400
            set_flash("Max 5 programs allowed", "err")
            return redirect_screen("input")
        selected.append(prog_id)
        is_selected = True

    state["selected_programs"] = selected

    if ajax:
        return jsonify({
            "ok": True,
            "prog_id": prog_id,
            "is_selected": is_selected,
            "count": len(selected),
            "selected": selected,
        })

    return redirect_screen("input")


def _generation_flash_message(aleph_count, bet_count, timed_out):
    if timed_out:
        return (
            f"Time limit reached — {aleph_count} Aleph + {bet_count} Bet partial results",
            "err",
        )
    if aleph_count or bet_count:
        return (f"{aleph_count} Aleph + {bet_count} Bet schedules generated!", "ok")
    return ("No schedules found for the current selection", "err")


def _generation_ajax_payload(aleph_count, bet_count, flash_msg, flash_type):
    return jsonify({
        "ok": True,
        "gen_result": format_generate_result(aleph_count, bet_count),
        "history_html": render_gen_history_html(relevant_gen_history()),
        "flash": {"msg": flash_msg, "type": flash_type},
    })


def _upload_status_payload():
    courses_count = len(state["courses"])
    periods_count = len(state["periods"])
    ctx = {
        "courses_count": courses_count,
        "periods_count": periods_count,
        "selected_programs": list(state["selected_programs"]),
        "programs": list_programs(),
    }
    return {
        "courses_count": courses_count,
        "periods_count": periods_count,
        "courses_status": f"✓ {courses_count} loaded" if courses_count else "Not loaded",
        "periods_status": f"✓ {periods_count} loaded" if periods_count else "Not loaded",
        "program_grid_html": render_program_grid_html(ctx),
        "sel_count": len(state["selected_programs"]),
        "gen_result": "",
        "history_html": "",
    }


@app.route("/generate", methods=["POST"])
def generate():
    ajax = _ajax_request()

    if not state["courses"]:
        if ajax:
            return jsonify({"ok": False, "error": "No courses loaded"}), 400
        set_flash("No courses loaded", "err")
        return redirect_screen("input")
    if not state["periods"]:
        if ajax:
            return jsonify({"ok": False, "error": "No exam periods loaded"}), 400
        set_flash("No exam periods loaded", "err")
        return redirect_screen("input")
    if not state["selected_programs"]:
        if ajax:
            return jsonify({"ok": False, "error": "No programs selected"}), 400
        set_flash("No programs selected", "err")
        return redirect_screen("input")

    if state["gen_job"].get("running"):
        if ajax:
            return jsonify({"ok": False, "error": "Generation already in progress"}), 409
        set_flash("Generation already in progress", "err")
        return redirect_screen("input")

    threading.Thread(target=_run_generation_job, daemon=True).start()

    if ajax:
        return jsonify({"ok": True, "started": True})
    return redirect_screen("input")


@app.route("/generate/status")
def generate_status():
    job = state.get("gen_job", {})
    aleph_count = len(state["aleph_schedules"])
    bet_count = len(state["bet_schedules"])
    payload = {
        "running": bool(job.get("running")),
        "done": bool(job.get("done")),
        "aleph_count": aleph_count,
        "bet_count": bet_count,
        "timed_out": bool(job.get("timed_out")),
        "error": job.get("error"),
        "gen_result": format_generate_result(aleph_count, bet_count),
    }
    if job.get("running") or job.get("done"):
        with app.test_request_context("/?screen=output"):
            ctx = build_context("output")
        ctx["gen_running"] = bool(job.get("running"))
        payload.update(render_output_live(ctx))
    if job.get("done"):
        payload["history_html"] = render_gen_history_html(relevant_gen_history())
        if job.get("flash"):
            payload["flash"] = job["flash"]
    return jsonify(payload)


@app.route("/history/restore", methods=["POST"])
def history_restore():
    ajax = _ajax_request()
    try:
        idx = int(request.form.get("index", -1))
    except ValueError:
        idx = -1
    if 0 <= idx < len(state["gen_history"]):
        entry = state["gen_history"][idx]
        if entry.get("input_fingerprint") != input_fingerprint():
            if ajax:
                return jsonify({"ok": False, "error": "History entry does not match current input files"}), 400
            set_flash("History entry does not match current input files", "err")
            return redirect_screen("input")
        state["selected_programs"] = list(entry["programs"])
        state["aleph_schedules"] = snapshot_schedules(entry.get("aleph_schedules", []))
        state["bet_schedules"] = snapshot_schedules(entry.get("bet_schedules", []))
        state["period_overrides"] = copy.deepcopy(entry.get("period_overrides", {}))
        state["edit_history"] = []
        state["locked_exams"] = set()
        apply_sort()
        state["gen_history"].append(state["gen_history"].pop(idx))
        flash_msg = "Previous run restored — programs, calendar, and schedules recovered"
        set_flash(flash_msg, "ok")
        if ajax:
            aleph_count = len(state["aleph_schedules"])
            bet_count = len(state["bet_schedules"])
            return jsonify({
                "ok": True,
                "gen_result": format_generate_result(aleph_count, bet_count),
                "history_html": render_gen_history_html(relevant_gen_history()),
                "flash": {"msg": flash_msg, "type": "ok"},
                "count": len(state["selected_programs"]),
                "selected": list(state["selected_programs"]),
            })
        return redirect_screen("input")
    if ajax:
        return jsonify({"ok": False, "error": "Invalid history entry"}), 400
    return redirect_screen("input")


@app.route("/calendar/toggle", methods=["POST"])
def calendar_toggle():
    semester = request.form.get("semester")
    moed = request.form.get("moed")
    date_str = request.form.get("date")
    action = toggle_day(semester, moed, date_str)
    if action:
        set_flash(f"{date_str} {action}", "ok")
    return redirect_screen(
        "calendar", active_aleph=state["active_aleph"], active_bet=state["active_bet"]
    )


@app.route("/calendar/shift", methods=["POST"])
def calendar_shift():
    key = f"{request.form.get('semester')}|{request.form.get('moed')}"
    if key not in state["period_overrides"]:
        state["period_overrides"][key] = {
            "excluded_extra": [],
            "reincluded": [],
            "start_shift": 0,
            "end_shift": 0,
        }
    ov = state["period_overrides"][key]
    try:
        ov["start_shift"] = int(request.form.get("start_shift", 0))
        ov["end_shift"] = int(request.form.get("end_shift", 0))
    except ValueError:
        pass
    set_flash("Date shift applied", "ok")
    return redirect_screen(
        "calendar", active_aleph=state["active_aleph"], active_bet=state["active_bet"]
    )


@app.route("/calendar/preset_target", methods=["POST"])
def calendar_preset_target():
    moed = request.form.get("moed")
    if moed == "aleph":
        state["preset_target_aleph"] = request.form.get("target_aleph") == "1"
        if not state["preset_target_aleph"] and not state["preset_target_bet"]:
            state["preset_target_aleph"] = True
            set_flash("At least one moed must be selected", "err")
    elif moed == "bet":
        state["preset_target_bet"] = request.form.get("target_bet") == "1"
        if not state["preset_target_aleph"] and not state["preset_target_bet"]:
            state["preset_target_bet"] = True
            set_flash("At least one moed must be selected", "err")
    return redirect_screen(
        "calendar", active_aleph=state["active_aleph"], active_bet=state["active_bet"]
    )


@app.route("/calendar/preset", methods=["POST"])
def calendar_preset():
    preset_key = request.form.get("preset")
    target_aleph = request.form.get("target_aleph") == "1"
    target_bet = request.form.get("target_bet") == "1"
    preset = HOLIDAY_PRESETS.get(preset_key)
    if not preset:
        return redirect_screen(
            "calendar", active_aleph=state["active_aleph"], active_bet=state["active_bet"]
        )
    if not state["periods"]:
        set_flash("Load calendar data first", "err")
        return redirect_screen(
            "calendar", active_aleph=state["active_aleph"], active_bet=state["active_bet"]
        )
    excluded = apply_holiday_preset(preset_key, target_aleph, target_bet)
    if excluded == 0:
        set_flash(f"{preset['label']}: no matching dates in current periods", "err")
    else:
        set_flash(
            f"{preset['label']}: excluded {excluded} day{'s' if excluded != 1 else ''}",
            "ok",
        )
    return redirect_screen(
        "calendar", active_aleph=state["active_aleph"], active_bet=state["active_bet"]
    )


@app.route("/calendar/custom_event", methods=["POST"])
def calendar_custom_event():
    """Excludes a user-defined event (single date or range) from the chosen moeds."""
    name = (request.form.get("event_name") or "").strip() or "Custom event"
    start = (request.form.get("start_date") or "").strip()
    end = (request.form.get("end_date") or "").strip() or start
    target_aleph = request.form.get("target_aleph") == "1"
    target_bet = request.form.get("target_bet") == "1"

    redirect_to = lambda: redirect_screen(
        "calendar", active_aleph=state["active_aleph"], active_bet=state["active_bet"]
    )

    if not state["periods"]:
        set_flash("Load calendar data first", "err")
        return redirect_to()
    if not start:
        set_flash("Provide at least a start date", "err")
        return redirect_to()
    if not (target_aleph or target_bet):
        target_aleph = target_bet = True

    try:
        d0 = datetime.strptime(start, "%Y-%m-%d")
        d1 = datetime.strptime(end, "%Y-%m-%d")
    except ValueError:
        set_flash("Invalid date format", "err")
        return redirect_to()
    if d1 < d0:
        d0, d1 = d1, d0

    dates = []
    cur = d0
    while cur <= d1:
        dates.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)

    periods = []
    if target_aleph:
        periods.extend(period_to_dict(p) for p in state["periods"] if p.moed == "Aleph")
    if target_bet:
        periods.extend(period_to_dict(p) for p in state["periods"] if p.moed == "Bet")

    excluded = 0
    for period in periods:
        avail_set = set(period["available"])
        all_set = set(period["all_dates"])
        for date in dates:
            if date in all_set and date in avail_set:
                toggle_day(period["semester"], period["moed"], date)
                excluded += 1

    state["custom_events"].append(
        {
            "name": name,
            "start": start,
            "end": end if end != start else "",
            "aleph": target_aleph,
            "bet": target_bet,
            "excluded": excluded,
        }
    )

    if excluded:
        set_flash(f"{name}: excluded {excluded} day(s)", "ok")
    else:
        set_flash(f"{name}: no matching available dates in the selected terms", "err")
    return redirect_to()


@app.route("/export")
def export_schedule():
    sems = all_semesters()
    if not sems:
        return Response("No schedules to export.", mimetype="text/plain")
        
    lines = [
        "=" * 70,
        "  SCHEDULIX — Exam Schedule Generator  |  Version 34.0",
        "=" * 70,
        f"  Selected Programs : {', '.join(str(p) for p in state['selected_programs'])}",
        "=" * 70 + "\n",
    ]
    
    for sem in sems:
        exp_aleph, exp_bet = schedules_for_semester(sem)
        aleph_total = len(exp_aleph)
        bet_total   = len(exp_bet)
        
        # Retrieve the currently saved pagination for this specific semester
        saved_pages = state.get("pagination", {}).get(sem, {"aleph": 0, "bet": 0})
        aleph_page = saved_pages["aleph"]
        bet_page = saved_pages["bet"]
        
        aleph_sched = exp_aleph[aleph_page] if aleph_total and aleph_page < aleph_total else None
        bet_sched   = exp_bet[bet_page]     if bet_total   and bet_page   < bet_total   else None
        
        lines.append(f"### SEMESTER: {sem} ###")
        lines.append(f"  Moed Aleph: Schedule {aleph_page + 1} of {aleph_total}")
        lines.append(f"  Moed Bet  : Schedule {bet_page + 1} of {bet_total}")
        lines.append("-" * 70)

        for moed_label, sched in [
            ("Moed Aleph  (מועד א׳)", aleph_sched),
            ("Moed Bet  (מועד ב׳)", bet_sched),
        ]:
            lines.append("─" * 70)
            lines.append(f"  {moed_label}")
            lines.append("─" * 70)
            if sched:
                for e in schedule_to_entries(sched):
                    try:
                        dt = datetime.strptime(e["date"], "%Y-%m-%d")
                        date_str = dt.strftime("%d-%m-%Y (%A)")
                    except ValueError:
                        date_str = e["date"]
                    lines.append(
                        f"    {date_str:<28}  {e['course_name']:<35}  {e['instructor']}"
                    )
            else:
                lines.append("    (no schedule)")
            lines.append("")
        lines.append("\n")

    fname = "schedule_all_semesters.txt"
    return Response(
        "\n".join(lines),
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


# ── Startup ───────────────────────────────────────────────────────────────────

def try_load_defaults():
    courses_path = os.path.join(DATA_DIR, "V1.0CourseDB.txt")
    periods_path = os.path.join(DATA_DIR, "V1.0 ExamDates.txt")
    ch = file_hash(courses_path)
    ph = file_hash(periods_path)
    cached = load_cache()
    if cached and state["courses_file_hash"] == ch and state["periods_file_hash"] == ph:
        print("[Startup] Using cached data.")
        return
    print("[Startup] Loading from default data files...")
    clear_generated_results()
    try:
        state["courses"] = CourseParser().parse(courses_path)
        state["courses_file_hash"] = ch
    except Exception as e:
        print(f"[Startup] Courses load failed: {e}")
    try:
        state["periods"] = PeriodParser().parse(periods_path)
        state["periods_file_hash"] = ph
    except Exception as e:
        print(f"[Startup] Periods load failed: {e}")
    save_cache()


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    try_load_defaults()
    app.run(debug=True, port=5000, threaded=True)
