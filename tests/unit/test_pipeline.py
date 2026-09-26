from pathlib import Path

from pytest import fixture

from slp2mp4.artifact import Mp4Artifact, SlippiArtifact
from slp2mp4.config import CombineMode
from slp2mp4.pipeline import Pipeline
from slp2mp4.task import ConcatVideosTask


@fixture
def complex_pipeline(tmp_path):
    def build():
        input_tasks = []
        input_by_task = {}
        phase_by_task = {}
        phases = [
            ("Tournament A", "Singles", "Winners", 0),
            ("Tournament A", "Singles", "Losers", 0),
            ("Tournament A", "Doubles", "Winners", 0),
            ("Tournament B", "Doubles", "Winners", 0),
            ("Tournament B", "Singles", "Losers", 0),
            ("Tournament B", "Doubles", "Winners", 1),
            ("Tournament C", "Doubles", "Losers", 1),
            ("Tournament C", "Doubles", "Losers", 0),
            ("Tournament C", "Doubles", "Losers", 2),
        ]
        for i, phase in enumerate(phases):
            output = Mp4Artifact(Path(f"{i} out.mp4"))
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
            phase_by_task[task] = phase
        return input_tasks, input_by_task, phase_by_task

    return build


def test_get_render_tasks_single(tmp_path):
    pipeline = Pipeline(tmp_path)
    slps = [tmp_path / "game.slp"]
    for slp in slps:
        slp.touch()
    artifacts = [SlippiArtifact(slp) for slp in slps]
    tasks = list(pipeline.get_render_tasks(artifacts))

    assert len(tasks) == 1

    task = tasks[0]
    assert task.name == "render game.slp"
    assert task.slp == artifacts[0]
    assert task.inputs == artifacts
    assert task.final_name == Path("game.mp4")


def test_get_render_tasks_multiple(tmp_path):
    pipeline = Pipeline(tmp_path)
    prefixes = [f"g{i}" for i in range(3)]
    slps = [tmp_path / f"{prefix}.slp" for prefix in prefixes]
    for slp in slps:
        slp.touch()
    artifacts = [SlippiArtifact(slp) for slp in slps]
    tasks = list(pipeline.get_render_tasks(artifacts))

    assert len(tasks) == 3

    for task, artifact, prefix in zip(tasks[:3], artifacts, prefixes):
        assert task.name == f"render {prefix}.slp"
        assert task.slp == artifact
        assert task.inputs == [artifact]
        assert task.final_name == Path(f"{prefix}.mp4")


def test_get_concat_tasks_single(tmp_path):
    pipeline = Pipeline(tmp_path)
    vids = [tmp_path / "game.mp4"]
    for vid in vids:
        vid.touch()
    artifacts = [Mp4Artifact(vid) for vid in vids]
    final_path = Path("used.mp4")
    tasks = list(pipeline.get_concat_tasks(artifacts, final_path))
    assert len(tasks) == 0


def test_get_concat_tasks_multiple(tmp_path):
    pipeline = Pipeline(tmp_path)
    prefixes = [f"g{i}" for i in range(3)]
    vids = [tmp_path / f"{prefix}.mp4" for prefix in prefixes]
    for vid in vids:
        vid.touch()
    artifacts = [Mp4Artifact(vid) for vid in vids]
    final_path = Path("used.mp4")
    tasks = list(pipeline.get_concat_tasks(artifacts, final_path))

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
    tasks = list(pipeline.get_group_concat_tasks(input_tasks, {}, {}, CombineMode.NONE))
    assert tasks == []


def test_get_group_concat_tasks_all_combine_simple(tmp_path):
    pipeline = Pipeline(tmp_path)
    outputs = []
    input_tasks = []
    input_by_task = {}
    phase_by_task = {}
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
        phase_by_task[task] = (str(i), str(i), str(i))

    tasks = list(
        pipeline.get_group_concat_tasks(
            input_tasks, input_by_task, phase_by_task, CombineMode.ALL
        )
    )
    assert len(tasks) == 1
    assert len(tasks[0]) == 1

    task = tasks[0][0]
    assert task.name == "concat all.mp4"
    assert task.inputs == outputs
    assert task.final_name == Path("all.mp4")


def test_get_group_concat_tasks_all_combine_complex(tmp_path, complex_pipeline):
    pipeline = Pipeline(tmp_path)
    input_tasks, input_by_task, phase_by_task = complex_pipeline()
    tasks = list(
        pipeline.get_group_concat_tasks(
            input_tasks, input_by_task, phase_by_task, CombineMode.ALL
        )
    )

    assert len(tasks) == 1

    assert len(tasks[0]) == 1
    task = tasks[0][0]
    assert task.name == "concat all.mp4"
    assert task.final_name == Path("all.mp4")
    assert len(task.inputs) == 9
    assert task.inputs == [
        Mp4Artifact(Path("2 out.mp4")),  # Tournament A - Doubles - Winners
        Mp4Artifact(Path("1 out.mp4")),  # Tournament A - Singles - Losers
        Mp4Artifact(Path("0 out.mp4")),  # Tournament A - Singles - Winners
        Mp4Artifact(Path("3 out.mp4")),  # Tournament B - Doubles - Winners
        Mp4Artifact(Path("5 out.mp4")),  # Tournament B - Doubles - Winners
        Mp4Artifact(Path("4 out.mp4")),  # Tournament B - Singles - Losers
        Mp4Artifact(Path("7 out.mp4")),  # Tournament C - Doubles - Losers
        Mp4Artifact(Path("6 out.mp4")),  # Tournament C - Doubles - Losers
        Mp4Artifact(Path("8 out.mp4")),  # Tournament C - Doubles - Losers
    ]


