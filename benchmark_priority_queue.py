"""
Benchmark: the heap priority queue.

MSCS-532 Assignment 4, Priority Queue analysis.

Three experiments, each writing a CSV into results/:

  P1. pq_op_costs.csv    levels moved and time per operation (insert,
                         extract_max, increase_key, decrease_key) on a queue of
                         n tasks, against log2 n
  P2. pq_structures.csv  the heap against two simpler queues (an unsorted list
                         scanned for its maximum, and a sorted list kept in
                         order with bisect) on a steady-state workload
  P3. pq_build.csv       building a queue by n inserts vs one bulk build

Run everything:       python benchmark_priority_queue.py
Run one experiment:   python benchmark_priority_queue.py --only p1
Quick smoke test:     python benchmark_priority_queue.py --quick
"""

import argparse
import bisect
import csv
import gc
import math
import os
import random
import statistics
import sys
import time

from priority_queue import PriorityQueue, Task, outranks

RESULTS_DIR = "results"
SEED = 532
TRIALS = 5  # each timed measurement is the median of this many fresh runs


def write_csv(name, header, rows):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, name)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  wrote {path}", file=sys.stderr)


def sort_key(task):
    """Same ordering as priority_queue.outranks, as a key for the baseline queues."""
    return (task.priority, -task.deadline, -task.arrival_time, -task.task_id)


def random_tasks(n, rng, first_id=1):
    return [Task(first_id + i, rng.randint(0, 10**9), rng.randint(0, 1000), rng.randint(1000, 5000))
            for i in range(n)]


def copy_tasks(tasks):
    """Fresh Task objects, because increase_key / decrease_key change priorities in place."""
    return [Task(t.task_id, t.priority, t.arrival_time, t.deadline) for t in tasks]


# ---------------------------------------------------------------------------
# Baseline queues for P2
# ---------------------------------------------------------------------------

class UnsortedListQueue:
    """insert O(1); extract_max scans the whole list, O(n)."""

    def __init__(self):
        self.items = []

    def insert(self, task):
        self.items.append(task)

    def extract_max(self):
        items = self.items
        best = max(range(len(items)), key=lambda i: sort_key(items[i]))
        items[best], items[-1] = items[-1], items[best]
        return items.pop()


class SortedListQueue:
    """Kept in increasing order with bisect. insert O(n) (shifting), extract_max O(1)."""

    def __init__(self):
        self.items = []

    def insert(self, task):
        bisect.insort(self.items, task, key=sort_key)

    def extract_max(self):
        return self.items.pop()


class PlainHeapQueue:
    """A binary max-heap with NO position index.

    The same sifting as PriorityQueue (same ordering rule, same "hole" technique),
    minus the dictionary updates that let PriorityQueue find a task in O(1) for
    increase_key / decrease_key. It cannot change a priority in O(log n), but
    it shows how much of PriorityQueue's time is that extra bookkeeping.
    """

    def __init__(self):
        self.h = []

    def insert(self, task):
        h = self.h
        h.append(task)
        i = len(h) - 1
        while i > 0:
            parent = (i - 1) // 2
            if not outranks(task, h[parent]):
                break
            h[i] = h[parent]
            i = parent
        h[i] = task

    def extract_max(self):
        h = self.h
        top = h[0]
        last = h.pop()
        if h:
            n = len(h)
            i = 0
            while True:
                child = 2 * i + 1
                if child >= n:
                    break
                if child + 1 < n and outranks(h[child + 1], h[child]):
                    child += 1
                if not outranks(h[child], last):
                    break
                h[i] = h[child]
                i = child
            h[i] = last
        return top


# ---------------------------------------------------------------------------
# P1: cost of each operation on a queue of n tasks
# ---------------------------------------------------------------------------

def timed_trials(run_once):
    """run_once() builds a FRESH queue, does the operations and returns (seconds, moves).

    Returns the median seconds over TRIALS fresh runs, and the moves from the
    first run (the inputs are identical every time, so the moves are too).
    """
    results = [run_once() for _ in range(TRIALS)]
    return statistics.median(r[0] for r in results), results[0][1]


