from pathlib import Path

from pytest import fixture

from slp2mp4.artifact import Mp4Artifact, SlippiArtifact
from slp2mp4.config import CombineMode
from slp2mp4.context import ContextData
from slp2mp4.pipeline import Pipeline
from slp2mp4.task import ConcatVideosTask


@fixture
def complex_pipeline(tmp_path):
    def build():
        input_tasks = []
        input_by_task = {}
        artifacts = []
        phases = [
            {
                "startgg": {
                    "tournament": {"name": "Tournament A"},
                    "event": {"name": "Singles"},
                    "phase": {"name": "Upper"},
                    "set": {"ordinal": 0, "round": 0},
                },
            },
            {
                "startgg": {
                    "tournament": {"name": "Tournament A"},
                    "event": {"name": "Singles"},
                    "phase": {"name": "Lower"},
                    "set": {"ordinal": 0, "round": 0},
                },
            },
            {
                "startgg": {
                    "tournament": {"name": "Tournament A"},
                    "event": {"name": "Doubles"},
                    "phase": {"name": "Upper"},
                    "set": {"ordinal": 0, "round": 0},
                },
            },
            {
                "startgg": {
                    "tournament": {"name": "Tournament B"},
                    "event": {"name": "Doubles"},
                    "phase": {"name": "Upper"},
                    "set": {"ordinal": 0, "round": 0},
                },
            },
            {
                "startgg": {
                    "tournament": {"name": "Tournament B"},
                    "event": {"name": "Singles"},
                    "phase": {"name": "Lower"},
                    "set": {"ordinal": 0, "round": 0},
                },
            },
            {
                "startgg": {
                    "tournament": {"name": "Tournament B"},
                    "event": {"name": "Doubles"},
                    "phase": {"name": "Upper"},
                    "set": {"ordinal": 1, "round": 0},
                },
            },
            {
                "startgg": {
                    "tournament": {"name": "Tournament C"},
                    "event": {"name": "Doubles"},
                    "phase": {"name": "Lower"},
                    "set": {"ordinal": 1, "round": 0},
                },
            },
            {
                "startgg": {
                    "tournament": {"name": "Tournament C"},
                    "event": {"name": "Doubles"},
                    "phase": {"name": "Lower"},
                    "set": {"ordinal": 0, "round": 0},
                },
            },
            {
                "startgg": {
                    "tournament": {"name": "Tournament C"},
                    "event": {"name": "Doubles"},
                    "phase": {"name": "Lower"},
                    "set": {"ordinal": 2, "round": 0},
                },
            },
        ]
        for i, platform_data in enumerate(phases):
            context = ContextData(0, 0, (), None, None, **platform_data)
            output = Mp4Artifact(Path(f"{i} out.mp4"), frozenset({context}))
            artifacts.append(output)
            task = ConcatVideosTask(
                f"concat {i}",
                [Mp4Artifact(Path(f"{i}.mp4"))],
                [output],
                Path(f"{i} final.mp4"),
            )
            input_tasks.append(task)
            input_item = tmp_path / Path(f"input-{i // 3}.mp4")
            input_item.touch()
            input_by_task[task] = input_item
        return input_tasks, input_by_task, artifacts

    return build


def test_get_render_task(tmp_path):
    pipeline = Pipeline(tmp_path)
    slps = [tmp_path / "game.slp"]
    for slp in slps:
        slp.touch()
    slp = SlippiArtifact(slp)
    tasks = list(pipeline.get_render_task(slp))

    assert len(tasks) == 1
    task = tasks[0]
    assert task.name == "render game.slp"
    assert task.slp == slp
    assert task.inputs == [slp]
    assert task.final_name == Path("game.mp4")


def test_get_concat_tasks_single(tmp_path):
    pipeline = Pipeline(tmp_path)
    vids = [tmp_path / "game.mp4"]
    for vid in vids:
        vid.touch()
    artifacts = [Mp4Artifact(vid) for vid in vids]
    final_path = Path("used.mp4")
    tasks = list(pipeline.get_concat_task(artifacts, final_path))

    assert len(tasks) == 1
    task = tasks[0]
    assert task.name == "concat used.mp4"
    assert task.inputs == artifacts
    assert task.final_name == Path("used.mp4")


