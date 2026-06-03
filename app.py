"""
app.py  —  Schedulix V3.1 Flask Backend
Dual-calendar mode: Moed Aleph + Moed Bet stored separately.
Each has its own independent page index on the frontend.
Export always combines the currently-viewed Aleph + Bet together.
"""

import os, sys, json, pickle, hashlib, threading, copy, time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory, Response

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.parser.CourseParser import CourseParser
from src.parser.PeriodParser import PeriodParser
from src.scheduler.BacktrackScheduler import BacktrackScheduler
from src.models.ExamPeriod import ExamPeriod
from src.models.Schedule import Schedule

app = Flask(__name__, static_folder="static")

# ── In-memory state ──────────────────────────────────────────────────────────
state = {
    "courses": [],
    "periods": [],
    "period_overrides": {},
    "selected_programs": [],
    # Schedules stored separately per moed
    "aleph_schedules": [],  # list of Schedule objects for Moed Aleph
    "bet_schedules":   [],  # list of Schedule objects for Moed Bet
    "courses_file_hash": None,
    "periods_file_hash": None,
}

CACHE_PATH = os.path.join(PROJECT_ROOT, "data", ".cache.pkl")
DATA_DIR   = os.path.join(PROJECT_ROOT, "data")

# ── Helpers ──────────────────────────────────────────────────────────────────

def file_hash(path):
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except:
        return None

def save_cache():
    try:
        with open(CACHE_PATH, "wb") as f:
            pickle.dump({k: state[k] for k in ("courses","periods","courses_file_hash","periods_file_hash")}, f)
    except Exception as e:
        print(f"[Cache] Save failed: {e}")

def load_cache():
    try:
        with open(CACHE_PATH, "rb") as f:
            data = pickle.load(f)
        state.update(data)
        print("[Cache] Loaded from cache.")
        return True
    except:
        return False

def get_effective_period(period):
    key = f"{period.semester}|{period.moed}"
    ov  = state["period_overrides"].get(key, {})
    start = period.start_date + timedelta(days=ov.get("start_shift", 0))
    end   = period.end_date   + timedelta(days=ov.get("end_shift", 0))

    extra_excluded = set()
    for d in ov.get("excluded_extra", []):
        try: extra_excluded.add(datetime.strptime(d, "%Y-%m-%d").date())
        except: pass

    reincluded = set()
    for d in ov.get("reincluded", []):
        try: reincluded.add(datetime.strptime(d, "%Y-%m-%d").date())
        except: pass

    orig_excluded = {d for d in period.excluded_dates if d not in reincluded}
    merged = list(orig_excluded | extra_excluded)

    ep = ExamPeriod(
        semester=period.semester,
        moed=period.moed,
        start_date=start.strftime("%d-%m-%Y"),
        end_date=end.strftime("%d-%m-%Y"),
        excluded_dates=[datetime.combine(d, datetime.min.time()) if hasattr(d,'year') and not hasattr(d,'hour') else d for d in merged]
    )
    return ep

def period_to_dict(period):
    key = f"{period.semester}|{period.moed}"
    ov  = state["period_overrides"].get(key, {})
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
        entries.append({
            "date": exam_date.date.strftime("%Y-%m-%d"),
            "course_id": course.course_id,
            "course_name": course.name,
            "instructor": course.instructor,
            "semester": exam_date.semester,
            "moed": exam_date.moed,
            "requirement": req,
            "programs": prog_ids,
        })
    entries.sort(key=lambda x: x["date"])
    return entries

# ── API Routes ────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/api/status")
def api_status():
    return jsonify({
        "courses_loaded": len(state["courses"]),
        "periods_loaded": len(state["periods"]),
        "selected_programs": state["selected_programs"],
        "aleph_count": len(state["aleph_schedules"]),
        "bet_count":   len(state["bet_schedules"]),
    })