def experiment_p1(sizes, max_ops):
    """Every operation type is measured on its own freshly built queue of n tasks.

    ops is at most n/4 (and at most max_ops), so the queue size stays between
    0.75 n and 1.25 n and log2 n is a fair yardstick. "moves" counts levels
    climbed or descended. Times are the median of TRIALS fresh runs.
    """
    rows = []
    for n in sizes:
        ops = min(max_ops, n // 4)
        rng = random.Random(SEED + n)
        base = random_tasks(n, rng)
        new = random_tasks(ops, rng, first_id=n + 1)
        pick_idx = rng.sample(range(n), ops)  # the same tasks are picked in every trial
        bumps = [rng.randint(1, 10**9) for _ in range(ops)]
        drops = [rng.randint(1, 10**9) for _ in range(ops)]

        def fresh():
            tasks = copy_tasks(base)
            return PriorityQueue(tasks), tasks

        def insert_random():
            pq, _ = fresh()
            batch = copy_tasks(new)
            pq.moves = 0
            t0 = time.perf_counter()
            for t in batch:
                pq.insert(t)
            return time.perf_counter() - t0, pq.moves

        def insert_worst():  # every new task outranks all others and climbs to the root
            pq, _ = fresh()
            top = max(t.priority for t in pq.tasks()) + 1
            pq.moves = 0
            t0 = time.perf_counter()
            for i in range(ops):
                pq.insert(Task(n + 1 + i, top + i))
            return time.perf_counter() - t0, pq.moves

        def extract():
            pq, _ = fresh()
            pq.moves = 0
            t0 = time.perf_counter()
            for _ in range(ops):
                pq.extract_max()
            return time.perf_counter() - t0, pq.moves

        def increase_random():
            pq, tasks = fresh()
            picks = [tasks[i] for i in pick_idx]
            pq.moves = 0
            t0 = time.perf_counter()
            for t, b in zip(picks, bumps):
                pq.increase_key(t, t.priority + b)
            return time.perf_counter() - t0, pq.moves

        def increase_worst():  # bottom-level tasks are raised above everything
            pq, _ = fresh()
            leaves = pq.tasks()[-ops:]
            top = max(t.priority for t in pq.tasks()) + 1
            pq.moves = 0
            t0 = time.perf_counter()
            for i, t in enumerate(leaves):
                pq.increase_key(t, top + i)
            return time.perf_counter() - t0, pq.moves

        def decrease_random():
            pq, tasks = fresh()
            picks = [tasks[i] for i in pick_idx]
            pq.moves = 0
            t0 = time.perf_counter()
            for t, d in zip(picks, drops):
                pq.decrease_key(t, t.priority - d)
            return time.perf_counter() - t0, pq.moves

        def decrease_worst():  # the top task is dropped below everything and sinks to the bottom
            pq, _ = fresh()
            pq.moves = 0
            t0 = time.perf_counter()
            for i in range(ops):
                pq.decrease_key(pq.peek(), -10**12 - i)
            return time.perf_counter() - t0, pq.moves

        ins_s, ins_m = timed_trials(insert_random)
        _, worst_ins_m = timed_trials(insert_worst)
        ext_s, ext_m = timed_trials(extract)
        inc_s, inc_m = timed_trials(increase_random)
        _, worst_inc_m = timed_trials(increase_worst)
        dec_s, dec_m = timed_trials(decrease_random)
        _, worst_dec_m = timed_trials(decrease_worst)
        ins_us, ext_us, inc_us, dec_us = (s / ops * 1e6 for s in (ins_s, ext_s, inc_s, dec_s))
        ins_moves, worst_ins_moves, ext_moves = ins_m / ops, worst_ins_m / ops, ext_m / ops
        inc_moves, worst_inc_moves, dec_moves, worst_dec_moves = inc_m / ops, worst_inc_m / ops, dec_m / ops, worst_dec_m / ops

        rows.append([n, f"{math.log2(n):.2f}", ops,
                     f"{ins_moves:.3f}", f"{worst_ins_moves:.3f}", f"{ext_moves:.3f}",
                     f"{inc_moves:.3f}", f"{worst_inc_moves:.3f}", f"{dec_moves:.3f}", f"{worst_dec_moves:.3f}",
                     f"{ins_us:.3f}", f"{ext_us:.3f}", f"{inc_us:.3f}", f"{dec_us:.3f}"])
        print(f"  P1 n={n:<7d} log2n={math.log2(n):5.2f} ops={ops:<5d} moves: insert={ins_moves:.2f} (worst {worst_ins_moves:.2f})  "
              f"extract={ext_moves:.2f}  increase={inc_moves:.2f} (worst {worst_inc_moves:.2f})  "
              f"decrease={dec_moves:.2f} (worst {worst_dec_moves:.2f})   us/op (median of {TRIALS}): insert={ins_us:.2f} "
              f"extract={ext_us:.2f} increase={inc_us:.2f} decrease={dec_us:.2f}", file=sys.stderr, flush=True)
    write_csv("pq_op_costs.csv",
              ["n", "log2_n", "ops_measured", "insert_moves_random", "insert_moves_worst", "extract_moves",
               "increase_key_moves_random", "increase_key_moves_worst", "decrease_key_moves_random",
               "decrease_key_moves_worst", "insert_us", "extract_us", "increase_key_us", "decrease_key_us"], rows)


# ---------------------------------------------------------------------------
# P2: heap vs simpler queues
# ---------------------------------------------------------------------------

def steady_state_run(queue, preload, new_tasks):
    """Fill the queue, then do len(new_tasks) rounds of (insert one, extract one)."""
    for t in preload:
        queue.insert(t)
    gc.collect()
    start = time.perf_counter()
    for t in new_tasks:
        queue.insert(t)
        queue.extract_max()
    return time.perf_counter() - start


def experiment_p2(sizes, rounds, unsorted_limit, trials):
    rows = []
    factories = {
        "heap": PriorityQueue,
        "heap_no_index": PlainHeapQueue,
        "sorted_list": SortedListQueue,
        "unsorted_list": UnsortedListQueue,
    }
    for n in sizes:
        rng = random.Random(SEED + n)
        preload = random_tasks(n, rng)
        new_tasks = random_tasks(rounds, rng, first_id=n + 1)
        for name, factory in factories.items():
            if name == "unsorted_list" and n > unsorted_limit:
                rows.append([name, n, rounds, "", ""])
                continue
            times = []
            for _ in range(trials):
                times.append(steady_state_run(factory(), preload, new_tasks))
            per_round_us = statistics.median(times) / rounds * 1e6
            rows.append([name, n, rounds, f"{per_round_us:.3f}", len(times)])
            print(f"  P2 {name:13s} n={n:<7d} {per_round_us:10.2f} us per (insert + extract)", file=sys.stderr, flush=True)
    write_csv("pq_structures.csv", ["queue", "n", "rounds", "us_per_insert_plus_extract", "trials"], rows)


# ---------------------------------------------------------------------------
# P3: n inserts vs bulk build
# ---------------------------------------------------------------------------

def experiment_p3(sizes, trials):
    rows = []
    for n in sizes:
        rng = random.Random(SEED + n)
        tasks = random_tasks(n, rng)
        insert_times, bulk_times = [], []
        insert_moves = bulk_moves = 0
        for _ in range(trials):
            gc.collect()
            pq = PriorityQueue()
            t0 = time.perf_counter()
            for t in tasks:
                pq.insert(t)
            insert_times.append(time.perf_counter() - t0)
            insert_moves = pq.moves
            gc.collect()
            t0 = time.perf_counter()
            bulk = PriorityQueue(tasks)
            bulk_times.append(time.perf_counter() - t0)
            bulk_moves = bulk.moves
        rows.append([n, f"{statistics.median(insert_times) * 1e3:.3f}", f"{statistics.median(bulk_times) * 1e3:.3f}",
                     f"{insert_moves / n:.3f}", f"{bulk_moves / n:.3f}"])
        print(f"  P3 n={n:<7d} {n} inserts: {rows[-1][1]} ms ({rows[-1][3]} moves/task)   "
              f"bulk build: {rows[-1][2]} ms ({rows[-1][4]} moves/task)", file=sys.stderr, flush=True)
    write_csv("pq_build.csv", ["n", "n_inserts_ms", "bulk_build_ms", "insert_moves_per_task", "bulk_moves_per_task"], rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="tiny sizes, finishes in a few seconds")
    parser.add_argument("--only", choices=["p1", "p2", "p3"], help="run just one experiment")
    args = parser.parse_args()
    global RESULTS_DIR
    if args.quick:
        RESULTS_DIR = "results_quick"  # keep smoke-test output away from the real results
        p1 = dict(sizes=[500, 2000], max_ops=200)
        p2 = dict(sizes=[500, 2000], rounds=200, unsorted_limit=2000, trials=1)
        p3 = dict(sizes=[2000], trials=1)
    else:
        p1 = dict(sizes=[1_000, 4_000, 16_000, 64_000, 256_000], max_ops=1_000)
        p2 = dict(sizes=[1_000, 4_000, 16_000, 64_000, 256_000], rounds=2_000, unsorted_limit=16_000, trials=3)
        p3 = dict(sizes=[10_000, 100_000], trials=5)
    if args.only in (None, "p1"):
        print("P1: cost per operation", file=sys.stderr)
        experiment_p1(**p1)
    if args.only in (None, "p2"):
        print("P2: heap vs simpler queues", file=sys.stderr)
        experiment_p2(**p2)
    if args.only in (None, "p3"):
        print("P3: build by inserts vs bulk build", file=sys.stderr)
        experiment_p3(**p3)
    print("done", file=sys.stderr)


if __name__ == "__main__":
    main()
