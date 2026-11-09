"""
Draw the charts used in REPORT.md from the CSV files in results/.

Needs matplotlib (pip install matplotlib). The data structures themselves do
not need it. Run the benchmarks first:

    python benchmark_sorts.py
    python benchmark_priority_queue.py
    python scheduler_experiments.py
    python make_plots.py
"""

import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS, FIGURES = "results", "figures"
os.makedirs(FIGURES, exist_ok=True)


def read(name):
    with open(os.path.join(RESULTS, name), newline="") as f:
        return list(csv.DictReader(f))


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(FIGURES, name), dpi=150)
    plt.close(fig)
    print("wrote", os.path.join(FIGURES, name))


def fig_sort_times():
    rows = read("sorts_times.csv")
    dists = [("random", "Random"), ("sorted", "Already sorted"), ("reverse", "Reverse sorted"),
             ("repeated", "Repeated (10 distinct values)")]
    colors = {"heapsort": "tab:purple", "quicksort": "tab:blue", "merge_sort": "tab:green"}
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), sharex=True)
    for ax, (dist, title) in zip(axes.flat, dists):
        for algo, color in colors.items():
            pts = sorted((int(r["n"]), float(r["median_seconds"])) for r in rows
                         if r["distribution"] == dist and r["algorithm"] == algo)
            ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", markersize=4, color=color,
                    label=algo.replace("_", " "))
        ax.set_xscale("log", base=2)
        ax.set_yscale("log")
        ax.set_title(title)
        ax.grid(True, which="both", alpha=0.3)
    for ax in axes[1]:
        ax.set_xlabel("array size n")
    for ax in axes[:, 0]:
        ax.set_ylabel("seconds (median)")
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("Heapsort vs Quicksort vs Merge Sort (log-log)")
    save(fig, "fig1_sort_times.png")


def fig_sort_comparisons():
    rows = read("sorts_comparisons.csv")
    dists = ["random", "sorted", "reverse", "repeated"]
    algos = [("heapsort", "tab:purple"), ("quicksort", "tab:blue"), ("merge_sort", "tab:green")]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    width = 0.26
    for k, (algo, color) in enumerate(algos):
        vals = [float(next(r["comparisons_over_n_log2_n"] for r in rows
                           if r["distribution"] == d and r["algorithm"] == algo)) for d in dists]
        ax.bar([i + (k - 1) * width for i in range(len(dists))], vals, width, color=color, label=algo.replace("_", " "))
    ax.set_xticks(range(len(dists)))
    ax.set_xticklabels(dists)
    n = rows[0]["n"]
    ax.set_ylabel("comparisons ÷ (n log₂ n)")
    ax.set_title(f"Key comparisons at n = {int(n):,}")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()
    save(fig, "fig2_sort_comparisons.png")


def fig_pq_op_costs():
    rows = read("pq_op_costs.csv")
    ns = [int(r["n"]) for r in rows]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.plot(ns, [float(r["log2_n"]) for r in rows], "k-", linewidth=2, label="log₂ n (the O(log n) ceiling)")
    series = [
        ("insert_moves_worst", "insert, worst case", "tab:red", "o", "-"),
        ("extract_moves", "extract_max", "tab:purple", "s", "-"),
        ("increase_key_moves_worst", "increase_key, worst case", "tab:orange", "^", "-"),
        ("decrease_key_moves_worst", "decrease_key, worst case", "tab:brown", "v", "-"),
        ("increase_key_moves_random", "increase_key, random", "tab:orange", "^", "--"),
        ("decrease_key_moves_random", "decrease_key, random", "tab:brown", "v", "--"),
        ("insert_moves_random", "insert, random priorities", "tab:green", "o", "--"),
    ]
    for col, label, color, marker, ls in series:
        ax.plot(ns, [float(r[col]) for r in rows], marker=marker, linestyle=ls, color=color, markersize=5, label=label)
    ax.set_xscale("log", base=2)
    ax.set_xlabel("tasks in the queue n")
    ax.set_ylabel("levels moved per operation (average)")
    ax.set_title("Heap operations never move more than log₂ n levels")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    save(fig, "fig3_pq_op_costs.png")


def fig_pq_structures():
    rows = read("pq_structures.csv")
    fig, ax = plt.subplots(figsize=(7, 4.4))
    for name, label, color in (("heap", "my heap (with position index)", "tab:purple"), ("heap_no_index", "heap without index", "tab:cyan"), ("sorted_list", "sorted list (bisect)", "tab:blue"),
                               ("unsorted_list", "unsorted list (scan for max)", "tab:red")):
        pts = sorted((int(r["n"]), float(r["us_per_insert_plus_extract"])) for r in rows
                     if r["queue"] == name and r["us_per_insert_plus_extract"])
        ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", color=color, label=label)
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlabel("tasks waiting in the queue n")
    ax.set_ylabel("microseconds per (insert + extract_max)")
    ax.set_title("Three ways to build a priority queue (steady state)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    save(fig, "fig4_pq_structures.png")


def fig_scheduler_policies():
    rows = read("scheduler_policies.csv")
    loads = ["moderate", "heavy", "overloaded"]
    policies = ["priority", "priority + aging", "edf (earliest deadline)", "fcfs"]
    colors = ["tab:purple", "tab:orange", "tab:blue", "tab:gray"]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    for ax, load in zip(axes, loads):
        width = 0.2
        for k, (policy, color) in enumerate(zip(policies, colors)):
            r = next(r for r in rows if r["load"] == load and r["policy"] == policy)
            vals = [float(r["mean_wait_priority5"]), float(r["mean_wait_priority1"]), float(r["largest_wait_seen_priority1"])]
            ax.bar([i + (k - 1.5) * width for i in range(3)], vals, width, color=color, label=policy)
        ax.set_xticks(range(3))
        ax.set_xticklabels(["priority-5 tasks\nmean wait", "priority-1 tasks\nmean wait", "priority-1 tasks\nlargest wait seen"],
                           fontsize=8)
        ax.set_yscale("log")
        ax.set_title(f"{load} load")
        ax.grid(True, axis="y", alpha=0.3)
    axes[0].set_ylabel("time units waiting (log scale)")
    axes[0].legend(fontsize=7)
    save(fig, "fig5_scheduler_policies.png")


def fig_scheduler_scaling():
    rows = read("scheduler_scaling.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for load, color in (("heavy", "tab:blue"), ("overloaded", "tab:red")):
        pts = sorted((int(r["tasks"]), float(r["us_per_task"]), float(r["heap_moves_per_task"]))
                     for r in rows if r["load"] == load)
        axes[0].plot([p[0] for p in pts], [p[1] for p in pts], marker="o", color=color, label=load)
        axes[1].plot([p[0] for p in pts], [p[2] for p in pts], marker="o", color=color, label=load)
    axes[0].set_ylabel("microseconds of simulation per task")
    axes[1].set_ylabel("heap levels moved per task")
    for ax in axes:
        ax.set_xscale("log", base=2)
        ax.set_xlabel("tasks simulated")
        ax.set_ylim(bottom=0)
        ax.grid(True, alpha=0.3)
        ax.legend()
    fig.suptitle("Cost of the scheduler simulation")
    save(fig, "fig6_scheduler_scaling.png")


if __name__ == "__main__":
    fig_sort_times()
    fig_sort_comparisons()
    fig_pq_op_costs()
    fig_pq_structures()
    fig_scheduler_policies()
    fig_scheduler_scaling()
