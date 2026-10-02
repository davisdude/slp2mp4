from multiprocessing import Event
from pathlib import Path
from unittest.mock import Mock

from slp2mp4.artifact import SlippiArtifact
from slp2mp4.collector import ConcatRequest, RenderRequest
from slp2mp4.config import CombineMode, get_default_config
from slp2mp4.context import ContextData
from slp2mp4.orchestrator import Orchestrator


def test_get_timestamps_simple():
    # concat game0-2.mp4 -> set.mp4
    mock_render_tasks = []
    for i in range(3):
        mock = Mock()
        mock.final_name = Path(f"game{i}.mp4")
        mock_render_tasks.append(mock)
    mock_mp4s = [Mock() for _ in range(3)]

    mock_task = Mock()
    mock_task.timestamps = [0, 60, 3601]
    mock_task.inputs = mock_mp4s

    mock_scheduler = Mock()
    mock_scheduler.walk_tree.side_effect = {
        mock_task: ((0, mock_task),),
    }.__getitem__
    mock_scheduler.get_producer.side_effect = {
        mock_mp4: mock_render_task
        for mock_mp4, mock_render_task in zip(mock_mp4s, mock_render_tasks)
    }.__getitem__

    conf = get_default_config()
    kill_event = Event()
    orchestrator = Orchestrator(
        conf=conf,
        kill_event=kill_event,
        collector=None,
        combine_mode=CombineMode.NONE,
    )
    orchestrator.scheduler = mock_scheduler

    timestamps = orchestrator.get_timestamps(mock_task)
    assert timestamps == "0:00:00 - game0\n0:01:00 - game1\n1:00:01 - game2"


def test_get_move_paths_simple():
    mock_task = Mock()
    mock_task.final_name = Path("out.mp4")
    conf = get_default_config()
    kill_event = Event()
    orchestrator = Orchestrator(
        conf=conf,
        kill_event=kill_event,
        collector=None,
        combine_mode=CombineMode.NONE,
    )
    tasks = [mock_task]

    move_paths = orchestrator.get_move_paths(tasks)
    assert move_paths == [Path("out.mp4")]


def test_get_move_paths_no_preserve_directory_structure():
    mock_task = Mock()
    mock_task.final_name = Path("path/to/out.mp4")
    conf = get_default_config()
    conf.runtime.preserve_directory_structure = False
    kill_event = Event()
    orchestrator = Orchestrator(
        conf=conf,
        kill_event=kill_event,
        collector=None,
        combine_mode=CombineMode.NONE,
    )
    tasks = [mock_task]

    move_paths = orchestrator.get_move_paths(tasks)
    assert move_paths == [Path("out.mp4")]


def test_get_move_paths_preserve_directory_structure():
    mock_task = Mock()
    mock_task.final_name = Path("path/to/out.mp4")
    conf = get_default_config()
    conf.runtime.preserve_directory_structure = True
    kill_event = Event()
    outdir = Path("outdir/foo/")
    orchestrator = Orchestrator(
        conf=conf,
        kill_event=kill_event,
        collector=None,
        combine_mode=CombineMode.NONE,
        output_directory=outdir,
    )
    tasks = [mock_task]

    move_paths = orchestrator.get_move_paths(tasks)
    assert move_paths == [Path("outdir/foo/path/to/out.mp4")]


def test_get_final_name_dont_use_context():
    conf = get_default_config()
    conf.runtime.use_context_json = False
    kill_event = Event()
    orchestrator = Orchestrator(
        conf=conf,
        kill_event=kill_event,
        collector=None,
        combine_mode=CombineMode.NONE,
    )
    request = ConcatRequest(Path("dont-use-context.mp4"), [])

    name = orchestrator.get_final_name(request)
    assert name == Path("dont-use-context.mp4")


def test_get_final_name_no_context(tmp_path):
    conf = get_default_config()
    conf.runtime.use_context_json = True
    kill_event = Event()
    orchestrator = Orchestrator(
        conf=conf,
        kill_event=kill_event,
        collector=None,
        combine_mode=CombineMode.NONE,
    )
    slp_path = tmp_path / "game.slp"
    slp_path.touch()
    slp = SlippiArtifact(slp_path)
    request = ConcatRequest(Path("no-context.mp4"), [slp])

    name = orchestrator.get_final_name(request)
    assert name == Path("no-context.mp4")


