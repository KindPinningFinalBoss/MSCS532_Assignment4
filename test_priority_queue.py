"""
Tests for priority_queue.py (Task and the binary max-heap PriorityQueue).

Run from this folder:  python -m unittest -v
"""

import math
import random
import unittest

from priority_queue import PriorityQueue, Task, outranks


def model_best(tasks):
    """Reference answer: the task a correct queue must hand out next."""
    return max(tasks, key=lambda t: (t.priority, -t.deadline, -t.arrival_time, -t.task_id))


class TaskTests(unittest.TestCase):
    def test_task_stores_its_fields(self):
        t = Task(7, priority=3, arrival_time=2, deadline=15, burst_time=4)
        self.assertEqual((t.task_id, t.priority, t.arrival_time, t.deadline), (7, 3, 2, 15))
        self.assertEqual(t.burst_time, 4)
        self.assertEqual(t.remaining_time, 4)

    def test_defaults(self):
        t = Task(1, priority=5)
        self.assertEqual(t.arrival_time, 0)
        self.assertEqual(t.deadline, math.inf)
        self.assertEqual(t.burst_time, 1)

    def test_non_positive_burst_is_rejected(self):
        with self.assertRaises(ValueError):
            Task(1, priority=1, burst_time=0)

    def test_outranks_uses_priority_then_deadline_then_arrival_then_id(self):
        base = dict(arrival_time=5, deadline=50)
        self.assertTrue(outranks(Task(1, 9, **base), Task(2, 3, **base)))
        self.assertFalse(outranks(Task(2, 3, **base), Task(1, 9, **base)))
        # same priority: earlier deadline wins
        self.assertTrue(outranks(Task(1, 5, arrival_time=0, deadline=10), Task(2, 5, arrival_time=0, deadline=20)))
        # same priority and deadline: earlier arrival wins
        self.assertTrue(outranks(Task(1, 5, arrival_time=1, deadline=10), Task(2, 5, arrival_time=2, deadline=10)))
        # all equal except id: smaller id wins
        self.assertTrue(outranks(Task(1, 5, arrival_time=1, deadline=10), Task(2, 5, arrival_time=1, deadline=10)))
        # a task never outranks itself
        t = Task(1, 5)
        self.assertFalse(outranks(t, t))


class BasicOperationTests(unittest.TestCase):
    def test_new_queue_is_empty(self):
        pq = PriorityQueue()
        self.assertTrue(pq.is_empty())
        self.assertEqual(len(pq), 0)

    def test_insert_makes_it_non_empty(self):
        pq = PriorityQueue()
        pq.insert(Task(1, 5))
        self.assertFalse(pq.is_empty())
        self.assertEqual(len(pq), 1)

    def test_extract_max_returns_highest_priority_first(self):
        pq = PriorityQueue()
        for task_id, prio in [(1, 3), (2, 9), (3, 1), (4, 7), (5, 5)]:
            pq.insert(Task(task_id, prio))
        order = []
        while not pq.is_empty():
            order.append(pq.extract_max().task_id)
        self.assertEqual(order, [2, 4, 5, 1, 3])

    def test_peek_shows_the_top_without_removing_it(self):
        pq = PriorityQueue()
        pq.insert(Task(1, 3))
        pq.insert(Task(2, 8))
        self.assertEqual(pq.peek().task_id, 2)
        self.assertEqual(len(pq), 2)

    def test_empty_queue_raises_on_extract_and_peek(self):
        pq = PriorityQueue()
        with self.assertRaises(IndexError):
            pq.extract_max()
        with self.assertRaises(IndexError):
            pq.peek()

    def test_ties_break_by_deadline_then_arrival_then_id(self):
        pq = PriorityQueue()
        pq.insert(Task(1, 5, arrival_time=0, deadline=30))
        pq.insert(Task(2, 5, arrival_time=0, deadline=10))
        pq.insert(Task(3, 5, arrival_time=4, deadline=10))
        pq.insert(Task(4, 5, arrival_time=4, deadline=10))
        order = [pq.extract_max().task_id for _ in range(4)]
        self.assertEqual(order, [2, 3, 4, 1])

    def test_inserting_a_duplicate_id_is_rejected(self):
        pq = PriorityQueue()
        pq.insert(Task(1, 5))
        with self.assertRaises(ValueError):
            pq.insert(Task(1, 9))
        self.assertEqual(len(pq), 1)

    def test_contains_looks_up_by_id(self):
        pq = PriorityQueue()
        t = Task(4, 2)
        pq.insert(t)
        self.assertIn(4, pq)
        self.assertNotIn(5, pq)
        pq.extract_max()
        self.assertNotIn(4, pq)

    def test_build_from_a_list_of_tasks(self):
        tasks = [Task(i, (i * 37) % 11) for i in range(1, 60)]
        pq = PriorityQueue(tasks)
        self.assertTrue(pq.is_valid())
        self.assertEqual(len(pq), len(tasks))
        out = [pq.extract_max().task_id for _ in range(len(tasks))]
        expected = [t.task_id for t in sorted(tasks, key=lambda t: (-t.priority, t.task_id))]
        self.assertEqual(out, expected)


