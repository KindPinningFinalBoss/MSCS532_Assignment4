"""
Task scheduler simulation built on the heap priority queue.

MSCS-532 Assignment 4, scheduler simulation.

One CPU runs one task at a time. Tasks arrive over time and wait in a
PriorityQueue. Whenever the CPU is free, the highest-ranked waiting task runs.

The simulation is event-driven: instead of stepping one time unit at a time it
jumps straight to the next moment something can change, which is one of

    - the running task finishes
    - a new task arrives
    - an aging tick (only when aging is switched on and tasks are waiting)

so, WITHOUT aging, the work done is about (number of events) x O(log q), where
q is the number of waiting tasks, and it does not depend on how much time is
simulated. WITH aging every tick also raises every waiting task with
increase_key, which costs O(q log q) per tick; REPORT.md measures what that does
to the running time.

Policies. They only differ in what number is used as a task's priority:

    "priority"  the task's own priority (bigger = more urgent)
    "edf"       earliest deadline first: priority = -deadline
    "fcfs"      first come first served: priority = -arrival_time

Ties are broken by the queue's ordering rule (earlier deadline, then earlier
arrival, then smaller id). So "fcfs" is only pure first-come-first-served when
the arrival times differ; two tasks that arrive together are ordered by deadline.

Options.

    preemptive   True (default): a task that outranks the running one takes the
                 CPU at once (a new arrival, or a waiting task that aging has
                 just lifted above it); the running task goes back in the queue
                 with its remaining time. False: the running task always
                 finishes first.
    aging        With aging_interval=N, at every multiple of N time units each
                 WAITING task's priority goes up by aging_step (using
                 increase_key). "Waiting" means it arrived before that moment
                 and is not the task currently on the CPU. This stops
                 low-priority tasks from waiting forever behind a steady
                 stream of high-priority ones (starvation).

Times (arrival_time, burst_time, aging_interval) must be integers or
fractions.Fraction. Floats are rejected: 0.1 + 0.2 - 0.1 is not exactly 0.2, so
a task could be left with a tiny leftover burst, and time would stop advancing
(the first version of this module looped forever on such input).

Priorities and deadlines may be any numbers that can be compared with each
other, and task ids must be mutually comparable (all ints, for example).
"""

import random
from dataclasses import dataclass
from numbers import Number, Rational

from priority_queue import PriorityQueue, Task, outranks

POLICIES = {
    "priority": lambda t: t.priority,
    "edf": lambda t: -t.deadline,
    "fcfs": lambda t: -t.arrival_time,
}


@dataclass
class ScheduleResult:
    timeline: list  # [(task_id, start, end), ...] in time order; gaps mean the CPU was idle
    finish_time: dict  # task_id -> time it completed
    first_start: dict  # task_id -> first time it got the CPU
    preemptions: int  # times a running task was pushed back by a higher-ranked task
    queue_moves: int = 0  # total levels moved inside the heap (a cost measure)
    events: int = 0  # number of simulation steps taken
    max_queue_length: int = 0  # most tasks ever waiting at once (the running task is not counted)
    queue_time_area: object = 0  # sum over time of (number of waiting tasks); divide by makespan for the mean
    tie_preemptions: int = 0  # preemptions between tasks of EQUAL priority (decided by the tie-break rule)
    aging_ticks: int = 0  # aging ticks that were applied
    aging_updates: int = 0  # increase_key calls made by aging


def _require_exact_time(name, value):
    if isinstance(value, bool) or not isinstance(value, Rational):
        raise ValueError(
            f"{name} must be an int or fractions.Fraction, got {value!r} "
            "(floats cannot be added exactly, and the simulation could stop advancing)"
        )


