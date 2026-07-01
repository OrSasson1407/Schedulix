"""
BacktrackScheduler.py
ULTRA-FAST STREAMING CSP Scheduler — Redesigned Edition

ALGORITHM IMPROVEMENTS OVER V1:
  1. NO SUBPROCESS OVERHEAD: Pure single-process generator pipeline.
  2. MAC (MAINTAINING ARC CONSISTENCY): AC3 restricted to affected arcs.
  3. TRAIL STACK (O(CHANGED) UNDO): Undo is O(changed) via an explicit trail.
  4. CONFLICT-DIRECTED BACKJUMPING (CBJ): Skips intermediate valid levels on wipeouts.
  5. LAZY COMPONENT CHAINING: Generators composed lazily with caching for small sets.
  6. SYMMETRY BREAKING: Interchangeable dates are grouped to prune symmetric branches.
  7. LCV (LEAST-CONSTRAINING VALUE): Bitmask popcount value ordering.
"""

import time
import collections
import heapq
import itertools
from datetime import datetime
from .Scheduler import Scheduler
from ..models.Schedule import Schedule


# ---------------------------------------------------------------------------
# Tuneable constants
# ---------------------------------------------------------------------------
NODE_CHECK_INTERVAL = 5_000          # How often to check wall-clock time limit
USE_MAC             = True           # Maintaining Arc Consistency after each assignment
USE_LCV             = True           # Least-Constraining Value ordering
LCV_DOMAIN_LIMIT    = 30             # Only sort by LCV if domain size <= this
USE_CBJ             = True           # Conflict-Directed Backjumping
USE_SYMMETRY        = True           # Skip symmetric (interchangeable) domain values
MAX_CACHE_SOLS      = 1000           # Materialize components with <= this many sols


# ---------------------------------------------------------------------------
# Bit utility: iterate set bits in an integer bitmask
# ---------------------------------------------------------------------------
def _bits(mask: int):
    """Yield the index of each set bit in mask, lowest first."""
    while mask:
        lsb  = mask & (-mask)
        yield lsb.bit_length() - 1
        mask &= mask - 1


def _bit_count(mask: int) -> int:
    # PERF: native Python 3.10+ C implementation, avoids string allocations
    return mask.bit_count()


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------
def _courses_conflict(course_a, course_b) -> bool:
    """Return True if scheduling course_a and course_b on the same day is forbidden."""
    a_map: dict = {}
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


# ---------------------------------------------------------------------------
# Connected-component decomposition
# ---------------------------------------------------------------------------
def _connected_components(n: int, adj: list[list[int]]) -> list[list[int]]:
    """BFS decomposition of the conflict graph into independent sub-problems."""
    visited   = [False] * n
    components: list[list[int]] = []
    for start in range(n):
        if visited[start]:
            continue
        comp:  list[int] = []
        queue: collections.deque = collections.deque([start])
        visited[start] = True
        while queue:
            v = queue.popleft()
            comp.append(v)
            for nb in adj[v]:
                if not visited[nb]:
                    visited[nb] = True
                    queue.append(nb)
        components.append(comp)
    return components