class ChangeKeyTests(unittest.TestCase):
    def setUp(self):
        self.pq = PriorityQueue()
        self.tasks = {i: Task(i, p) for i, p in [(1, 10), (2, 20), (3, 30), (4, 40), (5, 50), (6, 5)]}
        for t in self.tasks.values():
            self.pq.insert(t)

    def test_increase_key_moves_a_task_to_the_front(self):
        self.pq.increase_key(self.tasks[6], 99)
        self.assertEqual(self.tasks[6].priority, 99)
        self.assertEqual(self.pq.peek().task_id, 6)
        self.assertTrue(self.pq.is_valid())

    def test_decrease_key_moves_the_top_task_back(self):
        self.pq.decrease_key(self.tasks[5], 1)
        self.assertEqual(self.pq.peek().task_id, 4)
        self.assertTrue(self.pq.is_valid())
        order = [self.pq.extract_max().task_id for _ in range(6)]
        self.assertEqual(order, [4, 3, 2, 1, 6, 5])

    def test_increase_key_rejects_a_lower_value(self):
        with self.assertRaises(ValueError):
            self.pq.increase_key(self.tasks[3], 5)

    def test_decrease_key_rejects_a_higher_value(self):
        with self.assertRaises(ValueError):
            self.pq.decrease_key(self.tasks[3], 500)

    def test_same_value_is_allowed(self):
        self.pq.increase_key(self.tasks[3], 30)
        self.pq.decrease_key(self.tasks[3], 30)
        self.assertTrue(self.pq.is_valid())

    def test_change_priority_works_in_both_directions(self):
        self.pq.change_priority(self.tasks[1], 100)
        self.assertEqual(self.pq.peek().task_id, 1)
        self.pq.change_priority(self.tasks[1], 0)
        self.assertEqual(self.pq.peek().task_id, 5)
        self.assertTrue(self.pq.is_valid())

    def test_unknown_task_raises_key_error(self):
        stranger = Task(99, 1)
        with self.assertRaises(KeyError):
            self.pq.increase_key(stranger, 5)
        with self.assertRaises(KeyError):
            self.pq.decrease_key(stranger, 0)

    def test_extracted_task_is_no_longer_known(self):
        top = self.pq.extract_max()
        with self.assertRaises(KeyError):
            self.pq.increase_key(top, 1000)


class IsValidTests(unittest.TestCase):
    """is_valid() is what the other tests lean on, so it has to be able to say False."""

    def test_detects_a_broken_heap_order(self):
        tasks = [Task(1, 9), Task(2, 5), Task(3, 4)]
        pq = PriorityQueue(tasks)
        self.assertTrue(pq.is_valid())
        tasks[1].priority = 99  # changing a queued task's priority behind the queue's back
        self.assertFalse(pq.is_valid())

    def test_detects_a_wrong_position_index(self):
        pq = PriorityQueue([Task(1, 9), Task(2, 5)])
        self.assertTrue(pq.is_valid())
        pq._pos[2] = 0
        self.assertFalse(pq.is_valid())

    def test_detects_a_missing_index_entry(self):
        pq = PriorityQueue([Task(1, 9), Task(2, 5)])
        del pq._pos[2]
        self.assertFalse(pq.is_valid())


class BulkBuildTests(unittest.TestCase):
    def test_random_lists_build_valid_heaps_that_extract_in_order(self):
        gen = random.Random(14)
        for _ in range(300):
            n = gen.randint(0, 80)
            tasks = [Task(i + 1, gen.randint(0, 15), arrival_time=gen.randint(0, 9),
                          deadline=gen.randint(10, 40)) for i in range(n)]
            pq = PriorityQueue(tasks)
            self.assertTrue(pq.is_valid())
            expected = sorted(tasks, key=lambda t: (-t.priority, t.deadline, t.arrival_time, t.task_id))
            self.assertEqual([pq.extract_max().task_id for _ in range(n)], [t.task_id for t in expected])

    def test_duplicate_ids_in_the_starting_list_are_rejected(self):
        with self.assertRaises(ValueError):
            PriorityQueue([Task(1, 5), Task(1, 6)])


