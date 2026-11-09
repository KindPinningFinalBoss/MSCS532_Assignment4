"""
Tests for scheduler.py (event-driven scheduler simulation built on the heap).

Run from this folder:  python -m unittest -v
"""

import statistics
import threading
import unittest
from fractions import Fraction

from priority_queue import Task
from scheduler import generate_workload, simulate, summarize


def example_tasks(c_deadline=10):
    return [
        Task(1, priority=1, arrival_time=0, deadline=20, burst_time=5),  # A
        Task(2, priority=3, arrival_time=1, deadline=10, burst_time=2),  # B
        Task(3, priority=2, arrival_time=2, deadline=c_deadline, burst_time=1),  # C
    ]


def reference_sequence(tasks, policy="priority", preemptive=True, aging_interval=None, aging_step=1):
    """Slow, obviously-correct simulator: one time unit per loop, scan every task.

    Returns a list with one entry per time unit: the id of the task that ran
    during that unit, or None if the CPU was idle.
    """
    by_id = {t.task_id: t for t in tasks}
    score = {
        "priority": lambda t: t.priority,
        "edf": lambda t: -t.deadline,
        "fcfs": lambda t: -t.arrival_time,
    }[policy]
    prio = {t.task_id: score(t) for t in tasks}
    remaining = {t.task_id: t.burst_time for t in tasks}
    seq, now, done, last_ran = [], 0, 0, None
    while done < len(tasks):
        ready = [i for i in remaining if remaining[i] > 0 and by_id[i].arrival_time <= now]
        if aging_interval and now > 0 and now % aging_interval == 0:
            for i in ready:
                # "Waiting" = arrived earlier than this moment and not the task
                # that was just on the CPU.
                if i != last_ran and by_id[i].arrival_time < now:
                    prio[i] += aging_step
        if not ready:
            seq.append(None)
            last_ran = None
            now += 1
            continue
        if not preemptive and last_ran is not None and remaining[last_ran] > 0:
            best = last_ran
        else:
            best = max(ready, key=lambda i: (prio[i], -by_id[i].deadline, -by_id[i].arrival_time, -i))
        remaining[best] -= 1
        if remaining[best] == 0:
            done += 1
        seq.append(best)
        last_ran = best
        now += 1
    return seq


def timeline_to_sequence(timeline):
    seq = []
    for task_id, start, end in timeline:
        seq.extend([None] * (start - len(seq)))
        seq.extend([task_id] * (end - start))
    return seq


