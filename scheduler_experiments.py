"""
Scheduler experiments.

MSCS-532 Assignment 4, scheduler simulation and analysis of the results.

Experiments, each writing into results/:

  E1. scheduler_example.txt        a small hand-checkable schedule drawn as text
  E2. scheduler_policies.csv       four scheduling policies compared on random
                                   workloads at three load levels (averaged over
                                   5 random seeds each)
  E2b. scheduler_missed_by_priority.csv   who misses their deadlines, by priority
  E2c. scheduler_policies_independent_slack.csv (+ missed_by_priority version)
                                   the same comparison when each task's deadline
                                   slack does not depend on its burst time
  E3. scheduler_scaling.csv        simulation time as the number of tasks grows
  E3b. scheduler_aging_cost.csv    what aging costs in simulation time

Run everything:       python scheduler_experiments.py
Run one experiment:   python scheduler_experiments.py --only e2c
Quick smoke test:     python scheduler_experiments.py --quick
"""

import argparse
import csv
import os
import statistics
import sys
import time

from priority_queue import Task
from scheduler import generate_workload, simulate, summarize, waiting_by_priority

RESULTS_DIR = "results"

# name -> simulate() keyword arguments
CONFIGS = {
    "priority": dict(policy="priority"),
    "priority + aging": dict(policy="priority", aging_interval=20, aging_step=1),
    "edf (earliest deadline)": dict(policy="edf"),
    "fcfs": dict(policy="fcfs"),
}

# name -> (mean_gap, max_burst). Mean burst is (1 + max_burst) / 2, so
# load = mean burst / mean gap.
LOADS = {
    "moderate": (7, 10),  # 5.5 / 7  = about 79%
    "heavy": (6, 10),  # 5.5 / 6  = about 92%
    "overloaded": (5, 10),  # 5.5 / 5 = about 110%
}


def write_csv(name, header, rows):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, name)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  wrote {path}", file=sys.stderr)


def gantt(timeline, names):
    """One line per task, '#' where it holds the CPU, '.' otherwise."""
    end = max(e for _, _, e in timeline)
    lines = ["time    " + "".join(str(t % 10) for t in range(end))]
    for task_id, name in names.items():
        row = ["."] * end
        for tid, s, e in timeline:
            if tid == task_id:
                for t in range(s, e):
                    row[t] = "#"
        lines.append(f"{name:<8}" + "".join(row))
    return "\n".join(lines)


def experiment_e1():
    tasks = [
        Task(1, priority=1, arrival_time=0, deadline=20, burst_time=5),
        Task(2, priority=3, arrival_time=1, deadline=10, burst_time=2),
        Task(3, priority=2, arrival_time=2, deadline=4, burst_time=1),
        Task(4, priority=5, arrival_time=4, deadline=9, burst_time=2),
        Task(5, priority=2, arrival_time=5, deadline=15, burst_time=3),
        Task(6, priority=4, arrival_time=12, deadline=14, burst_time=2),
    ]
    names = {t.task_id: f"T{t.task_id} (p{t.priority})" for t in tasks}
    out = []
    out.append("Tasks: id, priority, arrival, burst, deadline")
    for t in tasks:
        out.append(f"  T{t.task_id}  priority {t.priority}  arrives {t.arrival_time:>2}  needs {t.burst_time}  due {t.deadline}")
    for label, opts in (("Preemptive priority scheduling", dict(preemptive=True)),
                        ("Non-preemptive priority scheduling", dict(preemptive=False)),
                        ("Earliest deadline first (preemptive)", dict(policy="edf"))):
        result = simulate(tasks, **opts)
        s = summarize(tasks, result)
        out.append("")
        out.append(f"{label}")
        out.append(gantt(result.timeline, names))
        out.append("segments: " + ", ".join(f"T{i}[{a}-{b}]" for i, a, b in result.timeline))
        out.append("finish:   " + ", ".join(f"T{t.task_id}={result.finish_time[t.task_id]}" for t in tasks))
        out.append(f"mean waiting {s['mean_waiting']:.2f}, max waiting {s['max_waiting']}, "
                   f"missed deadlines {s['missed_deadlines']}, preemptions {s['preemptions']}")
    text = "\n".join(out) + "\n"
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "scheduler_example.txt"), "w") as f:
        f.write(text)
    print(text, file=sys.stderr)