# ---------------------------------------------------------------------------
# Core CSP solver for a single connected component
# ---------------------------------------------------------------------------
def _solve_component(
    n:        int,
    adj:      list[list[int]],   # adjacency list (local indices)
    domains:  list[int],         # bitmask domain per variable
    deadline: float,             # monotonic time of hard cutoff
    aborted:  list[bool],        # shared abort flag (list for mutability)
):
    node_counter = [0]

    # -----------------------------------------------------------------------
    # Symmetry Precomputation (Index Space)
    # -----------------------------------------------------------------------
    if USE_SYMMETRY:
        footprint: dict[int, frozenset] = {}
        all_bits: set[int] = set()
        for d in domains:
            tmp = d
            while tmp:
                b = tmp & (-tmp)
                all_bits.add(b)
                tmp &= tmp - 1
        for b in all_bits:
            fp = frozenset(i for i in range(n) if domains[i] & b)
            footprint[b] = fp
            
        fp_to_bits: dict[frozenset, list[int]] = {}
        for b, fp in footprint.items():
            fp_to_bits.setdefault(fp, []).append(b)
            
        # canonical maps day_idx -> canonical_day_idx
        canonical: dict[int, int] = {}
        for fp, bits in fp_to_bits.items():
            bits.sort()
            canon_idx = bits[0].bit_length() - 1
            for b in bits:
                canonical[b.bit_length() - 1] = canon_idx
    else:
        canonical = {}

    # -----------------------------------------------------------------------
    # MAC
    # -----------------------------------------------------------------------
    def mac_propagate(
        var:          int,
        assigned_bit: int,
        domains:      list[int],
        trail:        list[tuple[int, int]],
        pq:           list
    ) -> bool:
        queue: collections.deque = collections.deque()
        for nb in adj[var]:
            queue.append((nb, var))

        while queue:
            i, j = queue.popleft()
            support_mask = domains[j]
            if support_mask == 0:
                return False
                
            # True AC3 for != constraints: prune 'b' from i if 'b' has no support in j.
            # Support is entirely absent ONLY when domains[j] is forced to exactly 'b'.
            if _bit_count(support_mask) == 1:
                forced_bit = support_mask
                if domains[i] & forced_bit:
                    trail.append((i, domains[i]))
                    domains[i] &= ~forced_bit
                    if domains[i] == 0:
                        return False
                    heapq.heappush(pq, (_bit_count(domains[i]), -len(adj[i]), i))
                    
                    for k in adj[i]:
                        if k != j:
                            queue.append((k, i))
        return True

    # -----------------------------------------------------------------------
    # Trail Undo
    # -----------------------------------------------------------------------
    def undo(domains: list[int], trail: list, target_len: int, pq: list) -> None:
        while len(trail) > target_len:
            v, old_mask = trail.pop()
            domains[v] = old_mask
            heapq.heappush(pq, (_bit_count(old_mask), -len(adj[v]), v))

    # -----------------------------------------------------------------------
    # Lazy Min-Heap Variable Ordering (MRV + Degree)
    # -----------------------------------------------------------------------
    def pick_var(unassigned: int, domains: list[int], pq: list) -> int:
        while pq:
            sz, neg_deg, v = pq[0]
            # Discard if already assigned
            if not ((unassigned >> v) & 1):
                heapq.heappop(pq)
                continue
            actual_sz = _bit_count(domains[v])
            # Discard stale records
            if actual_sz > sz:
                heapq.heappop(pq)
                continue
            return heapq.heappop(pq)[2]
        return -1

    # -----------------------------------------------------------------------
    # LCV
    # -----------------------------------------------------------------------
    def order_values(var: int, domain_mask: int, domains: list[int], unassigned: int) -> list[int]:
        sz = _bit_count(domain_mask)
        bits = list(_bits(domain_mask))
        
        # Fast paths
        if sz <= 1:
            return bits
        if not USE_LCV or sz > LCV_DOMAIN_LIMIT:
            return bits
            
        def lcv_score(b: int) -> int:
            count = 0
            bit = 1 << b
            for nb in adj[var]:
                if (unassigned >> nb) & 1:
                    count += bool(domains[nb] & bit)
            return count

        if sz == 2:
            s0 = lcv_score(bits[0])
            s1 = lcv_score(bits[1])
            return bits if s0 <= s1 else [bits[1], bits[0]]

        bits.sort(key=lcv_score)
        return bits

    # -----------------------------------------------------------------------
    # Backtracking with CBJ
    # -----------------------------------------------------------------------
    def backtrack(
        assignment:  list[int | None],
        unassigned:  int,              
        depth:       int,
        trail:       list[tuple[int, int]],
        domains:     list[int],
        conf_sets:   list[set[int]],   
        pq:          list
    ):
        node_counter[0] += 1
        if node_counter[0] % NODE_CHECK_INTERVAL == 0:
            if time.monotonic() > deadline:
                aborted[0] = True

        if aborted[0]: return set()
        if unassigned == 0:
            yield list(assignment)
            return set()

        var = pick_var(unassigned, domains, pq)
        if var == -1: return set()
        
        # Clear inherited stale constraints
        conf_sets[var].clear()

        domain_mask = domains[var]
        if domain_mask == 0: 
            heapq.heappush(pq, (_bit_count(domains[var]), -len(adj[var]), var))
            return set()

        ordered_values = order_values(var, domain_mask, domains, unassigned)
        failed_canonical: set[int] = set()
        conflict_set: set[int] = set()
        trail_before = len(trail)

        for day_idx in ordered_values:
            if aborted[0]: break

            bit = 1 << day_idx

            if USE_SYMMETRY:
                canon_idx = canonical.get(day_idx, day_idx)
                if canon_idx in failed_canonical and canon_idx != day_idx:
                    conflict_set.update(conf_sets[var])
                    continue

            assignment[var] = day_idx
            new_unassigned = unassigned & ~(1 << var)

            trail_mark = len(trail)
            wipeout    = False

            for nb in adj[var]:
                if (new_unassigned >> nb) & 1:
                    if domains[nb] & bit:
                        trail.append((nb, domains[nb]))
                        domains[nb] &= ~bit
                        heapq.heappush(pq, (_bit_count(domains[nb]), -len(adj[nb]), nb))
                        if domains[nb] == 0:
                            wipeout = True
                            conf_sets[nb].add(var)
                            break

            if not wipeout and USE_MAC:
                wipeout = not mac_propagate(var, bit, domains, trail, pq)

            if wipeout:
                undo(domains, trail, trail_mark, pq)
                assignment[var] = None
                if USE_SYMMETRY:
                    failed_canonical.add(canonical.get(day_idx, day_idx))
                conflict_set.update(conf_sets[var])
                continue

            child_gen = backtrack(
                assignment, new_unassigned, depth + 1,
                trail, domains, conf_sets, pq
            )

            found_any = False
            child_conflict = set()
            try:
                while True:
                    sol = next(child_gen)
                    found_any = True
                    yield sol
            except StopIteration as e:
                child_conflict = e.value or set()

            undo(domains, trail, trail_mark, pq)
            assignment[var] = None

            if not found_any:
                if USE_SYMMETRY:
                    failed_canonical.add(canonical.get(day_idx, day_idx))
                conflict_set.update(child_conflict - {var})

                if USE_CBJ and conflict_set and var not in conflict_set:
                    undo(domains, trail, trail_before, pq)
                    heapq.heappush(pq, (_bit_count(domains[var]), -len(adj[var]), var))
                    return conflict_set
            else:
                conflict_set.clear()

        undo(domains, trail, trail_before, pq)
        heapq.heappush(pq, (_bit_count(domains[var]), -len(adj[var]), var))
        return conflict_set

    # -----------------------------------------------------------------------
    # Entry point
    # -----------------------------------------------------------------------
    local_domains = list(domains)

    ac3_queue: collections.deque = collections.deque()
    for i in range(n):
        for j in adj[i]:
            ac3_queue.append((i, j))
            
    while ac3_queue:
        i, j = ac3_queue.popleft()
        if _bit_count(local_domains[j]) == 1:
            bit = local_domains[j]
            if local_domains[i] & bit:
                local_domains[i] &= ~bit
                if local_domains[i] == 0:
                    return
                for k in adj[i]:
                    if k != j:
                        ac3_queue.append((k, i))

    assignment  = [None] * n
    trail:       list[tuple[int, int]] = []
    conf_sets:   list[set[int]] = [set() for _ in range(n)]
    initial_unassigned = (1 << n) - 1

    pq = []
    for i in range(n):
        heapq.heappush(pq, (_bit_count(local_domains[i]), -len(adj[i]), i))

    gen = backtrack(assignment, initial_unassigned, 0, trail, local_domains, conf_sets, pq)
    try:
        while True:
            yield next(gen)
            if aborted[0]: break
    except StopIteration:
        pass