class HandWorkedExampleTests(unittest.TestCase):
    def test_preemptive_priority_timeline(self):
        # A starts, B (higher priority) preempts at t=1, C waits behind B,
        # then C runs before A resumes.
        result = simulate(example_tasks(), policy="priority", preemptive=True)
        self.assertEqual(result.timeline, [(1, 0, 1), (2, 1, 3), (3, 3, 4), (1, 4, 8)])
        self.assertEqual(result.finish_time, {2: 3, 3: 4, 1: 8})
        self.assertEqual(result.preemptions, 1)

    def test_non_preemptive_priority_timeline(self):
        result = simulate(example_tasks(), policy="priority", preemptive=False)
        self.assertEqual(result.timeline, [(1, 0, 5), (2, 5, 7), (3, 7, 8)])
        self.assertEqual(result.preemptions, 0)

    def test_summary_numbers(self):
        tasks = example_tasks(c_deadline=3)  # C will finish at 4, one unit late
        summary = summarize(tasks, simulate(tasks, preemptive=True))
        # waiting = finish - arrival - burst: A 3, B 0, C 1
        self.assertAlmostEqual(summary["mean_waiting"], 4 / 3)
        self.assertEqual(summary["max_waiting"], 3)
        # turnaround = finish - arrival: A 8, B 2, C 2
        self.assertAlmostEqual(summary["mean_turnaround"], 4.0)
        # response = first start - arrival: A 0, B 0, C 1
        self.assertAlmostEqual(summary["mean_response"], 1 / 3)
        self.assertEqual(summary["missed_deadlines"], 1)
        self.assertEqual(summary["makespan"], 8)
        self.assertEqual(summary["busy_time"], 8)
        self.assertEqual(summary["preemptions"], 1)

    def test_cpu_idles_when_nothing_is_ready(self):
        tasks = [Task(1, 1, arrival_time=0, burst_time=2), Task(2, 1, arrival_time=5, burst_time=1)]
        result = simulate(tasks)
        self.assertEqual(result.timeline, [(1, 0, 2), (2, 5, 6)])
        summary = summarize(tasks, result)
        self.assertEqual(summary["makespan"], 6)
        self.assertEqual(summary["busy_time"], 3)

    def test_arrival_that_does_not_preempt_does_not_split_the_segment(self):
        tasks = [Task(1, 9, arrival_time=0, burst_time=6), Task(2, 1, arrival_time=2, burst_time=1)]
        self.assertEqual(simulate(tasks).timeline, [(1, 0, 6), (2, 6, 7)])

    def test_input_tasks_are_not_modified(self):
        tasks = example_tasks()
        simulate(tasks, policy="edf", aging_interval=3)
        self.assertEqual([t.priority for t in tasks], [1, 3, 2])
        self.assertEqual([t.remaining_time for t in tasks], [5, 2, 1])

    def test_edf_runs_the_earliest_deadline_first(self):
        tasks = [
            Task(1, priority=9, arrival_time=0, deadline=10, burst_time=3),
            Task(2, priority=1, arrival_time=0, deadline=5, burst_time=3),
        ]
        self.assertEqual(simulate(tasks, policy="edf").timeline, [(2, 0, 3), (1, 3, 6)])

    def test_fcfs_runs_in_arrival_order(self):
        tasks = [
            Task(1, priority=1, arrival_time=0, burst_time=4),
            Task(2, priority=9, arrival_time=1, burst_time=2),
            Task(3, priority=5, arrival_time=2, burst_time=2),
        ]
        self.assertEqual(simulate(tasks, policy="fcfs").timeline, [(1, 0, 4), (2, 4, 6), (3, 6, 8)])

    def test_bad_arguments_are_rejected(self):
        with self.assertRaises(ValueError):
            simulate(example_tasks(), policy="round-robin")
        with self.assertRaises(ValueError):
            simulate(example_tasks(), aging_interval=0)
        with self.assertRaises(ValueError):
            simulate([Task(1, 1), Task(1, 2)])  # duplicate ids

    def test_empty_workload(self):
        result = simulate([])
        self.assertEqual(result.timeline, [])
        self.assertEqual(summarize([], result)["makespan"], 0)


class AgingTests(unittest.TestCase):
    def test_aging_rescues_a_starved_low_priority_task(self):
        # A steady stream of priority-5 jobs keeps the CPU 100% busy, so the
        # priority-1 task L never runs until the stream ends, unless aging
        # slowly raises its priority above 5.
        def make():
            tasks = [Task(100, priority=1, arrival_time=0, deadline=10_000, burst_time=3)]
            tasks += [Task(i, priority=5, arrival_time=2 * i, deadline=2 * i + 2, burst_time=2)
                      for i in range(20)]
            return tasks

        plain = simulate(make())
        aged = simulate(make(), aging_interval=4, aging_step=1)
        self.assertEqual(plain.finish_time[100], 43)  # after all 20 stream jobs (40) + its own 3
        self.assertLess(aged.finish_time[100], 30)
        # The cost of aging is visible in the counters: every tick raises every waiting task.
        self.assertEqual((plain.aging_ticks, plain.aging_updates), (0, 0))
        self.assertGreater(aged.aging_ticks, 0)
        self.assertGreaterEqual(aged.aging_updates, aged.aging_ticks)


