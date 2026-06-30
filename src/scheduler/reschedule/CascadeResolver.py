"""
CascadeResolver.py
Finds the MINIMAL sequence of cascading exam moves that returns a hypothetical
schedule to a fully legal state.

Modelled as a shortest-path search over a tree of ScheduleStates:
  * node      = a hypothetical ScheduleState
  * edge      = one Move of a non-pinned exam (cost 1)
  * goal      = a state whose ViolationReport is legal (no hard violations)
  * heuristic = number of independent violation components (admissible, so A*
                returns a provably minimal-length cascade)

The search is bounded by a maximum cascade depth and a wall-clock budget so the
UI stays responsive; if no legal state is reachable within those bounds it
returns None (and the caller can surface the remaining violations).
"""

import heapq
import time
import itertools


class CascadeResolver:
    def __init__(self, max_cascade: int = 5, time_budget_ms: int = 400):
        self.max_cascade = max_cascade
        self.deadline_s = time_budget_ms / 1000.0

    def resolve(self, start_state, evaluate_fn, successors_fn):
        """
        :param start_state:   ScheduleState with the forced user move already applied
                              (and that exam pinned).
        :param evaluate_fn:   state -> ViolationReport
        :param successors_fn: (state, report) -> iterable[Move]
        :return: list[Move] (possibly empty if already legal) or None if unsolved.
        """
        t0 = time.monotonic()
        start_report = evaluate_fn(start_state)
        if start_report.is_legal:
            return []

        counter = itertools.count()
        h0 = len(start_report.components())
        # frontier entries: (f, tiebreak, g, state, path, report)
        frontier = [(h0, next(counter), 0, start_state, [], start_report)]
        best_g = {start_state.signature(): 0}

        while frontier:
            if time.monotonic() - t0 > self.deadline_s:
                break

            f, _, g, state, path, report = heapq.heappop(frontier)

            if report.is_legal:
                return path
            if g >= self.max_cascade:
                continue

            for move in successors_fn(state, report):
                nxt = state.with_move(move)
                sig = nxt.signature()
                ng = g + 1
                prev = best_g.get(sig)
                if prev is not None and prev <= ng:
                    continue
                best_g[sig] = ng

                nreport = evaluate_fn(nxt)
                nh = len(nreport.components())
                heapq.heappush(
                    frontier,
                    (ng + nh, next(counter), ng, nxt, path + [move], nreport),
                )

        return None
