# Takes collections and creates tasks / schedules them

import concurrent.futures
import dataclasses
import json
import math
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from logging import Logger
from multiprocessing import Event
from pathlib import Path

import pathvalidate
import psutil

from slp2mp4 import log, util
from slp2mp4.artifact import Artifact, ContextArtifact, Mp4Artifact, SlippiArtifact
from slp2mp4.collector import Collector
from slp2mp4.config import Config
from slp2mp4.pipeline import Pipeline
from slp2mp4.scheduler import Scheduler
from slp2mp4.task import MoveFileTask, Task
from slp2mp4.worker import Worker


@dataclasses.dataclass
class Orchestrator:
    conf: Config
    kill_event: Event
    collector: Collector

    dry_run: bool = dataclasses.field(default=False)
    num_procs: int | None = dataclasses.field(default=None)
    output_directory: Path | None = dataclasses.field(default=None)
    workdir: Path | None = dataclasses.field(default=None)

    worker: Worker | None = dataclasses.field(default=None, init=False)
    scheduler: Scheduler | None = dataclasses.field(default=None, init=False)
    pipeline: Pipeline | None = dataclasses.field(default=None, init=False)
    log: Logger | None = dataclasses.field(default=None, init=False)

    def __post_init__(self):
        if self.num_procs is None:
            self.num_procs = self.conf.runtime.parallel
        if self.num_procs == 0:
            self.num_procs = psutil.cpu_count(logical=False) or 1

        self.worker = Worker(self.conf, self.kill_event)
        self.scheduler = Scheduler({"cpu": self.num_procs})
        self.pipeline = Pipeline(self.workdir, self.output_directory)
        self.log = log.get_logger()

    def get_slps(self, artifact: Artifact):
        task = self.scheduler.get_producer(artifact)
        for _, leaf in self.scheduler.walk_tree(task):
            if isinstance(leaf, SlippiArtifact):
                yield leaf

    def get_contexts(self, task: Task):
        slps = self.get_slps(task.video)
        return list({slp.context for slp in slps})

    def get_round_info(self, task: Task):
        default_round_info = ("", "", "", -math.inf)
        contexts = self.get_contexts(task)
        if (len(contexts) != 1) or (contexts[0] is None):
            return default_round_info
        context = contexts[0]
        with open(context.path, "rb") as f:
            try:
                # TODO: parry / challonge / etc.
                data = json.load(f)
                tournament_name = data["startgg"]["tournament"]["name"]
                event_name = data["startgg"]["event"]["name"]
                phase_name = data["startgg"]["phase"]["name"]
                set_order = (
                    data["startgg"]["set"]["ordinal"] or data["startgg"]["set"]["round"]
                )
                return (tournament_name, event_name, phase_name, set_order)
            except Exception as e:  # noqa: BLE001
                self.log.error(f"Encountered error getting round info: {e}")
        return default_round_info

    def print_leaf(self, task: Task):
        indent = "    "
        for indent_level, leaf in self.scheduler.walk_tree(task):
            if isinstance(leaf, Task):
                pad = indent_level * indent
                self.log.info(f"{pad}{leaf.final_name} ({leaf.short_name})")
            elif isinstance(leaf, Artifact):
                pad = (indent_level + 1) * indent
                self.log.info(f"{pad}{leaf}")
                if context := getattr(leaf, "context", None):
                    self.log.info(f"{pad}{context} ({leaf.index + 1})")

    def write_timestamps(self, main_task):
        filename = main_task.video.path.with_suffix(".txt")
        for _, leaf in self.scheduler.walk_tree(main_task):
            if hasattr(leaf, "timestamps") and not self.dry_run:
                if leaf.timestamps:
                    with open(filename, "w") as f:
                        names = [
                            self.scheduler.get_producer(i).final_name.stem
                            for i in leaf.inputs
                        ]
                        times = [timedelta(seconds=int(t)) for t in leaf.timestamps]
                        f.writelines(f"{t} - {n}\n" for n, t in zip(names, times))
                break

    def get_move_tasks(self, tasks: list[Task]):
        for task in tasks:
            parents = task.final_name.parents
            name = task.final_name.stem
            if self.conf.runtime.youtubify_names:
                name = util.translate(name, self.conf.runtime.name_replacements)
            output_directory = self.output_directory
            if self.conf.runtime.preserve_directory_structure:
                for parent in parents:
                    output_directory /= parent
            name = pathvalidate.sanitize_filename(name, max_len=251)  # 255 - .mp4
            output_path = output_directory / f"{name}.mp4"
            output_artifact = Mp4Artifact(output_path)
            yield [
                MoveFileTask(
                    f"move {output_path}", [task.video], [output_artifact], output_path
                )
            ]

    def get_final_name(self, context: ContextArtifact):
        if not self.conf.runtime.use_context_json_for_naming:
            return None
        with open(context.path, "rb") as f:
            try:
                # TODO: parry / challonge / etc.
                data = json.load(f)
                separator = (
                    " / "
                    if (
                        self.conf.runtime.youtubify_names
                        and ("/" in self.conf.runtime.name_replacements)
                    )
                    else " + "
                )
                player1 = separator.join(data["scores"][0]["slots"][0]["displayNames"])
                player2 = separator.join(data["scores"][0]["slots"][1]["displayNames"])
                tournament_name = data["startgg"]["tournament"]["name"]
                event_name = data["startgg"]["event"]["name"]
                phase_name = data["startgg"]["phase"]["name"]
                round_text = data["startgg"]["set"]["fullRoundText"]
                name = f"{player1} vs {player2} - {tournament_name} - {event_name} - {phase_name} - {round_text}.mp4"
                return Path(name)
            except Exception as e:  # noqa: BLE001
                self.log.error(f"Encountered error getting round info: {e}")
        return None

    def next(self):
        """Iterator that returns <task>."""
        input_by_task: dict[Task, Path] = {}
        for input_item, final, artifacts in self.collector.next():
            contexts = list({artifact.context for artifact in artifacts})
            if (len(contexts) == 1) and ((context := contexts[0]) is not None):
                final = self.get_final_name(context) or final
            for task in self.pipeline.get_render_tasks(artifacts, final):
                input_by_task[task] = input_item
                yield [task]
        leaves = self.scheduler.get_leaves()
        phase_by_task = {task: self.get_round_info(task) for task in leaves}
        yield from self.pipeline.get_concat_tasks(
            leaves, input_by_task, phase_by_task, self.conf.runtime.combine_mode
        )
        leaves = self.scheduler.get_leaves()
        yield from self.get_move_tasks(leaves)

    def collect_tasks(self):
        for tasks in self.next():
            self.scheduler.submit(tasks)

        leaves = self.scheduler.get_leaves()
        if self.dry_run:
            for leaf in leaves:
                self.print_leaf(leaf)

    def do_work(self):
        while not self.kill_event.is_set():
            task = self.scheduler.get_work()
            if task is not None:
                try:
                    if not self.dry_run:
                        self.worker.submit(task)
                finally:
                    self.scheduler.finish(task)
            else:
                if self.collector.done:
                    break
                time.sleep(1)

    def run(self):
        # 1 do_work per num_proc, + 1 for collect_tasks
        with ThreadPoolExecutor(self.num_procs + 1) as executor:
            futures = [executor.submit(self.collect_tasks)]
            for _ in range(self.num_procs):
                futures.append(executor.submit(self.do_work))
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception:  # noqa: BLE001
                    self.log.error(
                        f"Orchestrator encountered exception: {traceback.format_exc()}"
                    )

        # Timestamps must be written after concat is done
        leaves = self.scheduler.get_leaves()
        for task in leaves:
            self.write_timestamps(task)

        self.collector.cleanup()
        self.pipeline.cleanup()