class TimeValidationTests(unittest.TestCase):
    def test_float_times_are_rejected_instead_of_hanging(self):
        # With floats, remaining_time can end at -2.8e-17 instead of 0, time
        # stops advancing, and the old simulate() never returned.
        with self.assertRaises(ValueError):
            simulate([Task(1, 1, arrival_time=0.1, burst_time=1)])
        with self.assertRaises(ValueError):
            simulate([Task(1, 1, arrival_time=0, burst_time=0.2)])

    def test_the_exact_input_that_used_to_hang_now_raises(self):
        # arrival 0.1 + burst 0.2 left remaining_time at -2.8e-17, so time never
        # advanced. Run it on a watchdog thread so a regression fails instead
        # of freezing the whole test run.
        outcome = {}

        def run():
            try:
                simulate([Task(1, 1, arrival_time=0.1, burst_time=0.2)])
                outcome["result"] = "returned"
            except ValueError:
                outcome["result"] = "ValueError"

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive(), "simulate() did not return")
        self.assertEqual(outcome.get("result"), "ValueError")

    def test_fractions_are_accepted_and_stay_exact(self):
        tasks = [Task(1, 1, arrival_time=Fraction(1, 2), burst_time=Fraction(3, 2))]
        result = simulate(tasks)
        self.assertEqual(result.timeline, [(1, Fraction(1, 2), 2)])
        self.assertEqual(result.finish_time[1], 2)

    def test_negative_arrival_time_is_rejected(self):
        with self.assertRaises(ValueError):
            simulate([Task(1, 1, arrival_time=-1, burst_time=1)])

    def test_bad_aging_arguments_are_rejected(self):
        tasks = example_tasks()
        with self.assertRaises(ValueError):
            simulate(tasks, aging_interval=2.5)  # not an exact time
        with self.assertRaises(ValueError):
            simulate(tasks, aging_interval=3, aging_step=-1)  # a negative boost
        simulate(tasks, aging_interval=3, aging_step=0)  # zero is allowed (aging does nothing)


class QueueStatisticsTests(unittest.TestCase):
    def test_hand_worked_queue_lengths(self):
        # Waiting tasks over time: [0,1) none; [1,2) A; [2,3) A and C; [3,4) A; [4,8) none.
        # Task-time spent waiting = 0 + 1 + 2 + 1 + 0 = 4, over a makespan of 8.
        tasks = example_tasks()
        summary = summarize(tasks, simulate(tasks, preemptive=True))
        self.assertEqual(summary["max_queue_length"], 2)
        self.assertAlmostEqual(summary["mean_queue_length"], 4 / 8)

    def test_a_lone_task_never_waits(self):
        tasks = [Task(1, 1, arrival_time=3, burst_time=4)]
        summary = summarize(tasks, simulate(tasks))
        self.assertEqual(summary["max_queue_length"], 0)
        self.assertEqual(summary["mean_queue_length"], 0)


class PreemptionCountingTests(unittest.TestCase):
    def test_equal_priority_preemption_is_counted_separately(self):
        # Same priority, but the newcomer has the earlier deadline, so the
        # tie-break rule lets it preempt.
        tie = [Task(1, 5, arrival_time=0, deadline=100, burst_time=10),
               Task(2, 5, arrival_time=1, deadline=20, burst_time=2)]
        result = simulate(tie)
        self.assertEqual((result.preemptions, result.tie_preemptions), (1, 1))
        higher = [Task(1, 5, arrival_time=0, deadline=100, burst_time=10),
                  Task(2, 9, arrival_time=1, deadline=20, burst_time=2)]
        result = simulate(higher)
        self.assertEqual((result.preemptions, result.tie_preemptions), (1, 0))


class DeadlineBoundaryTests(unittest.TestCase):
    def test_finishing_exactly_at_the_deadline_is_not_a_miss(self):
        on_time = [Task(1, 1, arrival_time=0, deadline=5, burst_time=5)]
        late = [Task(1, 1, arrival_time=0, deadline=4, burst_time=5)]
        self.assertEqual(summarize(on_time, simulate(on_time))["missed_deadlines"], 0)
        self.assertEqual(summarize(late, simulate(late))["missed_deadlines"], 1)