class SameIdImpostorTests(unittest.TestCase):
    def test_a_different_task_object_with_a_queued_id_is_not_accepted(self):
        pq = PriorityQueue()
        real = Task(1, 5)
        pq.insert(real)
        impostor = Task(1, 50)
        with self.assertRaises(KeyError):
            pq.increase_key(impostor, 60)
        with self.assertRaises(KeyError):
            pq.decrease_key(impostor, 0)
        self.assertEqual(real.priority, 5)


class ExactMoveCountTests(unittest.TestCase):
    """The cost-bound tests give only upper limits on `moves`. These pin exact
    values for hand-worked cases, so a counter that is never updated fails."""

    @staticmethod
    def _heap(priorities):
        tasks = [Task(i + 1, p) for i, p in enumerate(priorities)]
        pq = PriorityQueue(tasks)  # the list is already in heap order, so building moves nothing
        assert pq.moves == 0
        return pq, tasks

    def test_insert_that_outranks_everything_climbs_to_the_root(self):
        pq, _ = self._heap([100, 90, 80, 70, 60, 50, 40])
        pq.insert(Task(99, 1000))  # index 7 -> 3 -> 1 -> 0
        self.assertEqual(pq.moves, 3)

    def test_insert_that_outranks_nothing_does_not_move(self):
        pq, _ = self._heap([100, 90, 80, 70, 60, 50, 40])
        pq.insert(Task(99, 1))
        self.assertEqual(pq.moves, 0)

    def test_extract_max_sinks_the_last_task_to_the_bottom(self):
        pq, _ = self._heap([100, 90, 80, 70, 60, 50, 1])
        pq.extract_max()  # the 1 goes to the root, then 90 and 70 move up past it
        self.assertEqual(pq.moves, 2)

    def test_increase_key_on_a_bottom_task_climbs_to_the_root(self):
        pq, tasks = self._heap([100, 90, 80, 70, 60, 50, 40])
        pq.increase_key(tasks[6], 1000)  # index 6 -> 2 -> 0
        self.assertEqual(pq.moves, 2)

    def test_decrease_key_on_the_root_sinks_to_the_bottom(self):
        pq, tasks = self._heap([100, 90, 80, 70, 60, 50, 40])
        pq.decrease_key(tasks[0], 1)  # index 0 -> 1 -> 3
        self.assertEqual(pq.moves, 2)


class InvariantFuzzTests(unittest.TestCase):
    def test_random_operations_match_a_simple_model(self):
        gen = random.Random(321)
        pq = PriorityQueue()
        live = {}  # task_id -> Task, the model
        next_id = 1
        for step in range(4000):
            action = gen.random()
            if action < 0.40 or not live:
                t = Task(next_id, gen.randint(0, 20), arrival_time=gen.randint(0, 50),
                         deadline=gen.randint(10, 100))
                next_id += 1
                pq.insert(t)
                live[t.task_id] = t
            elif action < 0.60:
                expected = model_best(live.values())
                got = pq.extract_max()
                self.assertIs(got, expected, f"step {step}")
                del live[got.task_id]
            elif action < 0.80:
                t = live[gen.choice(list(live))]
                pq.increase_key(t, t.priority + gen.randint(0, 10))
            else:
                t = live[gen.choice(list(live))]
                pq.decrease_key(t, t.priority - gen.randint(0, 10))
            self.assertEqual(len(pq), len(live))
            if live:
                self.assertIs(pq.peek(), model_best(live.values()), f"step {step}")
            if step % 50 == 0:
                self.assertTrue(pq.is_valid(), f"step {step}")
        self.assertTrue(pq.is_valid())


class CostBoundTests(unittest.TestCase):
    """Each operation walks one root-to-leaf path at most, so moves <= floor(log2 n)."""

    def test_moves_per_operation_never_exceed_the_tree_height(self):
        gen = random.Random(9)
        pq = PriorityQueue()
        tasks = []
        for i in range(1, 2049):
            before = pq.moves
            t = Task(i, gen.randint(0, 10**6))
            pq.insert(t)
            tasks.append(t)
            self.assertLessEqual(pq.moves - before, math.floor(math.log2(len(pq))))
        for t in gen.sample(tasks, 300):
            before = pq.moves
            pq.increase_key(t, t.priority + gen.randint(0, 10**6))
            self.assertLessEqual(pq.moves - before, math.floor(math.log2(len(pq))))
        while len(pq) > 1:
            n = len(pq)
            before = pq.moves
            pq.extract_max()
            self.assertLessEqual(pq.moves - before, math.floor(math.log2(n)))


if __name__ == "__main__":
    unittest.main()