# ---------------------------------------------------------------------------
# Component-decomposed solver
# ---------------------------------------------------------------------------
def _solve_period(
    n:              int,
    adj:            list[list[int]],
    domains:        list[int],
    deadline:       float,
    aborted:        list[bool],
):
    components = _connected_components(n, adj)
    comp_specs = []
    
    for comp_indices in components:
        local      = {orig: loc for loc, orig in enumerate(comp_indices)}
        cn         = len(comp_indices)
        cadj       = [[] for _ in range(cn)]
        cdom       = [domains[orig] for orig in comp_indices]
        for orig in comp_indices:
            for nb in adj[orig]:
                cadj[local[orig]].append(local[nb])
        comp_specs.append((comp_indices, cadj, cdom))

    comp_sols = {}
    shared_partial = [0] * n

    def combine(comp_idx: int):
        if comp_idx == len(comp_specs):
            yield list(shared_partial)
            return

        comp_indices, cadj, cdom = comp_specs[comp_idx]

        # Logic: Cache solutions locally if the space is small
        if comp_idx not in comp_sols:
            gen = _solve_component(len(comp_indices), cadj, cdom, deadline, aborted)
            sols = []
            for sol in gen:
                sols.append(sol)
                if len(sols) > MAX_CACHE_SOLS:
                    break
            else:
                comp_sols[comp_idx] = sols
            
            if comp_idx not in comp_sols:
                iterable = itertools.chain(sols, gen)
                comp_sols[comp_idx] = None 
            else:
                iterable = comp_sols[comp_idx]
        else:
            if comp_sols[comp_idx] is not None:
                iterable = comp_sols[comp_idx]
            else:
                iterable = _solve_component(len(comp_indices), cadj, cdom, deadline, aborted)

        # Replay/Generate and apply assignments to the shared state array
        for local_sol in iterable:
            if aborted[0]: break
            for loc_i, orig_i in enumerate(comp_indices):
                shared_partial[orig_i] = local_sol[loc_i]
            yield from combine(comp_idx + 1)

    yield from combine(0)