class WorkloadGeneratorTests(unittest.TestCase):
    def test_independent_slack_changes_only_the_deadlines(self):
        proportional = generate_workload(200, seed=3)
        independent = generate_workload(200, seed=3, slack_mode="independent")
        same_part = lambda ts: [(t.task_id, t.priority, t.arrival_time, t.burst_time) for t in ts]
        self.assertEqual(same_part(proportional), same_part(independent))
        self.assertNotEqual([t.deadline for t in proportional], [t.deadline for t in independent])
        for t in independent:
            self.assertGreaterEqual(t.deadline, t.arrival_time + t.burst_time)

    def test_proportional_slack_follows_burst_and_independent_slack_does_not(self):
        def slack_burst_correlation(tasks):
            slack = [t.deadline - t.arrival_time - t.burst_time for t in tasks]
            return statistics.correlation(slack, [t.burst_time for t in tasks])

        self.assertGreater(slack_burst_correlation(generate_workload(3000, seed=1)), 0.4)
        self.assertLess(abs(slack_burst_correlation(generate_workload(3000, seed=1, slack_mode="independent"))), 0.1)

    def test_unknown_slack_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            generate_workload(5, slack_mode="random-ish")

    def test_same_seed_gives_the_same_workload(self):
        a = generate_workload(50, seed=4)
        b = generate_workload(50, seed=4)
        key = lambda ts: [(t.task_id, t.priority, t.arrival_time, t.deadline, t.burst_time) for t in ts]
        self.assertEqual(key(a), key(b))
        self.assertNotEqual(key(a), key(generate_workload(50, seed=5)))

    def test_fields_are_in_range(self):
        tasks = generate_workload(200, seed=1, priorities=5, max_burst=8)
        self.assertEqual([t.task_id for t in tasks], list(range(1, 201)))
        arrivals = [t.arrival_time for t in tasks]
        self.assertEqual(arrivals, sorted(arrivals))
        for t in tasks:
            self.assertTrue(1 <= t.priority <= 5)
            self.assertTrue(1 <= t.burst_time <= 8)
            self.assertGreaterEqual(t.deadline, t.arrival_time + t.burst_time)


class AgreementWithSlowReferenceTests(unittest.TestCase):
    """The heap-based simulator must give the same schedule, unit by unit, as a
    brute-force simulator that rescans every task at every tick."""

    def _check(self, tasks, **options):
        result = simulate(tasks, **options)
        self.assertEqual(
            timeline_to_sequence(result.timeline),
            reference_sequence(tasks, **options),
            options,
        )
        return result

    def test_random_workloads_every_policy_preemptive_and_not(self):
        for seed in range(25):
            tasks = generate_workload(30, seed=seed, mean_gap=3, max_burst=6, priorities=4)
            for policy in ("priority", "edf", "fcfs"):
                for preemptive in (True, False):
                    with self.subTest(seed=seed, policy=policy, preemptive=preemptive):
                        self._check(tasks, policy=policy, preemptive=preemptive)

    def test_random_workloads_with_aging(self):
        for seed in range(25):
            tasks = generate_workload(30, seed=100 + seed, mean_gap=2, max_burst=6, priorities=5)
            for interval, step in ((3, 1), (7, 2)):
                for preemptive in (True, False):
                    with self.subTest(seed=seed, interval=interval, step=step, preemptive=preemptive):
                        self._check(tasks, aging_interval=interval, aging_step=step, preemptive=preemptive)

    def test_basic_invariants_on_a_bigger_workload(self):
        tasks = generate_workload(400, seed=11)
        result = simulate(tasks)
        by_id = {t.task_id: t for t in tasks}
        ran = {t.task_id: 0 for t in tasks}
        previous_end = 0
        for task_id, start, end in result.timeline:
            self.assertGreaterEqual(start, previous_end)  # no overlap, in order
            self.assertGreater(end, start)
            self.assertGreaterEqual(start, by_id[task_id].arrival_time)  # never early
            ran[task_id] += end - start
            previous_end = end
        for task_id, task in by_id.items():
            self.assertEqual(ran[task_id], task.burst_time)  # got exactly its burst
            self.assertIn(task_id, result.finish_time)
        summary = summarize(tasks, result)
        self.assertEqual(summary["busy_time"], sum(t.burst_time for t in tasks))
        self.assertGreaterEqual(summary["mean_waiting"], 0)


if __name__ == "__main__":
    unittest.main()
