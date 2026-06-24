"""
ScheduleSorter.py
Dynamic, multi-criteria sorting for already-generated valid schedules.

Unlike the hard constraints (which run inside the scheduler and DROP schedules),
sorting is a pure, post-generation operation. It re-orders the in-memory list of
valid Schedule objects according to a user-defined, ordered list of criteria —
without re-running the scheduling algorithm.

For every supported criterion the schedules are ranked in DESCENDING order of the
computed metric. When several criteria are selected they are applied as a layered
sort: the first criterion is the primary key, the second is the tie-breaker, and
so on (primary -> secondary -> tertiary -> ...).

All day differences count calendar days (weekends and holidays included), since
they are measured directly on the assigned exam dates.
"""

# Public metadata describing each sort criterion (drives the Output UI).
SORT_CRITERIA = [
    {
        "key": "min_mandatory_spacing",
        "label": "Minimum Mandatory Spacing",
        "desc": "Min days between any two mandatory exams (same program & year).",
    },
    {
        "key": "avg_exam_spacing",
        "label": "Average Exam Spacing",
        "desc": "Average days between any two exams (same program & year).",
    },
    {
        "key": "elective_collisions",
        "label": "Elective Collisions Count",
        "desc": "Same-day collisions between elective courses in the same program.",
    },
    {
        "key": "mandatory_window",
        "label": "Mandatory Exam Window",
        "desc": "Days between the first and last mandatory exam (program, year, moed).",
    },
    {
        "key": "peak_daily_capacity",
        "label": "Peak Daily Capacity",
        "desc": "Maximum number of exams scheduled on the same day system-wide.",
    },
]

# Stable identity / ordering of every supported metric key.
METRIC_KEYS = tuple(c["key"] for c in SORT_CRITERIA)


# --------------------------------------------------------------------------- #
# Record extraction
# --------------------------------------------------------------------------- #
def _day_of(exam_date):
    """Returns the calendar 'date' object for an assigned ExamDate."""
    raw = exam_date.date
    return raw.date() if hasattr(raw, "date") else raw


def _records(schedule):
    """
    Flattens a Schedule into one record per (assignment, program membership),
    carrying the program/year/requirement context plus the assigned day.
    """
    records = []
    for (course, moed), exam_date in schedule.assignments.items():
        day = _day_of(exam_date)
        for prog in course.programs:
            records.append(
                {
                    "course_id": course.course_id,
                    "program_id": prog.program_id,
                    "year": prog.year,
                    "requirement": prog.requirement,
                    "moed": moed,
                    "day": day,
                }
            )
    return records


def _pairwise_gaps(records, mandatory_only):
    """
    Yields the absolute day gap for every pair of distinct courses that share the
    same (program_id, year). When mandatory_only is True only Obligatory
    memberships participate.
    """
    groups = {}
    for r in records:
        if mandatory_only and r["requirement"] != "Obligatory":
            continue
        groups.setdefault((r["program_id"], r["year"]), []).append(r)

    for group in groups.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                if a["course_id"] == b["course_id"]:
                    continue
                yield abs((a["day"] - b["day"]).days)


# --------------------------------------------------------------------------- #
# The 5 metric helpers
# --------------------------------------------------------------------------- #
def min_mandatory_spacing(schedule) -> int:
    """Minimum gap (days) between any two mandatory exams in the same program/year.
    Returns 0 when the schedule has no qualifying mandatory pair."""
    gaps = list(_pairwise_gaps(_records(schedule), mandatory_only=True))
    return min(gaps) if gaps else 0


def avg_exam_spacing(schedule) -> float:
    """Average gap (days) between any two exams in the same program/year.
    Returns 0.0 when the schedule has no qualifying pair."""
    gaps = list(_pairwise_gaps(_records(schedule), mandatory_only=False))
    return (sum(gaps) / len(gaps)) if gaps else 0.0


def elective_collisions(schedule) -> int:
    """Total same-day collisions between two elective courses within the same program."""
    by_program = {}
    for r in _records(schedule):
        if r["requirement"] != "Elective":
            continue
        by_program.setdefault(r["program_id"], []).append(r)

    total = 0
    for group in by_program.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                if a["course_id"] == b["course_id"]:
                    continue
                if a["day"] == b["day"]:
                    total += 1
    return total


def mandatory_window(schedule) -> int:
    """Widest span (days) between the first and last mandatory exam across all
    (program, year, moed) groups. Returns 0 when no group has >= 2 mandatory exams."""
    groups = {}
    for r in _records(schedule):
        if r["requirement"] != "Obligatory":
            continue
        groups.setdefault((r["program_id"], r["year"], r["moed"]), []).append(r["day"])

    widest = 0
    for days in groups.values():
        if len(days) < 2:
            continue
        span = (max(days) - min(days)).days
        if span > widest:
            widest = span
    return widest


def peak_daily_capacity(schedule) -> int:
    """Maximum number of exams scheduled on any single day across the whole schedule."""
    counts = {}
    for (course, moed), exam_date in schedule.assignments.items():
        day = _day_of(exam_date)
        counts[day] = counts.get(day, 0) + 1
    return max(counts.values()) if counts else 0


# Maps each criterion key to the function that computes its metric.
_METRIC_FUNCS = {
    "min_mandatory_spacing": min_mandatory_spacing,
    "avg_exam_spacing": avg_exam_spacing,
    "elective_collisions": elective_collisions,
    "mandatory_window": mandatory_window,
    "peak_daily_capacity": peak_daily_capacity,
}


def compute_metrics(schedule) -> dict:
    """Computes all five metrics for a single schedule, returning a {key: value} dict."""
    return {key: func(schedule) for key, func in _METRIC_FUNCS.items()}


# --------------------------------------------------------------------------- #
# Multi-key sorting
# --------------------------------------------------------------------------- #
def sort_schedules(schedules, criteria):
    """
    Returns a NEW list of schedules ordered by the given criteria, every layer in
    descending order.

    :param schedules: iterable of Schedule objects (the already-valid results).
    :param criteria:  ordered list of metric keys. The first entry is the primary
                      sort key, the next the secondary, and so on. Unknown or
                      duplicate keys are ignored.
    :return: a list of Schedule objects in the requested order.
    """
    schedules = list(schedules)

    # Keep only valid keys, preserving priority order and dropping duplicates.
    seen = set()
    keys = []
    for key in (criteria or []):
        if key in _METRIC_FUNCS and key not in seen:
            seen.add(key)
            keys.append(key)

    if not keys:
        return schedules

    # Decorate-sort-undecorate: compute metrics once per schedule, then sort by a
    # tuple of the selected metrics. reverse=True makes EVERY layer descending,
    # which is exactly the required behaviour.
    decorated = [(compute_metrics(s), s) for s in schedules]
    decorated.sort(key=lambda pair: tuple(pair[0][k] for k in keys), reverse=True)
    return [s for _, s in decorated]