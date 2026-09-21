import subprocess
from dataclasses import dataclass
from pathlib import Path

from slp2mp4 import artifact, task, scheduler
from pytest import fixture


@fixture
def make_file(tmp_path: Path):
    def build(name: str, create: bool = False, cls=artifact.Artifact):
        path = tmp_path / name
        if create:
            path.touch()
        return cls(Path(path))

    return build


@dataclass
class Pipeline:
    sched: scheduler.Scheduler
    render_tasks: dict[str, list[task.RenderGameTask]]
    concat_tasks: dict[str, task.ConcatVideosTask]


@fixture
def make_pipeline(make_file):
    def build(
        sets: list[tuple[str, list[str]]],
        cpus: float = 1.0,
        create_mp4s: bool = False,
        create_slps: bool = True,
    ):
        render_tasks = {}
        concat_tasks = {}
        tasks = []
        for name, set_paths in sets:
            mp4_artifacts = []
            mp4_tasks = []
            for set_path in set_paths:
                slp_artifact = make_file(
                    f"{set_path}.slp", create=create_slps, cls=artifact.SlippiArtifact
                )
                mp4_artifact = make_file(
                    f"{set_path}.mp4", create=create_mp4s, cls=artifact.Mp4Artifact
                )
                mp4_artifacts.append(mp4_artifact)
                render_task = task.RenderGameTask(
                    f"render_{set_path}", [slp_artifact], [mp4_artifact]
                )
                mp4_tasks.append(render_task)
            set_artifact = make_file(
                f"{name}.mp4", create=create_mp4s, cls=artifact.Mp4Artifact
            )
            concat_task = task.ConcatVideosTask(
                f"concat_{name}", mp4_artifacts, [set_artifact]
            )
            render_tasks[name] = mp4_tasks
            concat_tasks[name] = concat_task
            tasks.extend([*mp4_tasks, concat_task])

        sched = scheduler.Scheduler({"cpu": cpus})
        sched.submit(tasks)
        return Pipeline(sched, render_tasks, concat_tasks)

    return build


def _get_duration(path: Path):
    result = subprocess.run(
        [
            "ffprobe",
            "-i",
            str(path),
            "-show_entries",
            "format=duration",
            "-v",
            "quiet",
            "-of",
            "csv=p=0",
        ],
        check=True,
        capture_output=True,
    )
    return float(result.stdout)


@fixture
def get_duration():
    return _get_duration


@fixture
def check_duration():
    def func(path: Path, expected: float, tolerance: float):
        duration = _get_duration(path)
        assert abs(duration - expected) <= tolerance

    return func
