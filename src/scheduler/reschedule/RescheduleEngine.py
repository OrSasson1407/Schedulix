"""
RescheduleEngine.py
Facade that the UI / Flask controller talks to. It owns the baseline schedule for
a single moed, the moed's available dates, and the active hard-constraint set, and
exposes three operations:

  preview(course_id, new_date)  -> ViolationReport      (instant; the cascade view)
  resolve(course_id, new_date)  -> dict with before/after reports + minimal plan
  apply(course_id, new_date)    -> mutates the Schedule in place with move + cascade

The engine is framework-free: it depends only on the domain models and the other
reschedule helpers, so it is fully unit-testable and reusable outside Flask.
"""

from src.models.Schedule import Schedule
from .Move import Move
from .ScheduleState import ScheduleState
from .ConstraintEvaluator import ConstraintEvaluator
from .CascadeResolver import CascadeResolver


class RescheduleEngine:
    def __init__(self, schedule, available_dates, moed, constraints,
                 max_cascade=5, time_budget_ms=400, companion_dates=None, locked=None):
        self.moed = moed
        self.constraints = constraints
        self.evaluator = ConstraintEvaluator(constraints, companion_dates)
        self.resolver = CascadeResolver(max_cascade, time_budget_ms)
        # course_ids that are locked by the user and must never move (drag or cascade).
        self.locked = set(locked or [])

        # Build the date<->ordinal indexes. Dates already on the schedule that are
        # somehow outside the available list are appended so they remain movable.
        self.available = list(available_dates)
        self.date_to_ord = {ed.date.strftime("%Y-%m-%d"): i for i, ed in enumerate(self.available)}

        self.registry = {}
        assignments = {}
        for (course, moed_key), exam_date in schedule.assignments.items():
            self.registry[course.course_id] = course
            ds = exam_date.date.strftime("%Y-%m-%d")
            if ds not in self.date_to_ord:
                self.date_to_ord[ds] = len(self.available)
                self.available.append(exam_date)
            assignments[(course.course_id, moed_key)] = self.date_to_ord[ds]

        # Locked exams are pinned from the start so the cascade can never move them.
        pins = frozenset((cid, self.moed) for cid in self.locked if (cid, self.moed) in assignments)
        self.initial_state = ScheduleState(frozenset(assignments.items()), pins)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def preview(self, course_id, new_date):
        """Applies just the dragged move and reports the resulting violations."""
        state = self._forced_state(course_id, new_date)
        return self.evaluator.evaluate(self._schedule_from_state(state))

    def resolve(self, course_id, new_date):
        """
        Applies + pins the dragged move, then searches for the minimal cascade.
        Returns a JSON-friendly dict describing the cascade effect and the plan.
        """
        forced = self._forced_state(course_id, new_date).with_pin(course_id, self.moed)
        before = self.evaluator.evaluate(self._schedule_from_state(forced))

        plan = self.resolver.resolve(forced, self._evaluate_state, self._successors)

        if plan is None:
            return {
                "ok": True,
                "solved": False,
                "before": before.to_dict(),
                "plan": [],
                "after": before.to_dict(),
            }

        final = forced
        for mv in plan:
            final = final.with_move(mv)
        after = self.evaluator.evaluate(self._schedule_from_state(final))

        return {
            "ok": True,
            "solved": True,
            "before": before.to_dict(),
            "plan": [self._move_to_dict(mv) for mv in plan],
            "after": after.to_dict(),
        }

    def apply(self, course_id, new_date, schedule):
        """
        Applies the dragged move plus its resolved cascade directly onto the given
        Schedule object (mutating it in place). Returns the applied move list and
        the post-apply report. If no cascade was found, only the forced move is
        applied so the user can still force the change and see what remains.
        """
        forced = self._forced_state(course_id, new_date).with_pin(course_id, self.moed)
        plan = self.resolver.resolve(forced, self._evaluate_state, self._successors)

        final = forced
        applied = []
        if plan:
            applied = [self._move_to_dict(mv) for mv in plan]
            for mv in plan:
                final = final.with_move(mv)

        # Write the final assignments back onto the real Schedule.
        new_schedule = self._schedule_from_state(final)
        schedule.assignments = new_schedule.assignments

        report = self.evaluator.evaluate(new_schedule)
        forced_move = self._move_to_dict(
            Move(course_id, self.moed,
                 self.initial_state.as_map()[(course_id, self.moed)],
                 self.date_to_ord[new_date])
        )
        return {
            "ok": True,
            "solved": report.is_legal,
            "forced_move": forced_move,
            "cascade": applied,
            "after": report.to_dict(),
        }

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _forced_state(self, course_id, new_date):
        if (course_id, self.moed) not in self.initial_state.as_map():
            raise ValueError(f"Unknown exam: {course_id} ({self.moed})")
        if course_id in self.locked:
            raise ValueError("This exam is locked — unlock it before moving it")
        if new_date not in self.date_to_ord:
            raise ValueError(f"Date {new_date} is not available in this period")
        cur = self.initial_state.as_map()[(course_id, self.moed)]
        return self.initial_state.with_move(
            Move(course_id, self.moed, cur, self.date_to_ord[new_date])
        )

    def _schedule_from_state(self, state):
        sch = Schedule()
        for (cid, moed), ordn in state.as_map().items():
            sch.add_assignment(self.registry[cid], moed, self.available[ordn])
        return sch

    def _evaluate_state(self, state):
        return self.evaluator.evaluate(self._schedule_from_state(state))

    def _successors(self, state, report):
        """
        Violation-directed successor generation: only relocate exams that currently
        participate in a hard violation, and skip target dates that would create a
        new baseline mandatory clash (those can never be part of a legal solution).
        """
        involved = report.involved_courses()
        smap = state.as_map()
        n = len(self.available)
        moves = []
        for (cid, moed), cur in smap.items():
            if cid not in involved or (cid, moed) in state.pinned:
                continue
            for ordn in range(n):
                if ordn == cur:
                    continue
                if not self._baseline_safe(smap, cid, ordn):
                    continue
                moves.append(Move(cid, moed, cur, ordn))
        return moves

    def _baseline_safe(self, smap, course_id, ordinal):
        course = self.registry[course_id]
        obl_keys = {
            (p.program_id, p.year) for p in course.programs if p.requirement == "Obligatory"
        }
        if not obl_keys:
            return True  # electives may share a day
        for (other_id, _moed), other_ord in smap.items():
            if other_id == course_id or other_ord != ordinal:
                continue
            other = self.registry[other_id]
            for p in other.programs:
                if p.requirement == "Obligatory" and (p.program_id, p.year) in obl_keys:
                    return False
        return True

    def _move_to_dict(self, move: Move):
        return {
            "course_id": move.course_id,
            "course_name": self.registry[move.course_id].name,
            "moed": move.moed,
            "from_date": self.available[move.from_ordinal].date.strftime("%Y-%m-%d"),
            "to_date": self.available[move.to_ordinal].date.strftime("%Y-%m-%d"),
        }
