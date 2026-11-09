# MSCS532_Assignment4

Heapsort, a binary-heap priority queue, and a task scheduler simulation, written in Python, with the analysis and experiments for Assignment 4 of MSCS-532 (Algorithms and Data Structures): *Heap Data Structures: Implementation, Analysis, and Applications*.

**The written report is [`REPORT.md`](REPORT.md).** It covers the design choices, the time and space analysis, the comparison with Quicksort and Merge Sort, and the analysis of the scheduling results.

## What is in here

| File | What it is |
|---|---|
| `heapsort.py` | `max_heapify`, `build_max_heap` and `heapsort` (in place, no recursion). |
| `priority_queue.py` | `Task` and `PriorityQueue`, a binary max-heap stored in a list: `insert`, `extract_max`, `increase_key`, `decrease_key`, `change_priority`, `peek`, `is_empty`, and a bottom-up build from a list of tasks. |
| `scheduler.py` | Event-driven scheduler simulation. Policies: priority, earliest deadline first, first come first served. Preemptive or not, with optional aging. Also a workload generator and the summary metrics. |
| `other_sorts.py` | Randomized Quicksort and Merge Sort, used only for the Heapsort comparison. |
| `counting.py` | A tiny helper that counts comparisons. |
| `test_heapsort.py`, `test_other_sorts.py`, `test_priority_queue.py`, `test_scheduler.py`, `test_counting.py` | 86 unit tests. |
| `mutation_check.py` | Breaks the code on purpose in 33 ways and checks that the tests fail (output in `results/mutation_check.txt`). |
| `benchmark_sorts.py` | Heapsort vs Quicksort vs Merge Sort (times, comparison counts, build vs extraction phase). |
| `benchmark_priority_queue.py` | Cost of each heap operation, and the heap against a sorted list and an unsorted list. |
| `scheduler_experiments.py` | A worked example, four scheduling policies at three loads, and how simulation cost scales. |
| `make_plots.py` | Draws the charts in `figures/` from the CSV files in `results/`. |
| `results/` | The raw numbers behind every table in the report (CSV and text), plus `environment.txt`. |
| `figures/` | The charts used in the report. |

## How to run it

Scheduler times must be integers or `fractions.Fraction` (floats are rejected, because they can stop the simulation from advancing).

The code uses only the Python standard library (Python 3.10 or newer, because the benchmark uses the `key=` argument of `bisect.insort`; written and tested on 3.13). Nothing to install.

Try Heapsort on a few sample arrays:

```
python heapsort.py
```

See the scheduler on a small hand-checkable example (prints a text chart of who holds the CPU when):

```
python scheduler_experiments.py --only e1
```

Run the tests (a few seconds):

```
python -m unittest -v
```

Rerun the experiments (a few minutes each; numbers will differ a little on another machine):

```
python benchmark_sorts.py
python benchmark_priority_queue.py
python scheduler_experiments.py
```

Add `--quick` to any of them for a small run that finishes in seconds (it writes to `results_quick/`, so the real results are not touched), or `--only p1` / `--only e2` and similar to run one experiment. The charts need matplotlib (`pip install matplotlib`):

```
python make_plots.py
```

### Using the code

```python
from heapsort import heapsort
from priority_queue import PriorityQueue, Task
from scheduler import simulate, summarize, generate_workload

heapsort([5, 2, 9, 1])                     # [1, 2, 5, 9]  (sorts in place, returns the list)

pq = PriorityQueue()
a = Task(1, priority=3, arrival_time=0, deadline=20, burst_time=4)
b = Task(2, priority=7, arrival_time=1, deadline=9, burst_time=2)
pq.insert(a)
pq.insert(b)
pq.peek().task_id                          # 2, the highest priority
pq.increase_key(a, 10)                     # task 1 now outranks task 2
pq.extract_max().task_id                   # 1
pq.is_empty()                              # False

tasks = generate_workload(200, seed=1)
result = simulate(tasks, policy="priority", preemptive=True, aging_interval=20)
summarize(tasks, result)["mean_waiting"]
```

## Summary of the findings

- **Heapsort is O(n log n) for every input and sorts in place.** The heap build took 1.88 comparisons per element (bound: 2n). The extraction phase took 1.5 to 1.7 times n·log₂ n (bound: 2). If all keys are equal it drops to about 3n comparisons.
- **In pure Python it was the slowest of the three.** At n = 160,000 on random input: 0.737 s for Heapsort, 0.632 s for Quicksort and 0.543 s for Merge Sort. It makes about twice as many comparisons as Merge Sort. Its time hardly changes with input order, which is the guarantee Quicksort lacks.
- **Every priority-queue operation moves a task at most log₂ n levels.** The forced worst cases hit exactly the tree height (17 levels at n = 256,000). Random inserts moved only about 1.2 to 1.3 levels on average.
- **The heap beats simpler queues only when the queue is long.** Below about 16,000 waiting tasks a sorted list was faster than my heap in pure Python (a plain heap without the position index was already faster at 16,000). At 256,000 waiting tasks my heap was about 5 times faster.
- **Priority scheduling starves the bottom class.** Priority-5 tasks waited about 0.5 time units on average, priority-1 tasks waited 17 to 2,264 depending on load. Aging cut the longest wait by 60 to 77% but did not lower the overall mean wait (it moves waiting onto the other classes), and under overload it made the simulation up to 10 times slower. At heavy load, earliest-deadline-first spread the lateness evenly and missed more deadlines (49%) than priority scheduling (31%); that held when I made deadline slack independent of burst time (54% against 32%).

## Environment used for the timings

AMD Ryzen 7 3700X, Windows 11, Python 3.13.9. See `results/environment.txt`.

## References

Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C. (2022). *Introduction to algorithms* (4th ed.). MIT Press.

Floyd, R. W. (1964). Algorithm 245: Treesort. *Communications of the ACM, 7*(12), 701. https://doi.org/10.1145/355588.365103

Liu, C. L., & Layland, J. W. (1973). Scheduling algorithms for multiprogramming in a hard-real-time environment. *Journal of the ACM, 20*(1), 46–61. https://doi.org/10.1145/321738.321743

Williams, J. W. J. (1964). Algorithm 232: Heapsort. *Communications of the ACM, 7*(6), 347–348. https://doi.org/10.1145/512274.3734138
