import dataclasses
import pathlib

from slp2mp4 import artifact, task, scheduler
import pytest

@pytest.fixture
def make_file(tmp_path: pathlib.Path):
    def build(name: str, create: bool = False, cls=artifact.Artifact):
        path = tmp_path / name
        if create:
            path.touch()
        return cls(pathlib.Path(path))
    return build

@dataclasses.dataclass
class Pipeline:
    sched: scheduler.Scheduler
    render_tasks: dict[str, list[task.RenderGameTask]]
    concat_tasks: dict[str, task.ConcatVideosTask]

@pytest.fixture
def make_pipeline(make_file):
    def build(sets: list[tuple[str, list[str]]], cpus: float = 1.0, create_mp4s: bool = False, create_slps: bool = True):
        render_tasks = {}
        concat_tasks = {}
        tasks = []
        for name, set_paths in sets:
            mp4_artifacts = []
            mp4_tasks = []
            for set_path in set_paths:
                slp_artifact = make_file(f"{set_path}.slp", create=create_slps, cls=artifact.SlippiArtifact)
                mp4_artifact = make_file(f"{set_path}.mp4", create=create_mp4s, cls=artifact.Mp4Artifact)
                mp4_artifacts.append(mp4_artifact)
                render_task = task.RenderGameTask(f"render_{set_path}", [slp_artifact], [mp4_artifact])
                mp4_tasks.append(render_task)
            set_artifact = make_file(f"{name}.mp4", create=create_mp4s, cls=artifact.Mp4Artifact)
            concat_task = task.ConcatVideosTask(f"concat_{name}", mp4_artifacts, [set_artifact])
            render_tasks[name] = mp4_tasks
            concat_tasks[name] = concat_task
            tasks.extend([*mp4_tasks, concat_task])

        sched = scheduler.Scheduler({"cpu": cpus})
        sched.submit(tasks)
        return Pipeline(sched, render_tasks, concat_tasks)
    return build
