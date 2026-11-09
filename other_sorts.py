"""
Randomized Quicksort and Merge Sort, written for the Heapsort comparison.

MSCS-532 Assignment 4. Both are plain Python with no use of sorted() or
list.sort(), so the timings against heapsort.py compare like with like.

quicksort    random pivot, three-way partition (so repeated values are cheap),
             and recursion only on the smaller side so the stack stays about
             log2(n) deep even on bad inputs. Same design as the Assignment 3
             version of the algorithm.
merge_sort   top-down, stable, one auxiliary buffer shared by every merge.
"""

import random


def quicksort(a, *, rng=None):
    """Sort a list in place with Randomized Quicksort. Returns the same list."""
    pick = (rng if rng is not None else random).randint
    lo, hi = 0, len(a) - 1
    # An explicit stack of pending ranges would also work; recursing into the
    # smaller side and looping on the larger keeps the code short.
    _quicksort(a, lo, hi, pick)
    return a


def _quicksort(a, lo, hi, pick):
    while lo < hi:
        pivot = a[pick(lo, hi)]
        lt, i, gt = lo, lo, hi  # a[lo:lt] < pivot, a[lt:i] == pivot, a[gt+1:hi+1] > pivot
        while i <= gt:
            x = a[i]
            if x < pivot:
                a[lt], a[i] = a[i], a[lt]
                lt += 1
                i += 1
            elif x > pivot:
                a[i], a[gt] = a[gt], a[i]
                gt -= 1
            else:
                i += 1
        if lt - lo < hi - gt:
            _quicksort(a, lo, lt - 1, pick)
            lo = gt + 1
        else:
            _quicksort(a, gt + 1, hi, pick)
            hi = lt - 1


def merge_sort(a):
    """Sort a list in place with a stable top-down merge sort. Returns the list."""
    if len(a) > 1:
        _merge_sort(a, a[:], 0, len(a))
    return a


def _merge_sort(a, buf, lo, hi):
    if hi - lo < 2:
        return
    mid = (lo + hi) // 2
    _merge_sort(a, buf, lo, mid)
    _merge_sort(a, buf, mid, hi)
    i, j, k = lo, mid, lo
    while i < mid and j < hi:
        # Take from the right half only when it is strictly smaller, which is
        # what keeps equal elements in their original order (stability).
        if a[j] < a[i]:
            buf[k] = a[j]
            j += 1
        else:
            buf[k] = a[i]
            i += 1
        k += 1
    while i < mid:
        buf[k] = a[i]
        i += 1
        k += 1
    while j < hi:
        buf[k] = a[j]
        j += 1
        k += 1
    a[lo:hi] = buf[lo:hi]


if __name__ == "__main__":
    for name, fn in (("quicksort", quicksort), ("merge_sort", merge_sort)):
        data = [5, 2, 9, 2, 7, 1, 8]
        print(f"{name}: {data} -> {fn(list(data))}")
