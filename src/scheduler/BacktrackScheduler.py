"""
BacktrackScheduler.py
ULTRA-FAST STREAMING CSP Scheduler — Advanced Algorithms Edition

MAJOR CS OPTIMIZATIONS APPLIED:
  1. STATE MEMENTO (TRAIL STACK): Replaced heavy 'pruned' loops with C-speed shallow copies (domains[:]).
  2. O(1) MRV BITMASKING: unassigned_mask uses bit-shifting to skip allocated nodes instantly.
  3. SYMMETRY BREAKING: Pre-calculates Equivalent Days (day_signatures) to skip redundant dead-ends.
  4. PURE IPC QUEUE & MONOTONIC CLOCK: For high-throughput stream yielding.
"""

import time
import itertools
import collections
import random
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from .Scheduler import Scheduler
from ..models.Schedule import Schedule

# ---------------------------------------------------------------------------
# Tuneable constants
# ---------------------------------------------------------------------------
NODE_CHECK_INTERVAL       = 10_000
MAX_NOGOODS               = 200_000
USE_AC3                   = True
USE_LCV                   = True
LCV_DOMAIN_LIMIT          = 20
BATCH_SIZE                = 10_000    
MAX_CARTESIAN_SOLUTIONS   = 50_000    
GIANT_COMPONENT_THRESHOLD = 25        

# O(1) Lookup table for lightning-fast bit decoding
BIT_TO_IDX = { (1 << i): i for i in range(100) }


