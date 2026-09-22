# Simple scheduler that ensures inputs run before outputs

import copy
import dataclasses
from collections import deque
from threading import Lock

from slp2mp4.artifact import ExistingFileArtifact
from slp2mp4.task import Task


@dataclasses.dataclass
class Scheduler:
    """Simple resource-aware FIFO scheduler. Uses DAG to put unblocked tasks in `ready_tasks`."""

    available_resources: dict[str, float]

    ready_tasks: deque[Task] = dataclasses.field(default_factory=deque)
    running_tasks: set[Task] = dataclasses.field(default_factory=set)
    completed_tasks: set[Task] = dataclasses.field(default_factory=set)

    waiting_on: dict[Task, set[Task]] = dataclasses.field(default_factory=dict)
    dependents: dict[Task, set[Task]] = dataclasses.field(default_factory=dict)

    lock: Lock = dataclasses.field(default_factory=Lock, init=False)
    full_resources: dict[str, float] = dataclasses.field(
        default_factory=dict, init=False
    )

    def __post_init__(self):
        self.full_resources = copy.deepcopy(self.available_resources)

    def submit(self, tasks: list[Task]):
        with self.lock:
            producer = {}
            for t in tasks:
                for resource in t.resources:
                    if resource not in self.available_resources:
                        raise RuntimeError(
                            f"Task '{t.name}' requires unknown resource '{resource}'."
                        )
                    if (req := t.resources[resource]) > (
                        avail := self.full_resources[resource]
                    ):
                        raise RuntimeError(
                            f"Task '{t.name}' will never satisfy '{resource}' requirement ({req} > {avail})."
                        )

                for output in t.outputs:
                    producer[output] = t
                self.waiting_on[t] = set()
                self.dependents[t] = set()

            for t in tasks:
                for i in t.inputs:
                    if isinstance(i, ExistingFileArtifact):
                        continue
                    upstream = producer.get(i)
                    if upstream is None:
                        raise RuntimeError(f"No producer found for artifact '{i}'.")
                    self.waiting_on[t].add(upstream)
                    self.dependents[upstream].add(t)

            for t, deps in self.waiting_on.items():
                if (len(deps) == 0) and (t not in self.ready_tasks):
                    self.ready_tasks.append(t)

    def get_work(self):
        with self.lock:
            blocked = deque()
            while self.ready_tasks:
                t = self.ready_tasks.popleft()
                if self._resources_available(t):
                    for name, value in t.resources.items():
                        self.available_resources[name] -= value
                    self.running_tasks.add(t)
                    self.ready_tasks.extend(blocked)
                    return t
                blocked.append(t)
            self.ready_tasks.extend(blocked)
            return None

    def finish(self, t: Task):
        with self.lock:
            if t not in self.running_tasks:
                raise RuntimeError(f"Task '{t.name}' was not running.")
            for name, value in t.resources.items():
                self.available_resources[name] += value
            for dependent in self.dependents[t]:
                self.waiting_on[dependent].remove(t)
                if len(self.waiting_on[dependent]) == 0:
                    self.ready_tasks.append(dependent)
            self.running_tasks.remove(t)
            self.completed_tasks.add(t)
            t.cleanup()

    def _resources_available(self, t: Task):
        for name, amount in t.resources.items():
            if self.available_resources[name] < amount:
                return False
        return True
