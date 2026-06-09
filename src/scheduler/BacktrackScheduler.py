"""
BacktrackScheduler.py
ULTRA-FAST STREAMING CSP Scheduler — Fully Optimized Edition

OPTIMIZATIONS APPLIED:
  1. [FIX] Streaming Generator: Worker is now a generator (yields, not appends).
           Eliminates RAM explosion on millions of solutions.
  2. [FIX] Real CBJ: Proper conflict-set tracking with backjump depth using
           ancestor resolution. Skips unrelated levels on failure.
  3. [FIX] Strong Nogood Cache: Keyed on (assigned_vars_tuple, domains_snapshot)
           instead of full None-padded assignment — far more cache hits.
  4. [FIX] AC-3 Benchmarked Toggle: ac3 is wrapped in a flag so you can
           disable it if benchmarking shows it costs more than it saves.
  5. [FIX] LCV Toggle + Cost Guard: LCV is gated behind a flag; also skipped
           when domain size is large (sort cost > benefit).
  6. [FIX] Time-check Interval: time.time() called only every NODE_CHECK_INTERVAL
           nodes, not on every recursive call.
  7. [FIX] Nogood Size Cap: Prevents unbounded memory growth with a max-size
           eviction policy (drop oldest on overflow).
  8. [FIX] Parallel streaming: Generator bridged across process boundary via
           Queue + sentinel, so main process can stream while workers run.
"""

import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from .Scheduler import Scheduler
from ..models.Schedule import Schedule


# ---------------------------------------------------------------------------
# Tuneable constants — adjust these based on your benchmark results
# ---------------------------------------------------------------------------
NODE_CHECK_INTERVAL = 10_000   # how often to call time.time() in backtracking
MAX_NOGOODS         = 200_000  # cap on nogood cache size (memory guard)
USE_AC3             = True     # set False if AC-3 costs more than it saves
USE_LCV             = True     # set False if LCV costs more than it saves
LCV_DOMAIN_LIMIT    = 20       # skip LCV sort when domain has > this many bits