def test_get_group_concat_tasks_input_combine(tmp_path, complex_pipeline):
    pipeline = Pipeline(tmp_path)
    input_tasks, input_by_task, phase_by_task = complex_pipeline()
    tasks = list(
        pipeline.get_group_concat_tasks(
            input_tasks, input_by_task, phase_by_task, CombineMode.BY_INPUT
        )
    )

    assert len(tasks) == 3

    assert len(tasks[0]) == 1
    task = tasks[0][0]
    assert task.name == "concat input-0.mp4"
    assert task.final_name == Path("input-0.mp4")
    assert len(task.inputs) == 3
    assert task.inputs == [
        Mp4Artifact(Path("2 out.mp4")),  # Tournament A - Doubles - Winners
        Mp4Artifact(Path("1 out.mp4")),  # Tournament A - Singles - Losers
        Mp4Artifact(Path("0 out.mp4")),  # Tournament A - Singles - Winners
    ]

    assert len(tasks[1]) == 1
    task = tasks[1][0]
    assert task.name == "concat input-1.mp4"
    assert task.final_name == Path("input-1.mp4")
    assert len(task.inputs) == 3
    assert task.inputs == [
        Mp4Artifact(Path("3 out.mp4")),  # Tournament B - Doubles - Winners
        Mp4Artifact(Path("5 out.mp4")),  # Tournament B - Doubles - Winners
        Mp4Artifact(Path("4 out.mp4")),  # Tournament B - Singles - Losers
    ]

    assert len(tasks[2]) == 1
    task = tasks[2][0]
    assert task.name == "concat input-2.mp4"
    assert task.final_name == Path("input-2.mp4")
    assert len(task.inputs) == 3
    assert task.inputs == [
        Mp4Artifact(Path("7 out.mp4")),  # Tournament C - Doubles - Losers
        Mp4Artifact(Path("6 out.mp4")),  # Tournament C - Doubles - Losers
        Mp4Artifact(Path("8 out.mp4")),  # Tournament C - Doubles - Losers
    ]


def test_get_group_concat_tasks_phase_combine(tmp_path, complex_pipeline):
    pipeline = Pipeline(tmp_path)
    input_tasks, input_by_task, phase_by_task = complex_pipeline()
    tasks = list(
        pipeline.get_group_concat_tasks(
            input_tasks, input_by_task, phase_by_task, CombineMode.BY_PHASE
        )
    )

    assert len(tasks) == 6

    assert len(tasks[0]) == 1
    task = tasks[0][0]
    assert task.name == "concat Tournament A - Singles - Winners.mp4"
    assert task.final_name == Path("Tournament A - Singles - Winners.mp4")
    assert len(task.inputs) == 1
    assert task.inputs == [
        Mp4Artifact(Path("0 out.mp4")),  # Tournament A - Singles - Winners
    ]

    assert len(tasks[1]) == 1
    task = tasks[1][0]
    assert task.name == "concat Tournament A - Singles - Losers.mp4"
    assert task.final_name == Path("Tournament A - Singles - Losers.mp4")
    assert len(task.inputs) == 1
    assert task.inputs == [
        Mp4Artifact(Path("1 out.mp4")),  # Tournament A - Singles - Losers
    ]

    assert len(tasks[2]) == 1
    task = tasks[2][0]
    assert task.name == "concat Tournament A - Doubles - Winners.mp4"
    assert task.final_name == Path("Tournament A - Doubles - Winners.mp4")
    assert len(task.inputs) == 1
    assert task.inputs == [
        Mp4Artifact(Path("2 out.mp4")),  # Tournament A - Doubles - Winners
    ]

    assert len(tasks[3]) == 1
    task = tasks[3][0]
    assert task.name == "concat Tournament B - Doubles - Winners.mp4"
    assert task.final_name == Path("Tournament B - Doubles - Winners.mp4")
    assert len(task.inputs) == 2
    assert task.inputs == [
        Mp4Artifact(Path("3 out.mp4")),  # Tournament B - Doubles - Winners
        Mp4Artifact(Path("5 out.mp4")),  # Tournament B - Doubles - Winners
    ]

    assert len(tasks[4]) == 1
    task = tasks[4][0]
    assert task.name == "concat Tournament B - Singles - Losers.mp4"
    assert task.final_name == Path("Tournament B - Singles - Losers.mp4")
    assert len(task.inputs) == 1
    assert task.inputs == [
        Mp4Artifact(Path("4 out.mp4")),  # Tournament B - Singles - Losers
    ]

    assert len(tasks[5]) == 1
    task = tasks[5][0]
    assert task.name == "concat Tournament C - Doubles - Losers.mp4"
    assert task.final_name == Path("Tournament C - Doubles - Losers.mp4")
    assert len(task.inputs) == 3
    assert task.inputs == [
        Mp4Artifact(Path("7 out.mp4")),  # Tournament C - Doubles - Losers
        Mp4Artifact(Path("6 out.mp4")),  # Tournament C - Doubles - Losers
        Mp4Artifact(Path("8 out.mp4")),  # Tournament C - Doubles - Losers
    ]
