"""
Task and a binary max-heap priority queue.

MSCS-532 Assignment 4, Priority Queue part.

Data structure choice: the heap lives in a plain Python list. A binary heap is
a complete tree, so it packs into an array with no gaps and the family of any
node is plain arithmetic:

    parent   (i - 1) // 2        left child   2 * i + 1        right child   2 * i + 2

That gives O(1) access to any node and no pointers to maintain. Appending at the
end (for insert) and removing from the end (for extract) are cheap on a list.

Max-heap versus min-heap: this is a max-heap because the scheduler in
scheduler.py runs the task with the HIGHEST priority number first. (Scheduling
by earliest deadline is done with the same max-heap by using the negative of
the deadline as the priority.)

One extra dictionary, _pos, remembers where every task currently sits in the
list. Without it, increase_key and decrease_key would first have to search the
whole heap for the task (O(n)). With it the lookup is O(1) and the operation
costs one trip up or down the tree, O(log n).

Ordering rule: higher priority first. Ties go to the earlier deadline, then
the earlier arrival, then the smaller task id, so the order is always fully
determined.
"""

import math


class Task:
    """One unit of work for the scheduler.

    task_id        unique id (an int is typical)
    priority       bigger number = more important
    arrival_time   when the task becomes ready to run
    deadline       when it should be finished (math.inf means no deadline)
    burst_time     how much CPU time it needs in total
    remaining_time CPU time still owed; starts equal to burst_time
    """

    __slots__ = ("task_id", "priority", "arrival_time", "deadline", "burst_time", "remaining_time")

    def __init__(self, task_id, priority, arrival_time=0, deadline=math.inf, burst_time=1):
        if burst_time <= 0:
            raise ValueError("burst_time must be positive")
        self.task_id = task_id
        self.priority = priority
        self.arrival_time = arrival_time
        self.deadline = deadline
        self.burst_time = burst_time
        self.remaining_time = burst_time

    def __repr__(self):
        return (f"Task(id={self.task_id}, priority={self.priority}, arrival={self.arrival_time}, "
                f"deadline={self.deadline}, burst={self.burst_time})")


def outranks(a, b):
    """True if task a should be served before task b."""
    if a.priority != b.priority:
        return a.priority > b.priority
    if a.deadline != b.deadline:
        return a.deadline < b.deadline
    if a.arrival_time != b.arrival_time:
        return a.arrival_time < b.arrival_time
    return a.task_id < b.task_id


class PriorityQueue:
    """Binary max-heap of Task objects.

    Operation costs, n = number of tasks in the queue:

        insert(task)               O(log n)   (O(1) on average for random priorities)
        extract_max()              O(log n)
        peek()                     O(1)
        increase_key / decrease_key / change_priority   O(log n)
        is_empty(), len()          O(1)
        PriorityQueue(list_of_tasks)  O(n)    (bottom-up build, same idea as build_max_heap)

    `moves` counts how many levels tasks have been shifted up or down in total,
    which the benchmarks use to check the O(log n) claims.

    Two things to know:

    - Change a queued task's priority ONLY through increase_key, decrease_key
      or change_priority. Assigning task.priority directly leaves the heap out
      of order without telling the queue; is_valid() will report it.
    - Whatever gets compared (task ids, priorities, deadlines, arrival times)
      must be comparable with each other, for example all ints. insert is not
      atomic: if a comparison raises (say, ids of mixed types with otherwise
      equal ranking) the task has already been added.
    """

    def __init__(self, tasks=None):
        self._heap = []
        self._pos = {}  # task_id -> index in self._heap
        self.moves = 0
        if tasks:
            for task in tasks:
                if task.task_id in self._pos:
                    raise ValueError(f"duplicate task id {task.task_id!r}")
                self._pos[task.task_id] = len(self._heap)
                self._heap.append(task)
            for i in range(len(self._heap) // 2 - 1, -1, -1):
                self._sift_down(i)

    # ---- the required operations ---------------------------------------

    def insert(self, task):
        """Add a task. Appends it at the bottom, then lets it rise to its place."""
        if task.task_id in self._pos:
            raise ValueError(f"task id {task.task_id!r} is already in the queue")
        self._heap.append(task)
        self._pos[task.task_id] = len(self._heap) - 1
        self._sift_up(len(self._heap) - 1)

    def extract_max(self):
        """Remove and return the task that outranks all others.

        Moves the last task into the root's place, then sinks it back down.
        Raises IndexError if the queue is empty.
        """
        if not self._heap:
            raise IndexError("extract_max from an empty priority queue")
        top = self._heap[0]
        last = self._heap.pop()
        del self._pos[top.task_id]
        if self._heap:
            self._heap[0] = last
            self._pos[last.task_id] = 0
            self._sift_down(0)
        return top

    def peek(self):
        """Return the top task without removing it. Raises IndexError if empty."""
        if not self._heap:
            raise IndexError("peek at an empty priority queue")
        return self._heap[0]

    def increase_key(self, task, new_priority):
        """Raise a queued task's priority and move it up as far as it needs to go."""
        i = self._index_of(task)
        if new_priority < task.priority:
            raise ValueError("increase_key needs a priority at least as high as the current one")
        task.priority = new_priority
        self._sift_up(i)

    def decrease_key(self, task, new_priority):
        """Lower a queued task's priority and move it down as far as it needs to go."""
        i = self._index_of(task)
        if new_priority > task.priority:
            raise ValueError("decrease_key needs a priority at most as high as the current one")
        task.priority = new_priority
        self._sift_down(i)

    def change_priority(self, task, new_priority):
        """Set a queued task's priority to any value, moving it whichever way is needed."""
        if new_priority >= task.priority:
            self.increase_key(task, new_priority)
        else:
            self.decrease_key(task, new_priority)

    def is_empty(self):
        return not self._heap

    # ---- small helpers ---------------------------------------------------

    def __len__(self):
        return len(self._heap)

    def __contains__(self, task_id):
        return task_id in self._pos

    def tasks(self):
        """A snapshot list of every queued task, in heap order (not sorted)."""
        return list(self._heap)

    def is_valid(self):
        """Check the heap property and the position index. For tests and debugging."""
        heap = self._heap
        if len(self._pos) != len(heap):
            return False
        for i, task in enumerate(heap):
            if self._pos.get(task.task_id) != i:
                return False
            if i > 0 and outranks(task, heap[(i - 1) // 2]):
                return False
        return True

    def _index_of(self, task):
        i = self._pos.get(task.task_id)
        if i is None or self._heap[i] is not task:
            raise KeyError(task.task_id)
        return i

    def _sift_up(self, i):
        heap, pos = self._heap, self._pos
        task = heap[i]
        while i > 0:
            parent = (i - 1) // 2
            if not outranks(task, heap[parent]):
                break
            heap[i] = heap[parent]  # pull the parent down into the hole
            pos[heap[i].task_id] = i
            i = parent
            self.moves += 1
        heap[i] = task
        pos[task.task_id] = i

    def _sift_down(self, i):
        heap, pos = self._heap, self._pos
        n = len(heap)
        task = heap[i]
        while True:
            child = 2 * i + 1
            if child >= n:
                break
            if child + 1 < n and outranks(heap[child + 1], heap[child]):
                child += 1  # pick the stronger of the two children
            if not outranks(heap[child], task):
                break
            heap[i] = heap[child]  # pull the child up into the hole
            pos[heap[i].task_id] = i
            i = child
            self.moves += 1
        heap[i] = task
        pos[task.task_id] = i