def test_get_concat_tasks_multiple(tmp_path):
    pipeline = Pipeline(tmp_path)
    prefixes = [f"g{i}" for i in range(3)]
    vids = [tmp_path / f"{prefix}.mp4" for prefix in prefixes]
    for vid in vids:
        vid.touch()
    artifacts = [Mp4Artifact(vid) for vid in vids]
    final_path = Path("used.mp4")
    tasks = list(pipeline.get_concat_task(artifacts, final_path))

    assert len(tasks) == 1
    task = tasks[0]
    assert task.name == "concat used.mp4"
    assert task.inputs == artifacts
    assert task.final_name == Path("used.mp4")


def test_get_group_concat_tasks_no_combine(tmp_path):
    pipeline = Pipeline(tmp_path)
    input_tasks = [
        ConcatVideosTask(
            f"concat {i}",
            [Mp4Artifact(Path(f"{i}.mp4"))],
            [Mp4Artifact(Path(f"{i} out.mp4"))],
            Path(f"{i} final.mp4"),
        )
        for i in range(3)
    ]
    tasks = list(pipeline.get_group_concat_tasks(input_tasks, {}, CombineMode.NONE))
    assert tasks == []


def test_get_group_concat_tasks_all_combine_simple(tmp_path):
    pipeline = Pipeline(tmp_path)
    outputs = []
    input_tasks = []
    input_by_task = {}
    for i in range(3):
        output = Mp4Artifact(Path(f"{i} out.mp4"))
        outputs.append(output)
        task = ConcatVideosTask(
            f"concat {i}",
            [Mp4Artifact(Path(f"{i}.mp4"))],
            [output],
            Path(f"{i} final.mp4"),
        )
        input_tasks.append(task)
        input_by_task[task] = None  # Unused

    tasks = list(
        pipeline.get_group_concat_tasks(input_tasks, input_by_task, CombineMode.ALL)
    )
    assert len(tasks) == 1
    assert len(tasks[0]) == 1

    task = tasks[0][0]
    assert task.name == "concat all.mp4"
    assert task.inputs == outputs
    assert task.final_name == Path("all.mp4")


def test_get_group_concat_tasks_all_combine_complex(tmp_path, complex_pipeline):
    pipeline = Pipeline(tmp_path)
    input_tasks, input_by_task, artifacts = complex_pipeline()
    tasks = list(
        pipeline.get_group_concat_tasks(input_tasks, input_by_task, CombineMode.ALL)
    )

    assert len(tasks) == 1

    assert len(tasks[0]) == 1
    task = tasks[0][0]
    assert task.name == "concat all.mp4"
    assert task.final_name == Path("all.mp4")
    assert len(task.inputs) == 9
    assert task.inputs == [
        artifacts[2],  # Tournament A - Doubles - Upper
        artifacts[1],  # Tournament A - Singles - Lower
        artifacts[0],  # Tournament A - Singles - Upper
        artifacts[3],  # Tournament B - Doubles - Upper
        artifacts[5],  # Tournament B - Doubles - Upper
        artifacts[4],  # Tournament B - Singles - Lower
        artifacts[7],  # Tournament C - Doubles - Lower
        artifacts[6],  # Tournament C - Doubles - Lower
        artifacts[8],  # Tournament C - Doubles - Lower
    ]


