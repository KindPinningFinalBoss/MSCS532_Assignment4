"""
Tests for heapsort.py.

Run from this folder:  python -m unittest -v
"""

import math
import random
import unittest

from counting import CountingKey, get_count, reset_count
from heapsort import build_max_heap, heapsort, max_heapify

EDGE_CASES = {
    "empty": [],
    "single": [7],
    "two sorted": [1, 2],
    "two reversed": [2, 1],
    "two equal": [3, 3],
    "three": [2, 3, 1],
    "already sorted": list(range(50)),
    "reverse sorted": list(range(50, 0, -1)),
    "all equal": [5] * 40,
    "few distinct values": [(i * 7) % 3 for i in range(200)],
    "negatives and zeros": [-5, 0, 3, -2, 0, 9, -5],
    "floats": [3.5, -1.25, 2.0, 2.0, 0.0],
    "strings": ["pear", "apple", "fig", "apple", "kiwi"],
}


def is_max_heap(a, size=None):
    n = len(a) if size is None else size
    return all(a[(i - 1) // 2] >= a[i] for i in range(1, n))


class CorrectnessTests(unittest.TestCase):
    def test_edge_cases_match_builtin_sorted(self):
        for name, data in EDGE_CASES.items():
            with self.subTest(case=name):
                arr = list(data)
                heapsort(arr)
                self.assertEqual(arr, sorted(data))

    def test_sorts_in_place_and_returns_same_list(self):
        arr = [3, 1, 2]
        result = heapsort(arr)
        self.assertIs(result, arr)
        self.assertEqual(arr, [1, 2, 3])

    def test_random_arrays_match_builtin_sorted(self):
        gen = random.Random(2024)
        for trial in range(300):
            n = gen.randint(0, 80)
            data = [gen.randint(-30, 30) for _ in range(n)]
            with self.subTest(trial=trial):
                arr = list(data)
                heapsort(arr)
                self.assertEqual(arr, sorted(data))

    def test_large_sorted_and_reverse_inputs_need_no_recursion(self):
        n = 20_000  # far beyond Python's default recursion limit of 1,000
        for name, data in (("sorted", list(range(n))), ("reverse", list(range(n, 0, -1)))):
            with self.subTest(case=name):
                arr = list(data)
                heapsort(arr)
                self.assertEqual(arr, sorted(data))


class HeapPropertyTests(unittest.TestCase):
    def test_build_max_heap_creates_a_valid_heap(self):
        gen = random.Random(1)
        for _ in range(200):
            data = [gen.randint(0, 50) for _ in range(gen.randint(0, 60))]
            arr = list(data)
            build_max_heap(arr)
            self.assertTrue(is_max_heap(arr), arr)
            self.assertEqual(sorted(arr), sorted(data))  # same elements

    def test_build_max_heap_puts_the_maximum_at_the_root(self):
        arr = [4, 10, 3, 5, 1, 99, 7]
        build_max_heap(arr)
        self.assertEqual(arr[0], 99)

    def test_max_heapify_repairs_a_bad_root(self):
        arr = [50, 40, 45, 20, 30, 25, 44, 10, 15]
        self.assertTrue(is_max_heap(arr))
        arr[0] = 1  # break the heap at the root only
        max_heapify(arr, 0, len(arr))
        self.assertTrue(is_max_heap(arr))
        self.assertEqual(sorted(arr), sorted([1, 40, 45, 20, 30, 25, 44, 10, 15]))

    def test_max_heapify_leaves_elements_past_heap_size_alone(self):
        arr = [1, 9, 8, 100, 200]
        max_heapify(arr, 0, 3)
        self.assertEqual(arr[3:], [100, 200])
        self.assertTrue(is_max_heap(arr, 3))
        self.assertEqual(arr[0], 9)


class CostTests(unittest.TestCase):
    @staticmethod
    def _count(values):
        reset_count()
        arr = [CountingKey(v) for v in values]
        heapsort(arr)
        assert [k.value for k in arr] == sorted(values)
        return get_count()

    def test_comparisons_stay_within_the_proven_bound(self):
        # Building the heap costs at most about 2n comparisons and the n - 1
        # extractions at most 2 * floor(log2 k) each, so the total is at most
        # 2n + 2 n log2 n. (The extra 2n matters: it is why a bare "2 n log2 n"
        # check would only pass on lucky inputs.)
        n = 2000
        values = list(range(n))
        random.Random(5).shuffle(values)
        count = self._count(values)
        self.assertLessEqual(count, 2 * n + 2 * n * math.log2(n))
        self.assertGreaterEqual(count, n * math.log2(n))

    def test_cost_barely_depends_on_input_order_when_keys_are_distinct(self):
        n = 4000
        shuffled = list(range(n))
        random.Random(6).shuffle(shuffled)
        counts = [
            self._count(list(range(n))),
            self._count(list(range(n, 0, -1))),
            self._count(shuffled),
        ]
        self.assertLess(max(counts) / min(counts), 1.5, counts)

    def test_all_equal_keys_cost_only_about_3n_comparisons(self):
        # Nothing ever moves, so each heapify stops after its first level.
        n = 5000
        self.assertLessEqual(self._count([9] * n), 3 * n)


if __name__ == "__main__":
    unittest.main()
