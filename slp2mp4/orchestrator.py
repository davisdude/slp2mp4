# Takes collections and creates tasks / schedules them

import dataclasses
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Event
from pathlib import Path

import psutil

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
    workdir: Path | None = dataclasses.field(default=None)
    collector: Collector | None = dataclasses.field(default=None)
    worker: Worker | None = dataclasses.field(default=None)
    scheduler: Scheduler | None = dataclasses.field(default=None)
    num_procs: int | None = dataclasses.field(default=None)

    def __post_init__(self):
        if self.workdir is None:
            self.workdir = Path(tempfile.mkdtemp())
        if self.collector is None:
            self.collector = Collector(
                self.inputs, self.kill_event, self.monitor, self.workdir
            )
        if self.worker is None:
            self.worker = Worker(self.conf, self.kill_event)
        if self.scheduler is None:
            if (num_procs := self.conf.runtime.parallel) == 0:
                num_procs = psutil.cpu_count(logical=False) or 1
            self.num_procs = num_procs
            self.scheduler = Scheduler({"cpu": num_procs})

    def format_output_name(self, path: Path):
        # TODO: pathvalidate
        # TODO: youtubify
        # TODO: Preserve directory structure
        return path

    def get_output_name(self, path: Path, _collection: Collection):
        # TODO: Rename using context.json
        if path.is_file():
            return self.format_output_name(path.with_suffix(".mp4"))
        parent = path.parent
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

    def do_work(self):
        while not self.kill_event.is_set():
            task = self.scheduler.get_work()
            if task is not None:
                try:
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
            executor.submit(self.collect_tasks)
            for _ in range(self.num_procs):
                executor.submit(self.do_work)
