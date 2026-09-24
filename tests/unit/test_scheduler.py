import dataclasses
from pathlib import Path

import pytest

from slp2mp4.artifact import Artifact, Mp4Artifact, SlippiArtifact
from slp2mp4.scheduler import Scheduler
from slp2mp4.task import ConcatVideosTask, RenderGameTask, Task


@dataclasses.dataclass
class MagicTask(Task):
    magic_limit: float = dataclasses.field(default=1.0)

    @property
    def resources(self):
        return {"magic": self.magic_limit}


@dataclasses.dataclass
class Pipeline:
    sched: Scheduler
    render_tasks: dict[str, list[RenderGameTask]]
    concat_tasks: dict[str, ConcatVideosTask]


@pytest.fixture
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
                    f"{set_path}.slp", create=create_slps, cls=SlippiArtifact
                )
                mp4_artifact = make_file(
                    f"{set_path}.mp4", create=create_mp4s, cls=Mp4Artifact
                )
                mp4_artifacts.append(mp4_artifact)
                render_task = RenderGameTask(
                    f"render_{set_path}", [slp_artifact], [mp4_artifact]
                )
                mp4_tasks.append(render_task)
            set_artifact = make_file(f"{name}.mp4", create=create_mp4s, cls=Mp4Artifact)
            concat_task = ConcatVideosTask(
                f"concat_{name}", mp4_artifacts, [set_artifact]
            )
            render_tasks[name] = mp4_tasks
            concat_tasks[name] = concat_task
            tasks.extend([*mp4_tasks, concat_task])

        sched = Scheduler({"cpu": cpus})
        sched.submit(tasks)
        return Pipeline(sched, render_tasks, concat_tasks)

    return build


def test_graph_construction(make_pipeline):
    pipeline = make_pipeline(
        [
            ("set1", ["game1", "game2", "game3"]),
            ("set2", ["game4"]),
        ]
    )
    render1 = pipeline.render_tasks["set1"][0]
    render2 = pipeline.render_tasks["set1"][1]
    render3 = pipeline.render_tasks["set1"][2]
    render4 = pipeline.render_tasks["set2"][0]
    concat1 = pipeline.concat_tasks["set1"]
    concat2 = pipeline.concat_tasks["set2"]

    assert pipeline.sched.waiting_on[concat1] == {render1, render2, render3}
    assert pipeline.sched.waiting_on[concat2] == {render4}
    assert pipeline.sched.waiting_on[render1] == set()
    assert pipeline.sched.waiting_on[render2] == set()
    assert pipeline.sched.waiting_on[render3] == set()
    assert pipeline.sched.waiting_on[render4] == set()

    assert pipeline.sched.dependents[render1] == {concat1}
    assert pipeline.sched.dependents[render2] == {concat1}
    assert pipeline.sched.dependents[render3] == {concat1}
    assert pipeline.sched.dependents[render4] == {concat2}
    assert pipeline.sched.dependents[concat1] == set()
    assert pipeline.sched.dependents[concat2] == set()


def test_missing_producer():
    game1_mp4 = Mp4Artifact(Path("game1.mp4"))
    set_mp4 = Mp4Artifact(Path("set.mp4"))
    concat = ConcatVideosTask("concat", [game1_mp4], [set_mp4])
    sched = Scheduler({"cpu": 1})
    with pytest.raises(
        RuntimeError, match=r"^No producer found for artifact 'game1.mp4'\.$"
    ):
        sched.submit([concat])


def test_invalid_resource():
    file = Artifact(Path("file.txt"))
    out = Artifact(Path("out.txt"))
    some_task = MagicTask("foo", [file], [out])
    sched = Scheduler({"cpu": 1})
    with pytest.raises(
        RuntimeError, match=r"^Task 'foo' requires unknown resource 'magic'\.$"
    ):
        sched.submit([some_task])


def test_impossible_resource():
    file = Artifact(Path("file.txt"))
    out = Artifact(Path("out.txt"))
    some_task = MagicTask("foo", [file], [out])
    some_task.magic_limit = 10
    sched = Scheduler({"magic": 1})
    with pytest.raises(
        RuntimeError,
        match=r"^Task 'foo' will never satisfy 'magic' requirement \(10 > 1\)\.$",
    ):
        sched.submit([some_task])


def test_invalid_finish(make_pipeline):
    pipeline = make_pipeline([("set", ["game1", "game2", "game3"])])
    with pytest.raises(RuntimeError, match=r"^Task 'render_game1' was not running\.$"):
        pipeline.sched.finish(pipeline.render_tasks["set"][0])


def test_double_finish(make_pipeline):
    pipeline = make_pipeline([("set", ["game1"])])
    work = pipeline.sched.get_work()
    pipeline.sched.finish(work)
    with pytest.raises(RuntimeError, match=r"^Task 'render_game1' was not running\.$"):
        pipeline.sched.finish(work)


def test_dependencies_and_resources(make_pipeline):
    pipeline = make_pipeline([("set", ["game1", "game2", "game3"])])
    completed = set()

    for _ in range(3):
        work = pipeline.sched.get_work()
        assert work in pipeline.render_tasks["set"]
        assert work not in completed
        assert pipeline.sched.get_work() is None
        pipeline.sched.finish(work)
        completed.add(work)

    assert completed == set(pipeline.render_tasks["set"])

    work = pipeline.sched.get_work()
    assert work == pipeline.concat_tasks["set"]


def test_two_cpus(make_pipeline):
    pipeline = make_pipeline([("set", ["game1", "game2", "game3"])], cpus=2.0)
    completed = set()

    t1 = pipeline.sched.get_work()
    t2 = pipeline.sched.get_work()
    t3 = pipeline.sched.get_work()

    assert t1 in pipeline.render_tasks["set"]
    assert t2 in pipeline.render_tasks["set"]
    assert t1 != t2
    assert t3 is None

    pipeline.sched.finish(t1)
    completed.add(t1)

    t4 = pipeline.sched.get_work()
    t5 = pipeline.sched.get_work()

    assert t4 in pipeline.render_tasks["set"]
    assert t4 not in completed
    assert t5 is None

    pipeline.sched.finish(t2)
    completed.add(t2)
    pipeline.sched.finish(t4)
    completed.add(t4)

    t6 = pipeline.sched.get_work()

    assert t6 == pipeline.concat_tasks["set"]
    assert t6 not in completed


def test_all_tasks_execute_once(make_pipeline):
    pipeline = make_pipeline(
        [
            ("set1", ["game1", "game2", "game3"]),
            ("set2", ["game4"]),
        ],
        cpus=2.0,
    )
    completed = set()
    expected = (
        set(pipeline.render_tasks["set1"])
        | set(pipeline.render_tasks["set2"])
        | set(pipeline.concat_tasks.values())
    )

    while True:
        work = pipeline.sched.get_work()
        if work is None:
            break
        assert work not in completed
        for i in work.inputs:
            i.path.touch(exist_ok=True)
        pipeline.sched.finish(work)
        completed.add(work)

    assert completed == expected