def _get_connected_components(n: int, conflict_graph: list) -> list:
    visited = set()
    components = []

    for i in range(n):
        if i not in visited:
            component = []
            queue = collections.deque([i])
            visited.add(i)

            while queue:
                curr = queue.popleft() 
                component.append(curr)
                for neighbor in conflict_graph[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

            components.append(component)

    return components


def _solve_via_min_conflicts(n_comp, comp_graph, comp_domains, time_limit, start_time):
    valid_values = []
    for d in comp_domains:
        vals, tmp = [], d
        while tmp:
            bit = tmp & (-tmp)
            vals.append(BIT_TO_IDX[bit])
            tmp &= tmp - 1
        valid_values.append(vals)

    def count_conflicts(assignment, var, val):
        count = 0
        for neighbor in comp_graph[var]:
            if assignment[neighbor] == val:
                count += 1
        return count

    while time.monotonic() - start_time < time_limit:
        assignment = [random.choice(v) for v in valid_values]
        
        for _ in range(5_000): 
            conflicted_vars = [i for i in range(n_comp) if count_conflicts(assignment, i, assignment[i]) > 0]
            if not conflicted_vars:
                return [assignment] 
            
            var = random.choice(conflicted_vars)
            
            best_val, min_c = assignment[var], float('inf')
            for val in valid_values[var]:
                c = count_conflicts(assignment, var, val)
                if c == 0:
                    best_val = val
                    break
                if c < min_c:
                    min_c = c
                    best_val = val
            assignment[var] = best_val

    return [] 


def _solve_single_component(n_comp, comp_graph, comp_degrees, comp_domains, time_limit, start_time, time_exceeded):
    node_counter   = [0]
    nogoods        = {}
    nogood_counter = [0]

    # CS OPTIMIZATION 3: Symmetry Breaking
    # Group days by their initial domain footprint (which courses allow them).
    day_footprints = collections.defaultdict(list)
    all_bits = set()
    for d in comp_domains:
        tmp = d
        while tmp:
            b = tmp & (-tmp)
            all_bits.add(b)
            tmp &= tmp - 1
            
    for bit in all_bits:
        signature = sum((1 << i) for i in range(n_comp) if (comp_domains[i] & bit))
        day_footprints[signature].append(bit)
        
    symmetric_group = {}
    for sig, bits in day_footprints.items():
        if len(bits) > 1:
            for b in bits: symmetric_group[b] = bits

    def add_nogood(key):
        if key in nogoods: return
        if len(nogoods) >= MAX_NOGOODS:
            oldest = next(iter(nogoods))
            del nogoods[oldest]
        nogoods[key] = nogood_counter[0]
        nogood_counter[0] += 1

    def ac3(domains):
        queue = collections.deque()
        for i in range(n_comp):
            for j in comp_graph[i]:
                queue.append((i, j))

        while queue:
            i, j = queue.popleft()
            revised = False
            tmp = domains[i]
            while tmp:
                bit = tmp & (-tmp)
                tmp &= tmp - 1
                if domains[j] == bit:
                    domains[i] &= ~bit
                    revised = True
            if revised:
                if domains[i] == 0: return False
                for k in comp_graph[i]:
                    if k != j: queue.append((k, i))
        return True

    def lcv_sort(var, bits, domains, unassigned_mask):
        if not USE_LCV or len(bits) > LCV_DOMAIN_LIMIT: return bits
        def count_elim(bit):
            count = 0
            for nb in comp_graph[var]:
                # Check if neighbor is unassigned using the bitmask
                if (unassigned_mask & (1 << nb)) and (domains[nb] & bit):
                    count += 1
            return count
        return sorted(bits, key=count_elim)

    def backtrack(assignment, unassigned_mask, depth, ancestor_indices, domains):
        node_counter[0] += 1
        if node_counter[0] % NODE_CHECK_INTERVAL == 0:
            if time.monotonic() - start_time > time_limit:
                time_exceeded[0] = True

        if time_exceeded[0]: return set()

        if unassigned_mask == 0:
            yield list(assignment)
            return set()

        # CS OPTIMIZATION 2: MRV via Bitmask Iteration (O(1) skips)
        best_c, min_count, max_deg = -1, float('inf'), -1
        tmp_unassigned = unassigned_mask
        
        while tmp_unassigned:
            i = (tmp_unassigned & -tmp_unassigned).bit_length() - 1
            tmp_unassigned &= tmp_unassigned - 1
            
            c_count = domains[i].bit_count()
            if c_count == 0: return {i}
            if c_count < min_count or (c_count == min_count and comp_degrees[i] > max_deg):
                min_count = c_count
                best_c = i
                max_deg = comp_degrees[i]

        available_bits = []
        tmp = domains[best_c]
        while tmp:
            bit = tmp & (-tmp)
            tmp &= tmp - 1
            available_bits.append(bit)

        available_bits = lcv_sort(best_c, available_bits, domains, unassigned_mask)
        node_conflict_set = set()
        
        # CS OPTIMIZATION 1: State Memento (Trail Stack)
        # Fast memory copy instead of logical re-calculation
        saved_domains = domains[:]
        failed_symmetric_bits = set()

        for bit in available_bits:
            if time_exceeded[0]: break
            
            # Symmetry Skip: If an identical day failed from this exact state, skip this one
            if bit in failed_symmetric_bits:
                continue
                
            d = BIT_TO_IDX[bit]
            assignment[best_c] = d
            ng_key = tuple(assignment)
            
            if ng_key in nogoods:
                assignment[best_c] = None
                continue

            dead_end, fail_var = False, -1
            
            for neighbor in comp_graph[best_c]:
                if (unassigned_mask & (1 << neighbor)) and (domains[neighbor] & bit):
                    domains[neighbor] &= ~bit
                    if domains[neighbor] == 0:
                        dead_end = True
                        fail_var = neighbor
                        break

            if not dead_end:
                new_unassigned_mask = unassigned_mask & ~(1 << best_c)
                child_gen = backtrack(assignment, new_unassigned_mask, depth + 1, ancestor_indices + [best_c], domains)
                
                found_any, child_conflict_set = False, set()
                try:
                    while True:
                        sol = next(child_gen)
                        found_any = True
                        yield sol
                except StopIteration as e:
                    child_conflict_set = e.value if e.value else set()

                node_conflict_set.update(child_conflict_set - {best_c})

                if not found_any:
                    add_nogood(ng_key)
                    # If this was a dead branch, record it for symmetry breaking
                    if bit in symmetric_group:
                        failed_symmetric_bits.update(symmetric_group[bit])
                        
                    if child_conflict_set and child_conflict_set.issubset(set(ancestor_indices) | {best_c}):
                        domains[:] = saved_domains # Restore state instantly
                        assignment[best_c] = None
                        return node_conflict_set
            else:
                node_conflict_set.add(fail_var)
                if fail_var in set(ancestor_indices):
                    domains[:] = saved_domains # Restore state instantly
                    assignment[best_c] = None
                    return node_conflict_set

            # Restore state instantly
            domains[:] = saved_domains
            assignment[best_c] = None

        return node_conflict_set

    local_domains = list(comp_domains)
    if USE_AC3 and not ac3(local_domains): return

    initial_unassigned = (1 << n_comp) - 1
    gen = backtrack([None] * n_comp, initial_unassigned, 0, [], local_domains)
    try:
        while True:
            yield next(gen)
            if time_exceeded[0]: break
    except StopIteration:
        pass


def _solve_period_worker(worker_args: dict):
    n              = worker_args["n"]
    conflict_graph = worker_args["conflict_graph"]
    domains        = worker_args["domains"]
    time_limit     = worker_args["time_limit"]

    start_time    = time.monotonic()
    time_exceeded = [False]

    components = _get_connected_components(n, conflict_graph)
    component_solutions = []

    for comp_indices in components:
        if time_exceeded[0] or (time.monotonic() - start_time > time_limit): break

        comp_n       = len(comp_indices)
        comp_graph_l = [[] for _ in range(comp_n)]
        comp_degrees = [0] * comp_n
        comp_domains = [domains[idx] for idx in comp_indices]

        local_map = {orig: local for local, orig in enumerate(comp_indices)}
        for orig in comp_indices:
            for neighbor in conflict_graph[orig]:
                comp_graph_l[local_map[orig]].append(local_map[neighbor])
                comp_degrees[local_map[orig]] += 1

        if comp_n > GIANT_COMPONENT_THRESHOLD:
            comp_sols = _solve_via_min_conflicts(comp_n, comp_graph_l, comp_domains, time_limit, start_time)
        else:
            comp_gen = _solve_single_component(
                comp_n, comp_graph_l, comp_degrees, comp_domains,
                time_limit, start_time, time_exceeded
            )
            comp_sols = list(itertools.islice(comp_gen, MAX_CARTESIAN_SOLUTIONS))

        if not comp_sols: return
        component_solutions.append(comp_sols)

    for combined_solution in itertools.product(*component_solutions):
        if time_exceeded[0] or (time.monotonic() - start_time > time_limit): break

        full_assignment = [0] * n
        for comp_indices, local_sol in zip(components, combined_solution):
            for orig_idx, assigned_day in zip(comp_indices, local_sol):
                full_assignment[orig_idx] = assigned_day

        yield full_assignment


def _queue_bridge(worker_args: dict, queue, period_idx: int) -> None:
    try:
        batch = []
        for sol in _solve_period_worker(worker_args):
            batch.append(sol)
            if len(batch) >= BATCH_SIZE:
                queue.put((period_idx, batch))
                batch = []
        if batch:
            queue.put((period_idx, batch))
    finally:
        queue.put((period_idx, None))  


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
    _graph_cache: dict = {}

    def generate(self, courses: list, exam_periods: list):
        exam_courses = [c for c in courses if c.is_exam_required()]

        if not exam_courses:
            return

        if not exam_periods:
            return

        self._start_time    = time.monotonic()
        self._time_exceeded = False

        n_all = len(exam_courses)
        conflict_matrix = [[False] * n_all for _ in range(n_all)]
        for i in range(n_all):
            for j in range(i + 1, n_all):
                if _courses_conflict(exam_courses[i], exam_courses[j]):
                    conflict_matrix[i][j] = True
                    conflict_matrix[j][i] = True

        course_index = {c.course_id: idx for idx, c in enumerate(exam_courses)}

        period_args = []
        period_meta = []

        for period in exam_periods:
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
                conflict_graph, degrees = BacktrackScheduler._graph_cache[cache_key]
            else:
                conflict_graph = [[] for _ in range(n)]
                degrees        = [0] * n
                for i in range(n):
                    gi = course_index[period_courses[i].course_id]
                    for j in range(i + 1, n):
                        gj = course_index[period_courses[j].course_id]
                        if conflict_matrix[gi][gj]:
                            conflict_graph[i].append(j)
                            conflict_graph[j].append(i)
                            degrees[i] += 1
                            degrees[j] += 1
                BacktrackScheduler._graph_cache[cache_key] = (conflict_graph, degrees)

            domains = [0] * n
            for i, c in enumerate(period_courses):
                c_sems = {prog.semester for prog in c.programs}
                mask   = 0
                for d_idx, date_obj in enumerate(available_dates):
                    if date_obj.semester in c_sems:
                        mask |= (1 << d_idx)
                domains[i] = mask

            period_args.append({
                "n":              n,
                "conflict_graph": conflict_graph,
                "domains":        domains,
                "time_limit":     self.TIME_LIMIT_SECONDS,
            })
            period_meta.append((period, period_courses, available_dates))

        if not period_args: return

        def _emit(assignment_indices, period, period_courses, available_dates):
            schedule = Schedule()
            for idx, d_idx in enumerate(assignment_indices):
                schedule.add_assignment(period_courses[idx], period.moed, available_dates[d_idx])
            return schedule

        try:
            shared_queue = multiprocessing.Queue(maxsize=200)

            with ProcessPoolExecutor() as executor:
                futures = [
                    executor.submit(_queue_bridge, args, shared_queue, idx)
                    for idx, args in enumerate(period_args)
                ]

                active_workers = len(period_args)

                while active_workers > 0:
                    elapsed = time.monotonic() - self._start_time
                    if elapsed > self.TIME_LIMIT_SECONDS:
                        self._time_exceeded = True
                        break

                    try:
                        period_idx, batch = shared_queue.get(timeout=0.5)
                    except collections.deque.Empty if hasattr(collections, 'deque') else Exception:
                        continue
                    except Exception:
                        continue

                    if batch is None:
                        active_workers -= 1
                        continue

                    period, period_courses, available_dates = period_meta[period_idx]

                    for item in batch:
                        if time.monotonic() - self._start_time > self.TIME_LIMIT_SECONDS:
                            self._time_exceeded = True
                            break
                        yield _emit(item, period, period_courses, available_dates)

                    if self._time_exceeded:
                        break

                if self._time_exceeded:
                    executor.shutdown(wait=False, cancel_futures=True)

        except Exception as e:
            print(f"[Scheduler] Parallel error: {e}. Falling back to sequential.")
            for args, (period, period_courses, available_dates) in zip(period_args, period_meta):
                if self._time_exceeded: break
                for assignment_indices in _solve_period_worker(args):
                    if time.monotonic() - self._start_time > self.TIME_LIMIT_SECONDS:
                        self._time_exceeded = True
                        break
                    yield _emit(assignment_indices, period, period_courses, available_dates)