def test_get_final_name_with_context_startgg_singles(tmp_path):
    conf = get_default_config()
    conf.runtime.use_context_json = True
    kill_event = Event()
    orchestrator = Orchestrator(
        conf=conf,
        kill_event=kill_event,
        collector=None,
        combine_mode=CombineMode.NONE,
    )
    slp_path = tmp_path / "game.slp"
    slp_path.touch()
    context_data = ContextData.from_dict(
        {
            "bestOf": 0,
            "durationMs": 0,
            "scores": [{"slots": []}],
            "finalScore": {
                "slots": [
                    {
                        "displayNames": ["Alice"],
                        "ports": [],
                        "prefixes": [],
                        "pronouns": [],
                        "score": 0,
                    },
                    {
                        "displayNames": ["Bob"],
                        "ports": [],
                        "prefixes": [],
                        "pronouns": [],
                        "score": 0,
                    },
                ]
            },
            "startMs": 0,
            "startgg": {
                "tournament": {"name": "My Tournament"},
                "event": {"name": "Melee Singles"},
                "phase": {"name": "Pools"},
                "set": {"fullRoundText": "Winners Round 1"},
            },
        }
    )
    slp = SlippiArtifact(slp_path, 0, context_data)
    request = ConcatRequest(Path("yes-context.mp4"), [slp])

    name = orchestrator.get_final_name(request)
    assert name == Path(
        "Alice vs Bob - My Tournament - Melee Singles - Pools Winners Round 1.mp4"
    )


def test_get_final_name_with_context_startgg_doubles(tmp_path):
    conf = get_default_config()
    conf.runtime.use_context_json = True
    kill_event = Event()
    orchestrator = Orchestrator(
        conf=conf,
        kill_event=kill_event,
        collector=None,
        combine_mode=CombineMode.NONE,
    )
    slp_path = tmp_path / "game.slp"
    slp_path.touch()
    context_data = ContextData.from_dict(
        {
            "bestOf": 0,
            "durationMs": 0,
            "scores": [{"slots": []}],
            "finalScore": {
                "slots": [
                    {
                        "displayNames": ["Alice", "Bob"],
                        "ports": [],
                        "prefixes": [],
                        "pronouns": [],
                        "score": 0,
                    },
                    {
                        "displayNames": ["Carol", "Dan"],
                        "ports": [],
                        "prefixes": [],
                        "pronouns": [],
                        "score": 0,
                    },
                ]
            },
            "startMs": 0,
            "startgg": {
                "tournament": {"name": "My Tournament"},
                "event": {"name": "Melee Doubles"},
                "phase": {"name": "Pools"},
                "set": {"fullRoundText": "Winners Round 1"},
            },
        }
    )
    slp = SlippiArtifact(slp_path, 0, context_data)
    request = ConcatRequest(Path("yes-context.mp4"), [slp])

    name = orchestrator.get_final_name(request)
    assert name == Path(
        "Alice + Bob vs Carol + Dan - My Tournament - Melee Doubles - Pools Winners Round 1.mp4"
    )


def test_should_skip_request_disabled(tmp_path):
    conf = get_default_config()
    conf.runtime.exclude_streamed_sets = False
    kill_event = Event()
    orchestrator = Orchestrator(
        conf=conf,
        kill_event=kill_event,
        collector=None,
        combine_mode=CombineMode.NONE,
    )
    slp_path = tmp_path / "game.slp"
    slp_path.touch()

    slp = SlippiArtifact(slp_path)
    request = RenderRequest(slp)
    assert not orchestrator.should_skip_request(request)

    context_data = ContextData.from_dict(
        {
            "bestOf": 0,
            "durationMs": 0,
            "scores": [{"slots": []}],
            "finalScore": {"slots": []},
            "startMs": 0,
            "startgg": {"set": {"stream": None}},
        }
    )
    slp = SlippiArtifact(slp_path, 0, context_data)
    request = RenderRequest(slp)
    assert not orchestrator.should_skip_request(request)

    context_data = ContextData.from_dict(
        {
            "bestOf": 0,
            "durationMs": 0,
            "scores": [{"slots": []}],
            "finalScore": {"slots": []},
            "startMs": 0,
            "startgg": {"set": {"stream": "info"}},
        }
    )
    slp = SlippiArtifact(slp_path, 0, context_data)
    request = RenderRequest(slp)
    assert not orchestrator.should_skip_request(request)


def test_should_skip_request_enabled(tmp_path):
    conf = get_default_config()
    conf.runtime.exclude_streamed_sets = True
    kill_event = Event()
    orchestrator = Orchestrator(
        conf=conf,
        kill_event=kill_event,
        collector=None,
        combine_mode=CombineMode.NONE,
    )
    slp_path = tmp_path / "game.slp"
    slp_path.touch()

    slp = SlippiArtifact(slp_path)
    request = RenderRequest(slp)
    assert not orchestrator.should_skip_request(request)

    context_data = ContextData.from_dict(
        {
            "bestOf": 0,
            "durationMs": 0,
            "scores": [{"slots": []}],
            "finalScore": {"slots": []},
            "startMs": 0,
            "startgg": {"set": {"stream": None}},
        }
    )
    slp = SlippiArtifact(slp_path, 0, context_data)
    request = RenderRequest(slp)
    assert not orchestrator.should_skip_request(request)

    context_data = ContextData.from_dict(
        {
            "bestOf": 0,
            "durationMs": 0,
            "scores": [{"slots": []}],
            "finalScore": {"slots": []},
            "startMs": 0,
            "startgg": {"set": {"stream": "info"}},
        }
    )
    slp = SlippiArtifact(slp_path, 0, context_data)
    request = RenderRequest(slp)
    assert orchestrator.should_skip_request(request)
