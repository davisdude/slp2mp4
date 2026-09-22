import time
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Event
from pathlib import Path

from slp2mp4 import config
from slp2mp4.artifact import Mp4Artifact, SlippiArtifact
from slp2mp4.task import RenderGameTask, Worker


def test_render_full(make_file, check_duration):
    expected_duration = 65.6165
    duration_tolerance = 0.1

    test_slp_artifact = SlippiArtifact(Path("tests/integration/test.slp"))
    test_mp4_file = make_file("test.mp4")
    test_mp4_artifact = Mp4Artifact(test_mp4_file.path)
    render_task = RenderGameTask("render", [test_slp_artifact], [test_mp4_artifact])

    conf = config.get_config()
    default_conf = config.get_default_config()
    default_conf.paths = conf.paths
    kill_event = Event()

    worker = Worker(default_conf, kill_event)
    worker.submit(render_task)
    check_duration(test_mp4_file.path, expected_duration, duration_tolerance)


def test_render_short(make_file, check_duration):
    expected_duration = 10.0

    # duration_tolerance is so high because launching can be quite slow. Plus, test_render_full
    # validates time more precisely.
    duration_tolerance = 5.0

    test_slp_artifact = SlippiArtifact(Path("tests/integration/test.slp"))
    test_mp4_file = make_file("test.mp4")
    test_mp4_artifact = Mp4Artifact(test_mp4_file.path)
    render_task = RenderGameTask("render", [test_slp_artifact], [test_mp4_artifact])

    conf = config.get_config()
    default_conf = config.get_default_config()
    default_conf.paths = conf.paths
    kill_event = Event()

    worker = Worker(default_conf, kill_event)

    def _kill():
        time.sleep(expected_duration)
        kill_event.set()

    with ThreadPoolExecutor(2) as executor:
        executor.submit(worker.submit, render_task)
        executor.submit(_kill)

    check_duration(test_mp4_file.path, expected_duration, duration_tolerance)