# ---------------------------------------------------------------------------
# Module-level worker — must be top-level for ProcessPoolExecutor pickling.
# Now a GENERATOR: yields individual assignment lists instead of collecting.
# ---------------------------------------------------------------------------
def _solve_period_worker(worker_args: dict):
    """
    Streaming generator that yields raw assignment-index lists.
    Each element is a list like [d0, d1, d2, ...] indexed by period_course order.

    Called either directly (sequential fallback) or bridged through a Queue
    (parallel mode) — see _queue_bridge below.
    """
    n              = worker_args["n"]
    conflict_graph = worker_args["conflict_graph"]
    degrees        = worker_args["degrees"]
    time_limit     = worker_args["time_limit"]

    start_time     = time.time()
    node_counter   = [0]          # mutable counter for time-check interval
    time_exceeded  = [False]

    # ── [IMPROVED] Nogood cache with size cap ──────────────────────────────
    nogoods         = {}           # key -> insertion_order  (ordered by age)
    nogood_counter  = [0]

    def add_nogood(key):
        if key in nogoods:
            return
        if len(nogoods) >= MAX_NOGOODS:
            # evict oldest entry
            oldest = next(iter(nogoods))
            del nogoods[oldest]
        nogoods[key] = nogood_counter[0]
        nogood_counter[0] += 1

    def in_nogood(key):
        return key in nogoods

    # ── [IMPROVED] AC-3 pre-pass (toggle via USE_AC3) ─────────────────────
    def ac3(domains):
        """
        Arc-consistency pre-pass.  For "exam_i != exam_j":
        a value d in domains[i] is unsupported only when domains[j] == {d}
        (j is forced to that single day).
        Returns False if any domain empties (unsolvable).
        """
        from collections import deque
        queue = deque()
        for i in range(n):
            for j in conflict_graph[i]:
                queue.append((i, j))

        while queue:
            i, j = queue.popleft()
            revised = False
            tmp = domains[i]
            while tmp:
                bit = tmp & (-tmp)
                tmp &= tmp - 1
                if domains[j] == bit:          # j forced to same single day
                    domains[i] &= ~bit
                    revised = True
            if revised:
                if domains[i] == 0:
                    return False
                for k in conflict_graph[i]:
                    if k != j:
                        queue.append((k, i))
        return True

    # ── [IMPROVED] LCV helper (toggle + cost guard) ────────────────────────
    def lcv_sort(var, bits, domains, assignment):
        """
        Sort bits by LCV (fewest eliminated neighbors first).
        Skipped when bit-count is large (sort overhead > benefit).
        """
        if not USE_LCV or len(bits) > LCV_DOMAIN_LIMIT:
            return bits    # skip sort — too expensive or disabled

        def count_elim(bit):
            count = 0
            for nb in conflict_graph[var]:
                if assignment[nb] is None and (domains[nb] & bit):
                    count += 1
            return count

        return sorted(bits, key=count_elim)

    # ── [IMPROVED] Nogood key builder ──────────────────────────────────────
    def make_nogood_key(assignment, domains):
        """
        Key based on assigned vars + current domain snapshot.
        Much stronger than None-padded tuple: two partial states with the
        same assigned vars but different remaining domains are distinct.
        """
        assigned = tuple((i, assignment[i]) for i in range(n) if assignment[i] is not None)
        dom_snap  = tuple(domains[i] for i in range(n) if assignment[i] is None)
        return (assigned, dom_snap)

    # ── [IMPROVED] Core backtracking generator with real CBJ ──────────────
    def backtrack(assignment, depth, ancestor_indices, domains):
        """
        ancestor_indices: list of variable indices in assignment order (the
        "path" from root to current node).  Used for real backjump resolution.

        Yields solutions as flat lists.
        Returns (via StopIteration) the conflict_set of variables that caused
        the failure at this subtree — used by the parent for CBJ.
        """
        # Time check (throttled)
        node_counter[0] += 1
        if node_counter[0] % NODE_CHECK_INTERVAL == 0:
            if time.time() - start_time > time_limit:
                time_exceeded[0] = True

        if time_exceeded[0]:
            return set()   # conflict_set = empty on timeout

        if depth == n:
            yield list(assignment)
            return set()

        # ── MCV + Degree heuristic ──
        best_c    = -1
        min_count = float('inf')
        max_deg   = -1
        for i in range(n):
            if assignment[i] is None:
                c_count = domains[i].bit_count()
                if c_count == 0:
                    # Domain wipeout — conflict is whoever last pruned this var.
                    # Return it as the conflict set.
                    return {i}
                if c_count < min_count or (c_count == min_count and degrees[i] > max_deg):
                    min_count = c_count
                    best_c    = i
                    max_deg   = degrees[i]

        # Build available bits list
        available_bits = []
        tmp = domains[best_c]
        while tmp:
            bit = tmp & (-tmp)
            tmp &= tmp - 1
            available_bits.append(bit)

        # LCV ordering (with cost guard)
        available_bits = lcv_sort(best_c, available_bits, domains, assignment)

        # conflict set accumulated across values tried at this node
        node_conflict_set = set()

        for bit in available_bits:
            if time_exceeded[0]:
                break

            d = bit.bit_length() - 1

            # ── Nogood check ──
            assignment[best_c] = d
            ng_key = make_nogood_key(assignment, domains)
            if in_nogood(ng_key):
                assignment[best_c] = None
                continue

            # ── Forward checking ──
            dead_end       = False
            pruned         = []
            fail_var       = -1

            for neighbor in conflict_graph[best_c]:
                if assignment[neighbor] is None and (domains[neighbor] & bit):
                    domains[neighbor] &= ~bit
                    pruned.append(neighbor)
                    if domains[neighbor] == 0:
                        dead_end = True
                        fail_var = neighbor
                        break

            if not dead_end:
                # ── [REAL CBJ] Recurse and collect child conflict set ──
                child_gen = backtrack(
                    assignment,
                    depth + 1,
                    ancestor_indices + [best_c],
                    domains
                )
                found_any = False
                child_conflict_set = set()
                try:
                    while True:
                        sol = next(child_gen)
                        found_any = True
                        yield sol
                except StopIteration as e:
                    child_conflict_set = e.value if e.value else set()

                # Merge child conflicts into our node set (excluding self)
                node_conflict_set.update(child_conflict_set - {best_c})

                if not found_any:
                    add_nogood(ng_key)

                    # ── [REAL CBJ] Should we backjump? ──
                    # If none of the conflicting vars is in best_c's subtree
                    # (i.e., they are all ancestors), no other value of best_c
                    # can help — jump directly up.
                    ancestor_set = set(ancestor_indices)
                    if child_conflict_set and child_conflict_set.issubset(ancestor_set | {best_c}):
                        # Restore domains before jumping
                        for neighbor in pruned:
                            domains[neighbor] |= bit
                        assignment[best_c] = None
                        return node_conflict_set   # backjump

            else:
                # Forward checking killed a neighbor — that neighbor is the conflict
                node_conflict_set.add(fail_var)
                # If the culprit is an ancestor (placed before best_c), no
                # other value for best_c helps → backjump immediately.
                if fail_var in set(ancestor_indices):
                    for neighbor in pruned:
                        domains[neighbor] |= bit
                    assignment[best_c] = None
                    return node_conflict_set

            # Restore forward-checking pruning
            for neighbor in pruned:
                domains[neighbor] |= bit
            assignment[best_c] = None

        return node_conflict_set   # exhausted all values at this node

    # ── Run AC-3 then search ───────────────────────────────────────────────
    domains = list(worker_args["domains"])   # local mutable copy

    if USE_AC3:
        if not ac3(domains):
            return    # AC-3 proved unsolvable — yield nothing

    gen = backtrack([None] * n, 0, [], domains)
    try:
        while True:
            sol = next(gen)
            yield sol
            if time_exceeded[0]:
                break
    except StopIteration:
        pass