def simulate(tasks, policy="priority", preemptive=True, aging_interval=None, aging_step=1):
    """Run the schedule and return a ScheduleResult. The input tasks are not changed."""
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy!r}; use one of {sorted(POLICIES)}")
    if aging_interval is not None:
        _require_exact_time("aging_interval", aging_interval)
        if aging_interval <= 0:
            raise ValueError("aging_interval must be positive")
    if isinstance(aging_step, bool) or not isinstance(aging_step, Number) or aging_step < 0:
        raise ValueError(f"aging_step must be a number that is not negative, got {aging_step!r}")
    ids = [t.task_id for t in tasks]
    if len(set(ids)) != len(ids):
        raise ValueError("task ids must be unique")
    for t in tasks:
        _require_exact_time(f"arrival_time of task {t.task_id!r}", t.arrival_time)
        _require_exact_time(f"burst_time of task {t.task_id!r}", t.burst_time)
        if t.arrival_time < 0:
            raise ValueError(f"arrival_time of task {t.task_id!r} must not be negative")

    score = POLICIES[policy]
    jobs = [Task(t.task_id, score(t), t.arrival_time, t.deadline, t.burst_time) for t in tasks]
    arrivals = sorted(jobs, key=lambda t: (t.arrival_time, t.task_id))
    total = len(arrivals)

    ready = PriorityQueue()
    timeline, finish, first_start = [], {}, {}
    nxt = 0  # next index in `arrivals` that has not been admitted yet
    now = 0
    running = None
    segment_start = 0
    preemptions = tie_preemptions = 0
    events = 0
    max_queue = 0
    queue_area = 0
    aging_ticks = aging_updates = 0

    while len(finish) < total:
        if running is None and ready.is_empty():
            now = max(now, arrivals[nxt].arrival_time)  # CPU idles until the next arrival
        while nxt < total and arrivals[nxt].arrival_time <= now:
            ready.insert(arrivals[nxt])
            nxt += 1
        if running is None:
            running = ready.extract_max()
            segment_start = now
            first_start.setdefault(running.task_id, now)

        # Jump to the next moment anything can change.
        next_time = now + running.remaining_time
        if nxt < total:
            next_time = min(next_time, arrivals[nxt].arrival_time)
        if aging_interval is not None and not ready.is_empty():
            next_time = min(next_time, (now // aging_interval + 1) * aging_interval)
        waiting = len(ready)  # nothing changes between now and next_time
        max_queue = max(max_queue, waiting)
        queue_area += waiting * (next_time - now)
        running.remaining_time -= next_time - now
        now = next_time
        events += 1

        if running.remaining_time == 0:
            timeline.append((running.task_id, segment_start, now))
            finish[running.task_id] = now
            running = None

        while nxt < total and arrivals[nxt].arrival_time <= now:
            ready.insert(arrivals[nxt])
            nxt += 1

        if aging_interval is not None and now % aging_interval == 0:
            aging_ticks += 1
            for waiting_task in ready.tasks():
                if waiting_task.arrival_time < now:  # only tasks that have really waited
                    ready.increase_key(waiting_task, waiting_task.priority + aging_step)
                    aging_updates += 1

        if preemptive and running is not None and not ready.is_empty() and outranks(ready.peek(), running):
            if ready.peek().priority == running.priority:
                tie_preemptions += 1
            timeline.append((running.task_id, segment_start, now))
            ready.insert(running)
            running = None
            preemptions += 1

    return ScheduleResult(timeline, finish, first_start, preemptions, ready.moves, events,
                          max_queue, queue_area, tie_preemptions, aging_ticks, aging_updates)


def summarize(tasks, result):
    """Headline numbers for one schedule.

    waiting         time spent ready but not running = finish - arrival - burst
    turnaround      finish - arrival
    response        first time on the CPU - arrival
    queue length    number of tasks waiting (not counting the running one); the
                    mean is over the whole run from time 0 to the last finish
    """
    if not tasks:
        return {"mean_waiting": 0.0, "max_waiting": 0, "mean_turnaround": 0.0, "mean_response": 0.0,
                "missed_deadlines": 0, "makespan": 0, "busy_time": 0, "utilization": 0.0,
                "preemptions": result.preemptions, "tie_preemptions": result.tie_preemptions,
                "mean_queue_length": 0.0, "max_queue_length": 0}
    waits, turns, resp, missed = [], [], [], 0
    for t in tasks:
        finish = result.finish_time[t.task_id]
        turn = finish - t.arrival_time
        turns.append(turn)
        waits.append(turn - t.burst_time)
        resp.append(result.first_start[t.task_id] - t.arrival_time)
        if finish > t.deadline:
            missed += 1
    n = len(tasks)
    makespan = max(result.finish_time.values())
    busy = sum(t.burst_time for t in tasks)
    return {
        "mean_waiting": sum(waits) / n,
        "max_waiting": max(waits),
        "mean_turnaround": sum(turns) / n,
        "mean_response": sum(resp) / n,
        "missed_deadlines": missed,
        "makespan": makespan,
        "busy_time": busy,
        "utilization": busy / makespan,
        "preemptions": result.preemptions,
        "tie_preemptions": result.tie_preemptions,
        "mean_queue_length": result.queue_time_area / makespan,
        "max_queue_length": result.max_queue_length,
    }


def waiting_by_priority(tasks, result):
    """Mean and max waiting time for each ORIGINAL priority level: {priority: (mean, max, count)}."""
    groups = {}
    for t in tasks:
        wait = result.finish_time[t.task_id] - t.arrival_time - t.burst_time
        groups.setdefault(t.priority, []).append(wait)
    return {p: (sum(w) / len(w), max(w), len(w)) for p, w in sorted(groups.items(), reverse=True)}


SLACK_MODES = ("proportional", "independent")


def generate_workload(n, seed=0, mean_gap=6, max_burst=10, priorities=5, max_slack_multiple=3,
                      slack_mode="proportional"):
    """Make n random tasks, reproducible from the seed.

    The gap between arrivals is uniform on 0 .. 2*mean_gap (so it averages
    mean_gap). With the defaults the average burst is 5.5 and the average gap is
    6, which keeps the CPU about 92% loaded. Each deadline is arrival + burst +
    a random slack, drawn one of two ways:

    slack_mode="proportional" (default)
        slack is uniform on 0 .. max_slack_multiple x burst, so long tasks get
        more slack and a short task's deadline tends to be earlier.
    slack_mode="independent"
        slack is uniform on 0 .. round(max_slack_multiple x (1 + max_burst) / 2),
        the same on average as the proportional rule but unrelated to the
        task's own burst. Used in REPORT.md to check how much the policy
        comparison depends on the deadline rule.

    For one seed the two modes produce the same tasks except for their
    deadlines. (The "proportional" draw is also made, and thrown away, in
    "independent" mode so that both modes use up the main random stream in the
    same way; the independent slack itself comes from a separate stream. This
    also keeps the default mode producing exactly the workloads that the
    results in REPORT.md were made from.)
    """
    if slack_mode not in SLACK_MODES:
        raise ValueError(f"unknown slack_mode {slack_mode!r}; use one of {SLACK_MODES}")
    rng = random.Random(seed)
    slack_rng = random.Random(seed * 1_000_003 + 17)
    independent_max = round(max_slack_multiple * (1 + max_burst) / 2)
    tasks = []
    arrival = 0
    for task_id in range(1, n + 1):
        arrival += rng.randint(0, 2 * mean_gap)
        burst = rng.randint(1, max_burst)
        priority = rng.randint(1, priorities)
        slack = rng.randint(0, max_slack_multiple * burst)
        if slack_mode == "independent":
            slack = slack_rng.randint(0, independent_max)
        tasks.append(Task(task_id, priority, arrival, arrival + burst + slack, burst))
    return tasks