def experiment_e2(n, seeds, slack_mode="proportional", filename="scheduler_policies.csv"):
    """Four policies at three loads, averaged over the seeds.

    Note on the two "longest wait" numbers. avg_of_workload_max_wait is the
    AVERAGE over the seeds of each workload's own longest wait; largest_wait_seen
    is the single longest wait in any of the workloads.
    """
    rows = []
    for load_name, (gap, max_burst) in LOADS.items():
        for config_name, opts in CONFIGS.items():
            acc = {k: [] for k in ("mean_waiting", "max_waiting", "mean_turnaround", "mean_response",
                                   "missed_pct", "preemptions", "wait5", "wait4", "wait3", "wait2", "wait1",
                                   "low_max_wait", "mean_queue", "max_queue", "tie_preemptions")}
            for seed in seeds:
                tasks = generate_workload(n, seed=seed, mean_gap=gap, max_burst=max_burst, priorities=5,
                                          slack_mode=slack_mode)
                result = simulate(tasks, **opts)
                s = summarize(tasks, result)
                by_prio = waiting_by_priority(tasks, result)
                acc["mean_waiting"].append(s["mean_waiting"])
                acc["max_waiting"].append(s["max_waiting"])
                acc["mean_turnaround"].append(s["mean_turnaround"])
                acc["mean_response"].append(s["mean_response"])
                acc["missed_pct"].append(100.0 * s["missed_deadlines"] / n)
                acc["preemptions"].append(s["preemptions"])
                for p in (5, 4, 3, 2, 1):
                    acc[f"wait{p}"].append(by_prio[p][0])
                acc["low_max_wait"].append(by_prio[1][1])
                acc["mean_queue"].append(s["mean_queue_length"])
                acc["max_queue"].append(s["max_queue_length"])
                acc["tie_preemptions"].append(s["tie_preemptions"])
            mean = lambda k: statistics.mean(acc[k])
            row = [load_name, config_name, n, len(seeds),
                   f"{mean('mean_waiting'):.2f}", f"{mean('max_waiting'):.2f}", f"{mean('mean_turnaround'):.2f}",
                   f"{mean('mean_response'):.2f}", f"{mean('missed_pct'):.2f}", f"{mean('preemptions'):.2f}",
                   f"{mean('wait5'):.2f}", f"{mean('wait1'):.2f}", f"{mean('low_max_wait'):.2f}",
                   f"{mean('wait4'):.2f}", f"{mean('wait3'):.2f}", f"{mean('wait2'):.2f}",
                   f"{max(acc['max_waiting']):.0f}", f"{max(acc['low_max_wait']):.0f}",
                   f"{mean('mean_queue'):.2f}", f"{max(acc['max_queue']):.0f}", f"{mean('tie_preemptions'):.2f}"]
            rows.append(row)
            print(f"  E2 [{slack_mode}] {load_name:10s} {config_name:24s} wait={row[4]:>8} avg-of-max={row[5]:>8} "
                  f"largest={row[16]:>6} resp={row[7]:>8} missed={row[8]:>6}% preempt={row[9]:>7} (ties {row[20]:>6}) "
                  f"wait by class 5..1 = {row[10]}/{row[13]}/{row[14]}/{row[15]}/{row[11]}  "
                  f"queue mean={row[18]} max={row[19]}", file=sys.stderr, flush=True)
    write_csv(filename,
              ["load", "policy", "tasks", "seeds", "mean_waiting", "avg_of_workload_max_wait", "mean_turnaround",
               "mean_response", "missed_deadline_pct", "preemptions", "mean_wait_priority5",
               "mean_wait_priority1", "avg_of_workload_max_wait_priority1", "mean_wait_priority4",
               "mean_wait_priority3", "mean_wait_priority2", "largest_wait_seen", "largest_wait_seen_priority1",
               "mean_queue_length", "largest_queue_seen", "tie_preemptions"], rows)


def experiment_e2b(n, seeds, slack_mode="proportional", filename="scheduler_missed_by_priority.csv"):
    """Which priority classes miss their deadlines? (heavy load)"""
    gap, max_burst = LOADS["heavy"]
    rows = []
    for config_name, opts in CONFIGS.items():
        missed = {p: 0 for p in range(1, 6)}
        total = {p: 0 for p in range(1, 6)}
        for seed in seeds:
            tasks = generate_workload(n, seed=seed, mean_gap=gap, max_burst=max_burst, priorities=5,
                                      slack_mode=slack_mode)
            result = simulate(tasks, **opts)
            for t in tasks:
                total[t.priority] += 1
                if result.finish_time[t.task_id] > t.deadline:
                    missed[t.priority] += 1
        pct = {p: 100.0 * missed[p] / total[p] for p in missed}
        rows.append([config_name] + [f"{pct[p]:.1f}" for p in (5, 4, 3, 2, 1)])
        print(f"  E2b [{slack_mode}] {config_name:24s} missed % by priority 5,4,3,2,1: "
              + "  ".join(f"{pct[p]:5.1f}" for p in (5, 4, 3, 2, 1)), file=sys.stderr, flush=True)
    write_csv(filename,
              ["policy", "missed_pct_priority5", "missed_pct_priority4", "missed_pct_priority3",
               "missed_pct_priority2", "missed_pct_priority1"], rows)