def test_get_group_concat_tasks_input_combine(tmp_path, complex_pipeline):
    pipeline = Pipeline(tmp_path)
    input_tasks, input_by_task, artifacts = complex_pipeline()
    tasks = list(
        pipeline.get_group_concat_tasks(
            input_tasks, input_by_task, CombineMode.BY_INPUT
        )
    )

    assert len(tasks) == 3

    assert len(tasks[0]) == 1
    task = tasks[0][0]
    assert task.name == "concat input-0.mp4"
    assert task.final_name == Path("input-0.mp4")
    assert len(task.inputs) == 3
    assert task.inputs == [
        artifacts[2],  # Tournament A - Doubles - Upper
        artifacts[1],  # Tournament A - Singles - Lower
        artifacts[0],  # Tournament A - Singles - Upper
    ]

    assert len(tasks[1]) == 1
    task = tasks[1][0]
    assert task.name == "concat input-1.mp4"
    assert task.final_name == Path("input-1.mp4")
    assert len(task.inputs) == 3
    assert task.inputs == [
        artifacts[3],  # Tournament B - Doubles - Upper
        artifacts[5],  # Tournament B - Doubles - Upper
        artifacts[4],  # Tournament B - Singles - Lower
    ]

    assert len(tasks[2]) == 1
    task = tasks[2][0]
    assert task.name == "concat input-2.mp4"
    assert task.final_name == Path("input-2.mp4")
    assert len(task.inputs) == 3
    assert task.inputs == [
        artifacts[7],  # Tournament C - Doubles - Lower
        artifacts[6],  # Tournament C - Doubles - Lower
        artifacts[8],  # Tournament C - Doubles - Lower
    ]


def test_get_group_concat_tasks_phase_combine(tmp_path, complex_pipeline):
    pipeline = Pipeline(tmp_path)
    input_tasks, input_by_task, artifacts = complex_pipeline()
    tasks = list(
        pipeline.get_group_concat_tasks(
            input_tasks, input_by_task, CombineMode.BY_PHASE
        )
    )

    assert len(tasks) == 6

    assert len(tasks[0]) == 1
    task = tasks[0][0]
    assert task.name == "concat Tournament A - Singles - Upper.mp4"
    assert task.final_name == Path("Tournament A - Singles - Upper.mp4")
    assert len(task.inputs) == 1
    assert task.inputs == [
        artifacts[0],  # Tournament A - Singles - Upper
    ]

    assert len(tasks[1]) == 1
    task = tasks[1][0]
    assert task.name == "concat Tournament A - Singles - Lower.mp4"
    assert task.final_name == Path("Tournament A - Singles - Lower.mp4")
    assert len(task.inputs) == 1
    assert task.inputs == [
        artifacts[1],  # Tournament A - Singles - Lower
    ]

    assert len(tasks[2]) == 1
    task = tasks[2][0]
    assert task.name == "concat Tournament A - Doubles - Upper.mp4"
    assert task.final_name == Path("Tournament A - Doubles - Upper.mp4")
    assert len(task.inputs) == 1
    assert task.inputs == [
        artifacts[2],  # Tournament A - Doubles - Upper
    ]

    assert len(tasks[3]) == 1
    task = tasks[3][0]
    assert task.name == "concat Tournament B - Doubles - Upper.mp4"
    assert task.final_name == Path("Tournament B - Doubles - Upper.mp4")
    assert len(task.inputs) == 2
    assert task.inputs == [
        artifacts[3],  # Tournament B - Doubles - Upper
        artifacts[5],  # Tournament B - Doubles - Upper
    ]

    assert len(tasks[4]) == 1
    task = tasks[4][0]
    assert task.name == "concat Tournament B - Singles - Lower.mp4"
    assert task.final_name == Path("Tournament B - Singles - Lower.mp4")
    assert len(task.inputs) == 1
    assert task.inputs == [
        artifacts[4],  # Tournament B - Singles - Lower
    ]

    assert len(tasks[5]) == 1
    task = tasks[5][0]
    assert task.name == "concat Tournament C - Doubles - Lower.mp4"
    assert task.final_name == Path("Tournament C - Doubles - Lower.mp4")
    assert len(task.inputs) == 3
    assert task.inputs == [
        artifacts[7],  # Tournament C - Doubles - Lower
        artifacts[6],  # Tournament C - Doubles - Lower
        artifacts[8],  # Tournament C - Doubles - Lower
    ]
