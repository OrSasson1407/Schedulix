"""
app.py — Schedulix V3 (Python + CSS only)

All UI is built in Python (src/ui/views.py) and styled with static/style.css.
No separate HTML/JS frontend and no REST API for the browser — only form POSTs and links.

Run:  python app.py
"""

import os
import sys
import pickle
import hashlib
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
from src.models.ExamPeriod import ExamPeriod
from src.ui.views import (
    render_page,
    PROGRAM_NAMES,
    HOLIDAY_PRESETS,
    format_generate_result,
    render_gen_history_html,
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
    if scroll is not None and int(scroll) > 0:
        q["scroll"] = int(scroll)
    url = "/?" + urlencode(q)
    if anchor:
        url += "#" + anchor.lstrip("#")
    return redirect(url)


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
    aleph_page = _page_index(request.args.get("aleph_page"), aleph_total)
    bet_page = _page_index(request.args.get("bet_page"), bet_total)

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
        "gen_history": state["gen_history"],
        "aleph_periods": [period_to_dict(p) for p in state["periods"] if p.moed == "Aleph"],
        "bet_periods": [period_to_dict(p) for p in state["periods"] if p.moed == "Bet"],
        "active_aleph": state["active_aleph"],
        "active_bet": state["active_bet"],
        "preset_target_aleph": state["preset_target_aleph"],
        "preset_target_bet": state["preset_target_bet"],
        "aleph_page": aleph_page,
        "bet_page": bet_page,
        "aleph_total": aleph_total,
        "bet_total": bet_total,
        "schedule": None,
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

    if screen == "output" and (aleph_total or bet_total):
        aleph_entries = (
            schedule_to_entries(state["aleph_schedules"][aleph_page]) if aleph_total else []
        )
        bet_entries = (
            schedule_to_entries(state["bet_schedules"][bet_page]) if bet_total else []
        )
        sem = ""
        if aleph_entries:
            sem = aleph_entries[0]["semester"]
        elif bet_entries:
            sem = bet_entries[0]["semester"]
        ctx["schedule"] = {
            "semester": sem,
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

    def _run_aleph():
        sched = BacktrackScheduler()
        for s in sched.generate(_make_filtered(), aleph_periods):
            if s.assignments:
                state["aleph_schedules"].append(s)

    def _run_bet():
        sched = BacktrackScheduler()
        for s in sched.generate(_make_filtered(), bet_periods):
            if s.assignments:
                state["bet_schedules"].append(s)

    hard_timeout = BacktrackScheduler.TIME_LIMIT_SECONDS + 1
    with _generation_lock:
        t_a = threading.Thread(target=_run_aleph, daemon=True)
        t_b = threading.Thread(target=_run_bet, daemon=True)
        t_a.start()
        t_b.start()
        deadline = time.time() + hard_timeout
        while (t_a.is_alive() or t_b.is_alive()) and time.time() < deadline:
            time.sleep(0.1)
        timed_out = t_a.is_alive() or t_b.is_alive()

    return len(state["aleph_schedules"]), len(state["bet_schedules"]), timed_out


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
        save_cache()
        set_flash(f"Courses loaded — {len(state['courses'])} records", "ok")
    except Exception as e:
        set_flash(str(e), "err")
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
        save_cache()
        set_flash(f"Periods loaded — {len(state['periods'])} records", "ok")
    except Exception as e:
        set_flash(str(e), "err")
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
        "history_html": render_gen_history_html(state["gen_history"]),
        "flash": {"msg": flash_msg, "type": flash_type},
    })


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

    aleph_count, bet_count, timed_out = run_generation()
    state["gen_history"].append(
        {
            "ts": datetime.now(),
            "programs": list(state["selected_programs"]),
            "aleph_count": aleph_count,
            "bet_count": bet_count,
            "timed_out": timed_out,
        }
    )
    if len(state["gen_history"]) > 2:
        state["gen_history"].pop(0)

    flash_msg, flash_type = _generation_flash_message(aleph_count, bet_count, timed_out)
    set_flash(flash_msg, flash_type)

    if ajax:
        return _generation_ajax_payload(aleph_count, bet_count, flash_msg, flash_type)
    return redirect_screen("input")


@app.route("/history/restore", methods=["POST"])
def history_restore():
    ajax = _ajax_request()
    try:
        idx = int(request.form.get("index", -1))
    except ValueError:
        idx = -1
    if 0 <= idx < len(state["gen_history"]):
        entry = state["gen_history"][idx]
        state["selected_programs"] = list(entry["programs"])
        state["gen_history"].append(state["gen_history"].pop(idx))
        flash_msg = "Previous run restored — programs re-selected"
        set_flash(flash_msg, "ok")
        if ajax:
            aleph_count = len(state["aleph_schedules"])
            bet_count = len(state["bet_schedules"])
            return jsonify({
                "ok": True,
                "gen_result": format_generate_result(aleph_count, bet_count),
                "history_html": render_gen_history_html(state["gen_history"]),
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


@app.route("/export")
def export_schedule():
    aleph_total = len(state["aleph_schedules"])
    bet_total = len(state["bet_schedules"])
    aleph_page = _page_index(request.args.get("aleph_page"), aleph_total)
    bet_page = _page_index(request.args.get("bet_page"), bet_total)

    aleph_sched = (
        state["aleph_schedules"][aleph_page]
        if aleph_total and aleph_page < aleph_total
        else None
    )
    bet_sched = (
        state["bet_schedules"][bet_page]
        if bet_total and bet_page < bet_total
        else None
    )

    lines = [
        "=" * 70,
        "  SCHEDULIX — Exam Schedule Generator  |  Version 3.1",
        "=" * 70,
        f"  Selected Programs : {', '.join(str(p) for p in state['selected_programs'])}",
        f"  Moed Aleph        : Schedule {aleph_page + 1} of {aleph_total}",
        f"  Moed Bet          : Schedule {bet_page + 1} of {bet_total}",
        "=" * 70 + "\n",
    ]
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

    fname = f"schedule_A{aleph_page + 1}_B{bet_page + 1}.txt"
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