def experiment_e3(sizes, trials):
    """Simulation cost vs number of tasks, at two loads (no aging).

    Under heavy load the queue stays short, so each heap operation is cheap no
    matter how many tasks there are. Under overload the queue keeps growing, so
    the log factor of the heap starts to show.
    """
    rows = []
    for load_name in ("heavy", "overloaded"):
        gap, max_burst = LOADS[load_name]
        for n in sizes:
            tasks = generate_workload(n, seed=532, mean_gap=gap, max_burst=max_burst)
            times = []
            result = None
            for _ in range(trials):
                t0 = time.perf_counter()
                result = simulate(tasks)
                times.append(time.perf_counter() - t0)
            secs = statistics.median(times)
            mean_queue = result.queue_time_area / max(result.finish_time.values())
            rows.append([load_name, n, f"{secs:.4f}", f"{secs / n * 1e6:.3f}", result.events,
                         f"{result.events / n:.3f}", f"{result.queue_moves / n:.3f}", result.preemptions,
                         f"{mean_queue:.2f}", result.max_queue_length])
            print(f"  E3 {load_name:10s} n={n:<7d} {secs:8.3f}s  {secs / n * 1e6:7.2f} us/task  "
                  f"events/task={result.events / n:.2f}  heap moves/task={result.queue_moves / n:.2f}  "
                  f"queue: mean {mean_queue:.1f}, max {result.max_queue_length}", file=sys.stderr, flush=True)
    write_csv("scheduler_scaling.csv",
              ["load", "tasks", "seconds", "us_per_task", "events", "events_per_task",
               "heap_moves_per_task", "preemptions", "mean_queue_length", "max_queue_length"], rows)


def experiment_e3b(sizes, trials):
    """What aging costs. Every tick raises EVERY waiting task with increase_key,
    so one tick costs O(q log q) for q waiting tasks (aging interval 20, step 1)."""
    rows = []
    for load_name in ("heavy", "overloaded"):
        gap, max_burst = LOADS[load_name]
        for n in sizes:
            tasks = generate_workload(n, seed=532, mean_gap=gap, max_burst=max_burst)
            plain_times, aged_times = [], []
            aged = None
            for _ in range(trials):
                t0 = time.perf_counter()
                simulate(tasks)
                plain_times.append(time.perf_counter() - t0)
                t0 = time.perf_counter()
                aged = simulate(tasks, aging_interval=20, aging_step=1)
                aged_times.append(time.perf_counter() - t0)
            plain, with_aging = statistics.median(plain_times), statistics.median(aged_times)
            per_tick = aged.aging_updates / max(1, aged.aging_ticks)
            rows.append([load_name, n, f"{plain:.4f}", f"{with_aging:.4f}", f"{with_aging / plain:.2f}",
                         aged.aging_ticks, aged.aging_updates, f"{per_tick:.1f}", aged.max_queue_length])
            print(f"  E3b {load_name:10s} n={n:<7d} no aging {plain:7.3f}s  aging {with_aging:7.3f}s  "
                  f"({with_aging / plain:5.2f}x)  ticks={aged.aging_ticks} increase_key calls={aged.aging_updates} "
                  f"({per_tick:.1f} per tick)  max queue={aged.max_queue_length}", file=sys.stderr, flush=True)
    write_csv("scheduler_aging_cost.csv",
              ["load", "tasks", "seconds_no_aging", "seconds_with_aging", "slowdown", "aging_ticks",
               "increase_key_calls", "increase_key_calls_per_tick", "max_queue_length_with_aging"], rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="tiny sizes, finishes in a few seconds")
    parser.add_argument("--only", choices=["e1", "e2", "e2b", "e2c", "e3", "e3b"], help="run just one experiment")
    args = parser.parse_args()
    global RESULTS_DIR
    if args.quick:
        RESULTS_DIR = "results_quick"  # keep smoke-test output away from the real results
        e2 = dict(n=100, seeds=[1, 2])
        e3 = dict(sizes=[500, 1000], trials=1)
        e3b = dict(sizes=[500, 1000], trials=1)
    else:
        e2 = dict(n=2000, seeds=[1, 2, 3, 4, 5])
        e3 = dict(sizes=[1_000, 2_000, 4_000, 8_000, 16_000, 32_000, 64_000, 128_000], trials=3)
        e3b = dict(sizes=[2_000, 4_000, 8_000, 16_000], trials=3)
    if args.only in (None, "e1"):
        print("E1: worked example", file=sys.stderr)
        experiment_e1()
    if args.only in (None, "e2"):
        print("E2: policy comparison", file=sys.stderr)
        experiment_e2(**e2)
    if args.only in (None, "e2b"):
        print("E2b: missed deadlines by priority class", file=sys.stderr)
        experiment_e2b(**e2)
    if args.only in (None, "e2c"):
        print("E2c: the same comparison when slack does not depend on burst (robustness check)", file=sys.stderr)
        experiment_e2(**e2, slack_mode="independent", filename="scheduler_policies_independent_slack.csv")
        experiment_e2b(**e2, slack_mode="independent", filename="scheduler_missed_by_priority_independent_slack.csv")
    if args.only in (None, "e3"):
        print("E3: simulation scaling", file=sys.stderr)
        experiment_e3(**e3)
    if args.only in (None, "e3b"):
        print("E3b: cost of aging", file=sys.stderr)
        experiment_e3b(**e3b)
    print("done", file=sys.stderr)


if __name__ == "__main__":
    main()