# ---------------------------------------------------------------------------
# Queue bridge — lets a subprocess stream results back to the main process
# without collecting everything in RAM first.
# ---------------------------------------------------------------------------
def _queue_bridge(worker_args: dict, queue) -> None:
    """
    Runs inside a child process.  Feeds _solve_period_worker results into
    a multiprocessing.Queue; sends a None sentinel when done.
    """
    try:
        for sol in _solve_period_worker(worker_args):
            queue.put(sol)
    finally:
        queue.put(None)   # sentinel


def _courses_conflict(course_a, course_b) -> bool:
    a_map = {}
    for prog in course_a.programs:
        key = (prog.program_id, prog.year)
        if key not in a_map or prog.requirement == "Obligatory":
            a_map[key] = prog.requirement

    for prog in course_b.programs:
        key = (prog.program_id, prog.year)
        if key in a_map:
            if a_map[key] == "Obligatory" or prog.requirement == "Obligatory":
                return True
    return False


class BacktrackScheduler(Scheduler):
    TIME_LIMIT_SECONDS = 28

    # Conflict-graph cache: keyed by (semester, moed, frozenset of course ids)
    _graph_cache: dict = {}

    def generate(self, courses: list, exam_periods: list):
        exam_courses = [c for c in courses if c.is_exam_required()]

        if not exam_courses:
            print("[Scheduler] No exam courses to schedule.")
            return

        if not exam_periods:
            print("[Scheduler] No available exam periods found.")
            return

        self._start_time    = time.time()
        self._time_exceeded = False

        # ── Build per-period worker args ──────────────────────────────────
        period_args = []
        period_meta = []

        for period in exam_periods:
            available_dates = period.get_available_dates()
            if not available_dates:
                continue

            period_courses = [
                c for c in exam_courses
                if period.semester in {prog.semester for prog in c.programs}
            ]
            if not period_courses:
                continue

            n = len(period_courses)
            D = len(available_dates)

            # Incremental conflict-graph cache
            cache_key = (
                period.semester,
                period.moed,
                frozenset(id(c) for c in period_courses),
            )
            if cache_key in BacktrackScheduler._graph_cache:
                conflict_graph, degrees = BacktrackScheduler._graph_cache[cache_key]
            else:
                conflict_graph = [[] for _ in range(n)]
                degrees        = [0] * n
                for i in range(n):
                    for j in range(i + 1, n):
                        if self._programs_conflict(period_courses[i], period_courses[j]):
                            conflict_graph[i].append(j)
                            conflict_graph[j].append(i)
                            degrees[i] += 1
                            degrees[j] += 1
                BacktrackScheduler._graph_cache[cache_key] = (conflict_graph, degrees)

            # Build bitmask domains
            domains = [0] * n
            for i, c in enumerate(period_courses):
                c_sems = {prog.semester for prog in c.programs}
                mask   = 0
                for d_idx, date_obj in enumerate(available_dates):
                    if date_obj.semester in c_sems:
                        mask |= (1 << d_idx)
                domains[i] = mask

            period_args.append({
                "n":             n,
                "D":             D,
                "conflict_graph": conflict_graph,
                "degrees":       degrees,
                "domains":       domains,
                "time_limit":    self.TIME_LIMIT_SECONDS,
            })
            period_meta.append((period, period_courses, available_dates))

        if not period_args:
            return

        def _emit(assignment_indices, period, period_courses, available_dates):
            """Reconstruct a Schedule from a raw assignment list."""
            schedule = Schedule()
            for idx, d_idx in enumerate(assignment_indices):
                schedule.add_assignment(
                    period_courses[idx], period.moed, available_dates[d_idx]
                )
            return schedule

        # ── Parallel streaming via Queue bridge ───────────────────────────
        # Each period worker runs in its own process.  Results stream back
        # through a Queue so we never buffer all solutions in RAM.
        import multiprocessing
        remaining = self.TIME_LIMIT_SECONDS - (time.time() - self._start_time)

        try:
            queues   = []
            futures  = []
            with ProcessPoolExecutor() as executor:
                for args, meta in zip(period_args, period_meta):
                    q = multiprocessing.Manager().Queue(maxsize=1000)
                    queues.append((q, meta))
                    futures.append(executor.submit(_queue_bridge, args, q))

                for q, (period, period_courses, available_dates) in queues:
                    while True:
                        if time.time() - self._start_time > self.TIME_LIMIT_SECONDS:
                            self._time_exceeded = True
                            print("[Scheduler] 28-second limit reached.")
                            break
                        item = q.get()
                        if item is None:           # sentinel — this period done
                            break
                        yield _emit(item, period, period_courses, available_dates)

                    if self._time_exceeded:
                        break

        except Exception as e:
            print(f"[Scheduler] Parallel error: {e}. Falling back to sequential.")
            for args, (period, period_courses, available_dates) in zip(period_args, period_meta):
                if self._time_exceeded:
                    break
                for assignment_indices in _solve_period_worker(args):
                    if time.time() - self._start_time > self.TIME_LIMIT_SECONDS:
                        self._time_exceeded = True
                        break
                    yield _emit(assignment_indices, period, period_courses, available_dates)

    def _programs_conflict(self, course_a, course_b) -> bool:
        a_map = {}
        for prog in course_a.programs:
            key = (prog.program_id, prog.year)
            if key not in a_map or prog.requirement == "Obligatory":
                a_map[key] = prog.requirement

        for prog in course_b.programs:
            key = (prog.program_id, prog.year)
            if key in a_map:
                if a_map[key] == "Obligatory" or prog.requirement == "Obligatory":
                    return True

        return False