@app.route("/api/load_courses", methods=["POST"])
def api_load_courses():
    mode = request.args.get("mode", "overwrite")
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    path = os.path.join(DATA_DIR, "uploaded_courses.txt")
    f.save(path)
    try:
        parser = CourseParser()
        new_courses = parser.parse(path)
        if mode == "append":
            existing_ids = {c.course_id for c in state["courses"]}
            state["courses"] += [c for c in new_courses if c.course_id not in existing_ids]
        else:
            state["courses"] = new_courses
            state["selected_programs"] = []  # reset on overwrite
        state["courses_file_hash"] = file_hash(path)
        save_cache()
        return jsonify({"loaded": len(state["courses"]), "mode": mode,
                        "selected_programs_reset": mode == "overwrite"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/load_periods", methods=["POST"])
def api_load_periods():
    mode = request.args.get("mode", "overwrite")
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    path = os.path.join(DATA_DIR, "uploaded_periods.txt")
    f.save(path)
    try:
        parser = PeriodParser()
        new_periods = parser.parse(path)
        if mode == "append":
            existing = {(p.semester, p.moed) for p in state["periods"]}
            state["periods"] += [p for p in new_periods if (p.semester, p.moed) not in existing]
        else:
            state["periods"] = new_periods
            state["period_overrides"] = {}
            state["selected_programs"] = []
        state["periods_file_hash"] = file_hash(path)
        save_cache()
        return jsonify({"loaded": len(state["periods"]), "mode": mode})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/programs")
def api_programs():
    programs = {}
    for course in state["courses"]:
        for p in course.programs:
            if p.program_id not in programs:
                programs[p.program_id] = p.program_id
    name_map = {
        "83101": "Computer Engineering",
        "83102": "Electrical Engineering",
        "83104": "Industrial & Information Systems",
        "83107": "Data Engineering",
        "83108": "Software Engineering",
        "83109": "Materials Engineering",
        "83105": "Computer Engineering – Computer Hardware",
        "83182": "Electrical Engineering – Quantum Engineering",
        "83103": "Electrical Engineering – Neuro Engineering",
        "83115": "Electrical Engineering – Bio-Medical Engineering",
    }
    result = [{"id": pid, "name": name_map.get(pid, f"Program {pid}")} for pid in sorted(programs.keys())]
    return jsonify(result)

@app.route("/api/programs/select", methods=["POST"])
def api_select_programs():
    data = request.get_json()
    selected = data.get("programs", [])
    if len(selected) > 5:
        return jsonify({"error": "Max 5 programs allowed"}), 400
    state["selected_programs"] = selected
    return jsonify({"selected": state["selected_programs"]})

@app.route("/api/programs/<prog_id>/courses")
def api_program_courses(prog_id):
    year_filter = request.args.get("year")
    sem_filter  = request.args.get("semester")
    courses = []
    for course in state["courses"]:
        for p in course.programs:
            if p.program_id == prog_id:
                if year_filter and str(p.year) != year_filter: continue
                if sem_filter and p.semester != sem_filter: continue
                courses.append({
                    "course_id": course.course_id,
                    "name": course.name,
                    "instructor": course.instructor,
                    "year": p.year,
                    "semester": p.semester,
                    "requirement": p.requirement,
                    "evaluation": course.evaluation,
                })
    courses.sort(key=lambda x: (x["year"], x["semester"], x["name"]))
    return jsonify(courses)

@app.route("/api/calendar")
def api_calendar():
    aleph = [period_to_dict(p) for p in state["periods"] if p.moed == "Aleph"]
    bet   = [period_to_dict(p) for p in state["periods"] if p.moed == "Bet"]
    return jsonify({"aleph": aleph, "bet": bet})

@app.route("/api/calendar/toggle_day", methods=["POST"])
def api_toggle_day():
    data = request.get_json()
    semester = data["semester"]
    moed     = data["moed"]
    date_str = data["date"]
    key = f"{semester}|{moed}"

    if key not in state["period_overrides"]:
        state["period_overrides"][key] = {"excluded_extra": [], "reincluded": [], "start_shift": 0, "end_shift": 0}
    ov = state["period_overrides"][key]

    period = next((p for p in state["periods"] if p.semester == semester and p.moed == moed), None)
    if not period:
        return jsonify({"error": "Period not found"}), 404

    try: d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except: return jsonify({"error": "Invalid date"}), 400

    originally_excluded = d in period.excluded_dates
    currently_extra_excluded = date_str in ov["excluded_extra"]
    currently_reincluded = date_str in ov["reincluded"]

    if originally_excluded:
        if currently_reincluded:
            ov["reincluded"].remove(date_str); action = "re-excluded"
        else:
            ov["reincluded"].append(date_str); action = "re-included"
    else:
        if currently_extra_excluded:
            ov["excluded_extra"].remove(date_str); action = "re-included"
        else:
            ov["excluded_extra"].append(date_str); action = "excluded"

    return jsonify({"action": action, "date": date_str})

@app.route("/api/calendar/shift", methods=["POST"])
def api_shift_dates():
    data = request.get_json()
    key  = f"{data['semester']}|{data['moed']}"
    if key not in state["period_overrides"]:
        state["period_overrides"][key] = {"excluded_extra": [], "reincluded": [], "start_shift": 0, "end_shift": 0}
    ov = state["period_overrides"][key]
    if "start_shift" in data: ov["start_shift"] = int(data["start_shift"])
    if "end_shift"   in data: ov["end_shift"]   = int(data["end_shift"])
    return jsonify({"ok": True})

_generation_lock = threading.Lock()

@app.route("/api/generate", methods=["POST"])
def api_generate():
    if not state["courses"]:           return jsonify({"error": "No courses loaded"}), 400
    if not state["periods"]:           return jsonify({"error": "No exam periods loaded"}), 400
    if not state["selected_programs"]: return jsonify({"error": "No programs selected"}), 400

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
    bet_periods   = [p for p in effective_periods if p.moed == "Bet"]

    # Clear previous results immediately so state is never stale
    state["aleph_schedules"] = []
    state["bet_schedules"]   = []

    def _run_aleph():
        sched = BacktrackScheduler()
        for s in sched.generate(_make_filtered(), aleph_periods):
            if s.assignments:
                # Write each schedule into state as soon as it is found.
                # If the time limit fires mid-run, whatever landed here is
                # already visible to /api/schedules.
                state["aleph_schedules"].append(s)

    def _run_bet():
        sched = BacktrackScheduler()
        for s in sched.generate(_make_filtered(), bet_periods):
            if s.assignments:
                state["bet_schedules"].append(s)

    HARD_TIMEOUT = BacktrackScheduler.TIME_LIMIT_SECONDS + 1  # 29 s

    with _generation_lock:
        t_a = threading.Thread(target=_run_aleph, daemon=True)
        t_b = threading.Thread(target=_run_bet,   daemon=True)
        t_a.start(); t_b.start()

        # Both threads run in parallel. We wait until BOTH finish,
        # or until the shared 29-second deadline — whichever comes first.
        deadline = time.time() + HARD_TIMEOUT
        while (t_a.is_alive() or t_b.is_alive()) and time.time() < deadline:
            time.sleep(0.1)

        timed_out = t_a.is_alive() or t_b.is_alive()

    return jsonify({
        "aleph_count": len(state["aleph_schedules"]),
        "bet_count":   len(state["bet_schedules"]),
        "timed_out":   timed_out,
    })

@app.route("/api/schedules")
def api_schedules():
    """
    Returns the schedule at the given aleph_page and bet_page independently.
    Each can be navigated independently.
    """
    aleph_page = int(request.args.get("aleph_page", 0))
    bet_page   = int(request.args.get("bet_page",   0))

    aleph_total = len(state["aleph_schedules"])
    bet_total   = len(state["bet_schedules"])

    aleph_page = max(0, min(aleph_page, aleph_total - 1)) if aleph_total > 0 else 0
    bet_page   = max(0, min(bet_page,   bet_total   - 1)) if bet_total   > 0 else 0

    aleph_entries = schedule_to_entries(state["aleph_schedules"][aleph_page]) if aleph_total > 0 else []
    bet_entries   = schedule_to_entries(state["bet_schedules"][bet_page])     if bet_total   > 0 else []

    # Determine semester label
    sem = ""
    if aleph_entries: sem = aleph_entries[0]["semester"]
    elif bet_entries: sem = bet_entries[0]["semester"]

    return jsonify({
        "aleph_page":  aleph_page,
        "aleph_total": aleph_total,
        "bet_page":    bet_page,
        "bet_total":   bet_total,
        "schedule": {
            "semester":      sem,
            "aleph_entries": aleph_entries,
            "bet_entries":   bet_entries,
        }
    })

@app.route("/api/schedules/export")
def api_export():
    """Export the schedule at aleph_page + bet_page as a combined txt."""
    aleph_page = int(request.args.get("aleph_page", 0))
    bet_page   = int(request.args.get("bet_page",   0))

    aleph_total = len(state["aleph_schedules"])
    bet_total   = len(state["bet_schedules"])

    aleph_sched = state["aleph_schedules"][aleph_page] if aleph_total > 0 and aleph_page < aleph_total else None
    bet_sched   = state["bet_schedules"][bet_page]     if bet_total   > 0 and bet_page   < bet_total   else None

    lines = []
    lines.append("=" * 70)
    lines.append("  SCHEDULIX — Exam Schedule Generator  |  Version 3.1")
    lines.append("=" * 70)
    lines.append(f"  Selected Programs : {', '.join(str(p) for p in state['selected_programs'])}")
    lines.append(f"  Moed Aleph        : Schedule {aleph_page + 1} of {aleph_total}")
    lines.append(f"  Moed Bet          : Schedule {bet_page + 1} of {bet_total}")
    lines.append("=" * 70 + "\n")

    for moed_label, sched in [("Moed Aleph  (מועד א׳)", aleph_sched), ("Moed Bet  (מועד ב׳)", bet_sched)]:
        lines.append(f"{'─' * 70}")
        lines.append(f"  {moed_label}")
        lines.append(f"{'─' * 70}")
        if sched:
            entries = schedule_to_entries(sched)
            for e in entries:
                try:
                    dt = datetime.strptime(e["date"], "%Y-%m-%d")
                    date_str = dt.strftime("%d-%m-%Y (%A)")
                except:
                    date_str = e["date"]
                lines.append(f"    {date_str:<28}  {e['course_name']:<35}  {e['instructor']}")
        else:
            lines.append("    (no schedule)")
        lines.append("")

    content = "\n".join(lines)
    fname = f"schedule_A{aleph_page+1}_B{bet_page+1}.txt"
    return Response(content, mimetype="text/plain",
                    headers={"Content-Disposition": f"attachment; filename={fname}"})

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