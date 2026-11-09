"""
Tests for other_sorts.py (the Quicksort and Merge Sort used for comparison).

Run from this folder:  python -m unittest -v
"""

import math
import random
import unittest

from counting import CountingKey, get_count, reset_count
from other_sorts import merge_sort, quicksort

SORTERS = {
    "quicksort": lambda a: quicksort(a, rng=random.Random(3)),
    "merge_sort": merge_sort,
}

EDGE_CASES = {
    "empty": [],
    "single": [7],
    "two reversed": [2, 1],
    "already sorted": list(range(50)),
    "reverse sorted": list(range(50, 0, -1)),
    "all equal": [5] * 40,
    "few distinct values": [(i * 7) % 3 for i in range(200)],
    "negatives and zeros": [-5, 0, 3, -2, 0, 9, -5],
    "strings": ["pear", "apple", "fig", "apple", "kiwi"],
}


class _Keyed:
    """Compares by .key only, so equal keys can still be told apart."""

    def __init__(self, key, tag):
        self.key, self.tag = key, tag

    def __lt__(self, other):
        return self.key < other.key

    def __gt__(self, other):
        return self.key > other.key


class CorrectnessTests(unittest.TestCase):
    def test_edge_cases_match_builtin_sorted(self):
        for sorter_name, sorter in SORTERS.items():
            for case_name, data in EDGE_CASES.items():
                with self.subTest(sorter=sorter_name, case=case_name):
                    arr = list(data)
                    result = sorter(arr)
                    self.assertIs(result, arr)
                    self.assertEqual(arr, sorted(data))

    def test_random_arrays_match_builtin_sorted(self):
        gen = random.Random(77)
        for sorter_name, sorter in SORTERS.items():
            for trial in range(150):
                data = [gen.randint(-25, 25) for _ in range(gen.randint(0, 70))]
                with self.subTest(sorter=sorter_name, trial=trial):
                    arr = list(data)
                    sorter(arr)
                    self.assertEqual(arr, sorted(data))

    def test_quicksort_survives_sorted_input_past_the_recursion_limit(self):
        arr = list(range(5000))
        quicksort(arr, rng=random.Random(1))
        self.assertEqual(arr, list(range(5000)))

    def test_quicksort_stack_stays_shallow_even_with_the_worst_pivot_choices(self):
        # A "random" source that always answers "the first position" makes every
        # split lopsided. Recursing into the smaller side first is what keeps
        # the stack from growing to n levels and hitting Python's limit.
        class AlwaysFirst:
            def randint(self, lo, hi):
                return lo

        for name, data in (("sorted", list(range(3000))), ("reverse", list(range(3000, 0, -1)))):
            with self.subTest(case=name):
                arr = list(data)
                quicksort(arr, rng=AlwaysFirst())
                self.assertEqual(arr, sorted(data))

    def test_merge_sort_is_stable(self):
        gen = random.Random(8)
        items = [_Keyed(gen.randint(0, 5), i) for i in range(300)]
        merge_sort(items)
        for a, b in zip(items, items[1:]):
            self.assertLessEqual(a.key, b.key)
            if a.key == b.key:
                self.assertLess(a.tag, b.tag)  # original order kept


class CostTests(unittest.TestCase):
    @staticmethod
    def _count(sorter, values):
        reset_count()
        arr = [CountingKey(v) for v in values]
        sorter(arr)
        assert [k.value for k in arr] == sorted(values)
        return get_count()

    def test_merge_sort_never_uses_more_than_n_log_n_comparisons(self):
        n = 4096
        for name, values in (
            ("sorted", list(range(n))),
            ("reverse", list(range(n, 0, -1))),
            ("random", random.Random(4).sample(range(n), n)),
        ):
            with self.subTest(case=name):
                self.assertLessEqual(self._count(merge_sort, values), n * math.log2(n))

    def test_quicksort_on_sorted_input_is_not_quadratic(self):
        n = 4000
        count = self._count(SORTERS["quicksort"], list(range(n)))
        self.assertLess(count, 4 * n * math.log2(n))  # quadratic would be ~ 8,000,000

    def test_quicksort_on_all_equal_input_is_linear(self):
        n = 10_000
        self.assertLessEqual(self._count(SORTERS["quicksort"], [3] * n), 2 * n + 10)


if __name__ == "__main__":
    unittest.main()
