"""
Heapsort.

MSCS-532 Assignment 4, Heapsort part.

The array is treated as a binary tree stored level by level. For the element at
index i (counting from 0):

    parent   (i - 1) // 2
    left     2 * i + 1
    right    2 * i + 2

A max-heap is an array where every element is >= its children, so the largest
element sits at index 0. Heapsort has two phases:

    1. build_max_heap: rearrange the array into a max-heap.
    2. Repeatedly swap the root (the current maximum) with the last element of
       the heap, shrink the heap by one, and repair the root with
       max_heapify. The maximums pile up at the end of the array in order.

Everything happens inside the original list, and max_heapify is a loop instead
of a recursive call, so extra memory is O(1) and there is no recursion limit
to worry about. The structure follows Chapter 6 of Cormen et al.,
Introduction to Algorithms.
"""


def max_heapify(a, i, heap_size):
    """Sink a[i] down until the subtree rooted at i is a max-heap again.

    Assumes the subtrees under i's two children are already max-heaps. Only
    a[0 .. heap_size - 1] counts as part of the heap, so anything after that
    (the already-sorted tail during heapsort) is left alone.
    """
    while True:
        left = 2 * i + 1
        right = left + 1
        largest = i
        if left < heap_size and a[left] > a[largest]:
            largest = left
        if right < heap_size and a[right] > a[largest]:
            largest = right
        if largest == i:
            return
        a[i], a[largest] = a[largest], a[i]
        i = largest


def build_max_heap(a):
    """Turn a list into a max-heap in place, in O(n) time.

    Elements from index len(a)//2 onward are leaves, so each one is already a
    one-element heap. Working backwards from the last non-leaf up to the root
    means every call to max_heapify sees two subtrees that are already heaps.
    """
    n = len(a)
    for i in range(n // 2 - 1, -1, -1):
        max_heapify(a, i, n)


def heapsort(a):
    """Sort a list in place into increasing order.

    Returns the same list so it can also be used inline.
    """
    build_max_heap(a)
    for end in range(len(a) - 1, 0, -1):
        a[0], a[end] = a[end], a[0]  # current maximum goes to its final spot
        max_heapify(a, 0, end)  # heap is now a[0 .. end - 1]
    return a


def main():
    samples = [
        [5, 2, 4, 6, 1, 3],
        [],
        [42],
        [9, 9, 1, 9, 2],
        [1, 2, 3, 4, 5],
        [5, 4, 3, 2, 1],
        [-3, 7, 0, -8, 4],
    ]
    for data in samples:
        original = list(data)
        result = heapsort(data)
        print(f"{original}  ->  {result}")
        assert result == sorted(original), "wrong result"
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
