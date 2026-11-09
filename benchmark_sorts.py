"""
Benchmark: Heapsort vs Quicksort vs Merge Sort.

MSCS-532 Assignment 4, Heapsort comparison.

Three experiments, each writing a CSV into results/:

  S1. sorts_times.csv        wall-clock time, n = 5,000 .. 160,000, four input
                             kinds (random, sorted, reverse-sorted, repeated)
  S2. sorts_comparisons.csv  counted key comparisons at n = 10,000 (the four
                             input kinds plus an all-equal array)
  S3. heapsort_phases.csv    how many comparisons the build phase and the
                             extraction phase each use

Run everything:       python benchmark_sorts.py
Quick smoke test:     python benchmark_sorts.py --quick
"""

import argparse
import csv
import gc
import math
import os
import platform
import random
import statistics
import sys
import time

from counting import CountingKey, get_count, reset_count
from heapsort import build_max_heap, heapsort
from other_sorts import merge_sort, quicksort

RESULTS_DIR = "results"
SEED = 532
DISTRIBUTIONS = ["random", "sorted", "reverse", "repeated"]
COMPARISON_DISTRIBUTIONS = DISTRIBUTIONS + ["all_equal"]  # S2 also counts the all-equal extreme
ALGORITHMS = {
    "heapsort": heapsort,
    "quicksort": lambda a: quicksort(a, rng=random.Random(SEED)),
    "merge_sort": merge_sort,
}


def make_input(kind, n, rng):
    if kind == "random":
        return rng.sample(range(10 * n), n)
    if kind == "sorted":
        return list(range(n))
    if kind == "reverse":
        return list(range(n, 0, -1))
    if kind == "repeated":
        return [rng.randrange(10) for _ in range(n)]
    if kind == "all_equal":
        return [7] * n
    raise ValueError(kind)


def write_csv(name, header, rows):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, name)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  wrote {path}", file=sys.stderr)


def time_cell(sorter, data, max_trials, max_cell_seconds):
    expected = sorted(data)
    times, spent = [], 0.0
    while len(times) < max_trials and (not times or spent < max_cell_seconds):
        arr = list(data)
        gc.collect()
        start = time.perf_counter()
        sorter(arr)
        elapsed = time.perf_counter() - start
        if arr != expected:
            raise AssertionError("sort produced a wrong answer")
        times.append(elapsed)
        spent += elapsed
    return statistics.median(times), len(times)


def experiment_s1(sizes, max_trials, max_cell_seconds):
    rows = []
    for dist in DISTRIBUTIONS:
        for n in sizes:
            data = make_input(dist, n, random.Random(SEED + n))
            for name, sorter in ALGORITHMS.items():
                secs, runs = time_cell(sorter, data, max_trials, max_cell_seconds)
                per = secs / (n * math.log2(n)) * 1e6
                rows.append([dist, name, n, f"{secs:.6f}", f"{per:.5f}", runs])
                print(f"  S1 {dist:9s} {name:11s} n={n:<7d} {secs:8.4f}s  {per:.4f} us/(n log2 n)",
                      file=sys.stderr, flush=True)
    write_csv("sorts_times.csv", ["distribution", "algorithm", "n", "median_seconds", "us_per_n_log2_n", "runs"], rows)


def count_comparisons(sorter, values):
    reset_count()
    arr = [CountingKey(v) for v in values]
    sorter(arr)
    assert [k.value for k in arr] == sorted(values)
    return get_count()


def experiment_s2(n):
    rows = []
    for dist in COMPARISON_DISTRIBUTIONS:
        values = make_input(dist, n, random.Random(SEED + n))
        for name, sorter in ALGORITHMS.items():
            count = count_comparisons(sorter, values)
            rows.append([dist, name, n, count, f"{count / (n * math.log2(n)):.4f}"])
            print(f"  S2 {dist:9s} {name:11s} n={n} comparisons={count}  ({count / (n * math.log2(n)):.3f} x n log2 n)",
                  file=sys.stderr, flush=True)
    write_csv("sorts_comparisons.csv", ["distribution", "algorithm", "n", "comparisons", "comparisons_over_n_log2_n"], rows)


def experiment_s3(sizes):
    rows = []
    for n in sizes:
        values = make_input("random", n, random.Random(SEED + n))
        reset_count()
        arr = [CountingKey(v) for v in values]
        build_max_heap(arr)
        build = get_count()
        reset_count()
        arr = [CountingKey(v) for v in values]
        heapsort(arr)
        total = get_count()
        extract = total - build
        rows.append([n, build, f"{build / n:.3f}", extract, f"{extract / (n * math.log2(n)):.3f}", total,
                     f"{total / (n * math.log2(n)):.3f}"])
        print(f"  S3 n={n:<7d} build={build} ({build / n:.2f} n)  extraction={extract} "
              f"({extract / (n * math.log2(n)):.2f} n log2 n)  total={total}", file=sys.stderr, flush=True)
    write_csv("heapsort_phases.csv",
              ["n", "build_comparisons", "build_over_n", "extraction_comparisons",
               "extraction_over_n_log2_n", "total_comparisons", "total_over_n_log2_n"], rows)


def write_environment():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "environment.txt"), "w") as f:
        f.write(f"python {sys.version}\n")
        f.write(f"platform {platform.platform()}\n")
        f.write(f"machine {platform.machine()}  processor {platform.processor()}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="tiny sizes, finishes in a few seconds")
    parser.add_argument("--only", choices=["s1", "s2", "s3"], help="run just one experiment")
    args = parser.parse_args()
    global RESULTS_DIR
    if args.quick:
        RESULTS_DIR = "results_quick"  # keep smoke-test output away from the real results
        sizes, trials, cell, cmp_n, phase_sizes = [500, 1000], 2, 2.0, 1000, [500, 2000]
    else:
        sizes, trials, cell = [5_000, 10_000, 20_000, 40_000, 80_000, 160_000], 5, 20.0
        cmp_n, phase_sizes = 10_000, [1_000, 10_000, 100_000]
    write_environment()
    if args.only in (None, "s1"):
        print("S1: running times", file=sys.stderr)
        experiment_s1(sizes, trials, cell)
    if args.only in (None, "s2"):
        print("S2: comparison counts", file=sys.stderr)
        experiment_s2(cmp_n)
    if args.only in (None, "s3"):
        print("S3: heapsort build vs extraction", file=sys.stderr)
        experiment_s3(phase_sizes)
    print("done", file=sys.stderr)


if __name__ == "__main__":
    main()
