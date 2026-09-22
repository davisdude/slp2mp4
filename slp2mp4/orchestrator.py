# Takes collections and creates tasks / schedules them

import concurrent.futures
import dataclasses
import shutil
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from logging import Logger
from multiprocessing import Event
from pathlib import Path

import psutil

from slp2mp4 import log
from slp2mp4.artifact import Mp4Artifact
from slp2mp4.collector import Collection, Collector
from slp2mp4.config import Config
from slp2mp4.scheduler import Scheduler
from slp2mp4.task import ConcatVideosTask, RenderGameTask
from slp2mp4.worker import Worker


@dataclasses.dataclass
class Orchestrator:
    inputs: list[Path]
    conf: Config
    kill_event: Event = dataclasses.field(default_factory=Event)
    monitor: bool = dataclasses.field(default=False)
    dry_run: bool = dataclasses.field(default=False)
    num_procs: int | None = dataclasses.field(default=None)
    workdir: Path | None = dataclasses.field(default=None)
    collector: Collector | None = dataclasses.field(default=None)
    worker: Worker | None = dataclasses.field(default=None)
    scheduler: Scheduler | None = dataclasses.field(default=None)
    log: Logger | None = dataclasses.field(default=None)
    made_workdir: bool = dataclasses.field(default=False, init=False)

    def __post_init__(self):
        if self.num_procs is None:
            self.num_procs = self.conf.runtime.parallel
        if self.num_procs == 0:
            self.num_procs = psutil.cpu_count(logical=False) or 1
        if self.workdir is None:
            self.workdir = Path(tempfile.mkdtemp())
            self.made_workdir = True
        if self.collector is None:
            self.collector = Collector(
                self.inputs, self.kill_event, self.monitor, self.workdir
            )
        if self.worker is None:
            self.worker = Worker(self.conf, self.kill_event)
        if self.scheduler is None:
            self.scheduler = Scheduler({"cpu": self.num_procs})
        if self.log is None:
            self.log = log.get_logger()

    def format_output_name(self, path: Path):
        # TODO: pathvalidate
        # TODO: youtubify
        # TODO: Preserve directory structure
        return path

    def get_output_name(self, path: Path, _collection: Collection):
        # TODO: Rename using context.json
        if path.is_file():
            return self.format_output_name(path.with_suffix(".mp4"))
        if path != Path("."):
            parent = path.parent
        else:
            parent = Path("..")
            path = path.expanduser().absolute()
        return self.format_output_name(parent / (path.name + ".mp4"))

    def collect_tasks(self):
        for path, collection in self.collector.next():
            render_tasks = []
            tmp_artifacts = []
            for slp in collection.slps:
                _handle, tmp = tempfile.mkstemp(suffix=".mp4", dir=self.workdir)
                tmp_artifact = Mp4Artifact(Path(tmp))
                task = RenderGameTask(f"render {slp.path}", [slp], [tmp_artifact])
                tmp_artifacts.append(tmp_artifact)
                render_tasks.append(task)
            output_artifact = Mp4Artifact(self.get_output_name(path, collection))
            concat_task = ConcatVideosTask(
                f"concat {output_artifact.path}", tmp_artifacts, [output_artifact]
            )
            tasks = render_tasks + [concat_task]
            self.scheduler.submit(tasks)

            if self.dry_run:
                self.log.info(output_artifact.path)
                for slp in collection.slps:
                    self.log.info(f"\t{slp.path}")
                if collection.context:
                    self.log.info(f"\t{collection.context.path}")

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

        self.collector.cleanup()
        self.cleanup()

    def cleanup(self):
        if self.made_workdir:
            shutil.rmtree(self.workdir)
