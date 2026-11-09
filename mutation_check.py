"""
Break the code on purpose and check that the tests notice.

Each "mutant" is a temporary copy of the source with ONE small deliberate bug
(a wrong comparison, an off-by-one, a counter that is never updated, a missing
guard ...). The unit tests are run against that copy. A good test suite fails
on every mutant. A mutant the tests miss ("SURVIVED") means either a gap in the
tests or a change that does not alter behaviour.

Nothing in the real source files is touched: the work happens in a temp folder.

Run:   python mutation_check.py          (a couple of minutes)
Output: printed, and saved to results/mutation_check.txt
"""

import os
import shutil
import subprocess
import sys
import tempfile

# (name, file, exact text to replace (must occur once), replacement)
MUTANTS = [
    # --- heapsort ----------------------------------------------------------
    ("heapsort skips its last pass", "heapsort.py",
     "for end in range(len(a) - 1, 0, -1):", "for end in range(len(a) - 2, 0, -1):"),
    ("build_max_heap skips the root", "heapsort.py",
     "for i in range(n // 2 - 1, -1, -1):\n        max_heapify(a, i, n)",
     "for i in range(n // 2 - 1, 0, -1):\n        max_heapify(a, i, n)"),
    ("max_heapify ignores heap_size for the left child", "heapsort.py",
     "if left < heap_size and a[left] > a[largest]:", "if left < len(a) and a[left] > a[largest]:"),
    ("max_heapify compares the right child the wrong way round", "heapsort.py",
     "if right < heap_size and a[right] > a[largest]:", "if right < heap_size and a[right] < a[largest]:"),
    # --- merge sort / quicksort used for comparison ------------------------
    ("merge sort is no longer stable", "other_sorts.py", "if a[j] < a[i]:", "if a[j] <= a[i]:"),
    ("quicksort recurses into the BIGGER side", "other_sorts.py",
     "if lt - lo < hi - gt:", "if lt - lo > hi - gt:"),
    ("comparison counter never counts <", "counting.py",
     "def __lt__(self, other):\n        global _count\n        _count += 1\n",
     "def __lt__(self, other):\n        global _count\n"),
    # --- priority queue ----------------------------------------------------
    ("sift-up stops in the wrong place (comparison reversed)", "priority_queue.py",
     "            if not outranks(task, heap[parent]):\n                break",
     "            if outranks(task, heap[parent]):\n                break"),
    ("sift-down always follows the left child", "priority_queue.py",
     "if child + 1 < n and outranks(heap[child + 1], heap[child]):", "if False:"),
    ("tie-break on deadline reversed", "priority_queue.py",
     "        return a.deadline < b.deadline", "        return a.deadline > b.deadline"),
    ("increase_key does not move the task", "priority_queue.py",
     "        task.priority = new_priority\n        self._sift_up(i)", "        task.priority = new_priority"),
    ("decrease_key does not move the task", "priority_queue.py",
     "        task.priority = new_priority\n        self._sift_down(i)", "        task.priority = new_priority"),
    ("duplicate task ids are accepted", "priority_queue.py",
     "        if task.task_id in self._pos:\n            raise ValueError(f\"task id",
     "        if False:\n            raise ValueError(f\"task id"),
    ("sift-up never counts its moves", "priority_queue.py",
     "            i = parent\n            self.moves += 1\n", "            i = parent\n"),
    ("sift-down never counts its moves", "priority_queue.py",
     "            i = child\n            self.moves += 1\n", "            i = child\n"),
    ("is_valid() always says True", "priority_queue.py",
     "        heap = self._heap\n        if len(self._pos) != len(heap):\n            return False",
     "        return True\n        heap = self._heap\n        if len(self._pos) != len(heap):\n            return False"),
    ("bulk build skips the last internal node", "priority_queue.py",
     "for i in range(len(self._heap) // 2 - 1, -1, -1):", "for i in range(len(self._heap) // 2 - 2, -1, -1):"),
    ("a different task object with a queued id is accepted", "priority_queue.py",
     "if i is None or self._heap[i] is not task:", "if i is None:"),
    ("increase_key accepts a lower priority", "priority_queue.py",
     "        if new_priority < task.priority:\n            raise ValueError(\"increase_key",
     "        if False:\n            raise ValueError(\"increase_key"),
    # --- scheduler ---------------------------------------------------------
    ("scheduler never preempts", "scheduler.py", "outranks(ready.peek(), running):", "False:"),
    ("aging also boosts tasks that just arrived", "scheduler.py",
     "if waiting_task.arrival_time < now:", "if True:"),
    ("first_start is overwritten on every resume", "scheduler.py",
     "first_start.setdefault(running.task_id, now)", "first_start[running.task_id] = now"),
    ("aging step is one too big", "scheduler.py",
     "waiting_task.priority + aging_step", "waiting_task.priority + aging_step + 1"),
    ("EDF runs the LATEST deadline first", "scheduler.py",
     '"edf": lambda t: -t.deadline,', '"edf": lambda t: t.deadline,'),
    ("waiting time includes the task's own burst", "scheduler.py",
     "waits.append(turn - t.burst_time)", "waits.append(turn)"),
    ("finishing exactly at the deadline counts as a miss", "scheduler.py",
     "if finish > t.deadline:", "if finish >= t.deadline:"),
    ("float times are accepted again (the old hang)", "scheduler.py",
     "if isinstance(value, bool) or not isinstance(value, Rational):", "if False:"),
    ("negative arrival times are accepted", "scheduler.py",
     "        if t.arrival_time < 0:", "        if False:"),
    ("queue-length area is never added up", "scheduler.py",
     "        queue_area += waiting * (next_time - now)\n", "        pass\n"),
    ("equal-priority preemptions are not counted", "scheduler.py",
     "                tie_preemptions += 1\n", "                pass\n"),
    ("aging ticks are not counted", "scheduler.py", "            aging_ticks += 1\n", "            pass\n"),
    ("aging updates are not counted", "scheduler.py",
     "                    aging_updates += 1\n", "                    pass\n"),
    ("independent slack mode is ignored", "scheduler.py",
     "            slack = slack_rng.randint(0, independent_max)", "            pass"),
]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    lines = [f"mutation check: {len(MUTANTS)} deliberate bugs, python {sys.version.split()[0]}"]
    survivors = []
    for name, filename, old, new in MUTANTS:
        with tempfile.TemporaryDirectory() as tmp:
            for f in os.listdir(here):
                if f.endswith(".py") and f != "mutation_check.py":
                    shutil.copy(os.path.join(here, f), tmp)
            path = os.path.join(tmp, filename)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            if text.count(old) != 1:
                lines.append(f"[?]        {name}: could not apply (the text to change appears {text.count(old)} times)")
                print(lines[-1], flush=True)
                continue
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(text.replace(old, new))
            try:
                result = subprocess.run([sys.executable, "-m", "unittest"], cwd=tmp,
                                        capture_output=True, text=True, timeout=240)
                caught = result.returncode != 0
                detail = [l for l in (result.stderr + result.stdout).strip().splitlines() if l.strip()][-1]
            except subprocess.TimeoutExpired:
                caught, detail = True, "timed out (an endless loop or a very slow run counts as caught)"
        lines.append(f"[{'caught' if caught else 'SURVIVED'}]  {name}   ({detail})")
        if not caught:
            survivors.append(name)
        print(lines[-1], flush=True)
    lines.append("")
    lines.append(f"{len(MUTANTS) - len(survivors)} of {len(MUTANTS)} caught." +
                 (f" Survivors: {survivors}" if survivors else ""))
    print(lines[-1])
    os.makedirs(os.path.join(here, "results"), exist_ok=True)
    with open(os.path.join(here, "results", "mutation_check.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