def _pin_date_index(available_dates, date_str: str):
    """Map YYYY-MM-DD to the index of that day in available_dates, or None."""
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None
    for idx, date_obj in enumerate(available_dates):
        raw = date_obj.date
        day = raw.date() if hasattr(raw, "date") else raw
        if day == target:
            return idx
    return None


# ---------------------------------------------------------------------------
# Main scheduler class
# ---------------------------------------------------------------------------
class BacktrackScheduler(Scheduler):
    TIME_LIMIT_SECONDS = 28
    _graph_cache: dict = {}

    def generate(self, courses: list, exam_periods: list, constraints=None, pinned=None):
        exam_courses = [c for c in courses if c.is_exam_required()]
        if not exam_courses or not exam_periods:
            return

        # Optional user-defined hard constraints. A schedule that violates any
        # active constraint is dropped before it is ever yielded to the caller.
        apply_constraints = constraints is not None and constraints.any_enabled()
        pinned = pinned or {}

        deadline   = time.monotonic() + self.TIME_LIMIT_SECONDS
        aborted    = [False]

        n_all = len(exam_courses)
        conflict_flat = [False] * (n_all * n_all)
        for i in range(n_all):
            for j in range(i + 1, n_all):
                if _courses_conflict(exam_courses[i], exam_courses[j]):
                    conflict_flat[i * n_all + j] = True
                    conflict_flat[j * n_all + i] = True

        course_index = {c.course_id: idx for idx, c in enumerate(exam_courses)}

        for period in exam_periods:
            if aborted[0] or time.monotonic() > deadline: break

            available_dates = period.get_available_dates()
            if not available_dates: continue

            period_courses = [
                c for c in exam_courses
                if period.semester in {prog.semester for prog in c.programs}
            ]
            if not period_courses: continue

            n = len(period_courses)

            cache_key = (
                period.semester,
                period.moed,
                frozenset(c.course_id for c in period_courses),
            )
            if cache_key in BacktrackScheduler._graph_cache:
                adj = BacktrackScheduler._graph_cache[cache_key]
            else:
                adj = [[] for _ in range(n)]
                for i in range(n):
                    gi = course_index[period_courses[i].course_id]
                    for j in range(i + 1, n):
                        gj = course_index[period_courses[j].course_id]
                        if conflict_flat[gi * n_all + gj]:
                            adj[i].append(j)
                            adj[j].append(i)
                BacktrackScheduler._graph_cache[cache_key] = adj

            domains = [0] * n
            for i, c in enumerate(period_courses):
                c_sems = {prog.semester for prog in c.programs}
                mask   = 0
                for d_idx, date_obj in enumerate(available_dates):
                    if date_obj.semester in c_sems:
                        mask |= (1 << d_idx)
                if c.course_id in pinned:
                    pin_idx = _pin_date_index(available_dates, pinned[c.course_id])
                    mask = (1 << pin_idx) if pin_idx is not None else 0
                domains[i] = mask

            for assignment in _solve_period(n, adj, domains, deadline, aborted):
                if aborted[0] or time.monotonic() > deadline:
                    aborted[0] = True
                    break

                schedule = Schedule()
                for idx, d_idx in enumerate(assignment):
                    schedule.add_assignment(
                        period_courses[idx],
                        period.moed,
                        available_dates[d_idx],
                    )

                # Hard-constraint gate: disqualify any schedule that violates an
                # active user-configured constraint instead of yielding it.
                if apply_constraints and not constraints.is_satisfied_by(schedule):
                    continue

                yield schedule