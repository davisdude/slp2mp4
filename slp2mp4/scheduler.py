# Simple scheduler that ensures inputs run before outputs

import copy
import dataclasses
from collections import deque
from threading import RLock

from slp2mp4.artifact import Artifact, ExistingFileArtifact
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
    producers: dict[Artifact, Task] = dataclasses.field(default_factory=dict)

    lock: RLock = dataclasses.field(default_factory=RLock, init=False)
    full_resources: dict[str, float] = dataclasses.field(
        default_factory=dict, init=False
    )

    def __post_init__(self):
        self.full_resources = copy.deepcopy(self.available_resources)

    def submit(self, tasks: list[Task]):
        with self.lock:
            for task in tasks:
                for resource in task.resources:
                    if resource not in self.available_resources:
                        raise RuntimeError(
                            f"Task '{task.name}' requires unknown resource '{resource}'."
                        )
                    requested = task.resources[resource]
                    available = self.full_resources[resource]
                    if requested > available:
                        raise RuntimeError(
                            f"Task '{task.name}' will never satisfy '{resource}' requirement ({requested} > {available})."
                        )

                for output in task.outputs:
                    self.producers[output] = task
                self.waiting_on[task] = set()
                self.dependents[task] = set()

            for task in tasks:
                for i in task.inputs:
                    if isinstance(i, ExistingFileArtifact):
                        continue
                    upstream = self.producers.get(i)
                    if upstream is None:
                        raise RuntimeError(f"No producer found for artifact '{i}'.")
                    self.waiting_on[task].add(upstream)
                    self.dependents[upstream].add(task)

            for task, deps in self.waiting_on.items():
                if (
                    (len(deps) == 0)
                    and (task not in self.ready_tasks)
                    and (task not in self.running_tasks)
                    and (task not in self.completed_tasks)
                ):
                    self.ready_tasks.append(task)

    def get_work(self):
        with self.lock:
            blocked = deque()
            while self.ready_tasks:
                task = self.ready_tasks.popleft()
                if self._resources_available(task):
                    for name, value in task.resources.items():
                        self.available_resources[name] -= value
                    self.running_tasks.add(task)
                    self.ready_tasks.extendleft(blocked)
                    return task
                blocked.append(task)
            self.ready_tasks.extend(blocked)
            return None

    def finish(self, task: Task):
        with self.lock:
            if task not in self.running_tasks:
                raise RuntimeError(f"Task '{task.name}' was not running.")
            for name, value in task.resources.items():
                self.available_resources[name] += value
            for dependent in self.dependents[task]:
                self.waiting_on[dependent].remove(task)
                # Prioritize tasks hogging temp file space
                if len(self.waiting_on[dependent]) == 0:
                    self.ready_tasks.appendleft(dependent)
            self.running_tasks.remove(task)
            self.completed_tasks.add(task)
            task.cleanup()

    def get_leaves(self):
        with self.lock:
            return [
                task
                for task, dependents in self.dependents.items()
                if len(dependents) == 0
            ]

    def get_producer(self, artifact: Artifact):
        with self.lock:
            return self.producers.get(artifact)

    def get_parent_tasks(self, task: Task):
        with self.lock:
            yield task
            tasks = [task]
            while tasks:
                task = tasks.pop()
                for i in task.inputs:
                    producer = self.get_producer(i)
                    if producer is not None:
                        tasks.append(producer)
                        yield producer

    def _resources_available(self, task: Task):
        for name, amount in task.resources.items():
            if self.available_resources[name] < amount:
                return False
        return True
