import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from multiprocessing import Event

import slp2mp4.config as config
from slp2mp4.artifact import SlippiArtifact, Mp4Artifact
from slp2mp4.task import RenderGameTask


def test_render_full(make_file, check_duration):
    expected_duration = 65.6165
    duration_tolerance = 0.1

    test_slp_artifact = SlippiArtifact(Path("tests/integration/test.slp"))
    test_mp4_file = make_file("test.mp4")
    test_mp4_artifact = Mp4Artifact(test_mp4_file.path)
    render_task = RenderGameTask("render", [test_slp_artifact], [test_mp4_artifact])

    # TODO: Don't rely on user config except for paths...
    kill_event = Event()
    conf = config.get_config()
    config.translate_and_validate_config(conf)

    render_task.work(kill_event, conf)
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

    # TODO: Don't rely on user config except for paths...
    kill_event = Event()
    conf = config.get_config()
    config.translate_and_validate_config(conf)

    def _kill():
        time.sleep(expected_duration)
        kill_event.set()

    with ThreadPoolExecutor(2) as executor:
        executor.submit(render_task.work, kill_event, conf)
        executor.submit(_kill)

    check_duration(test_mp4_file.path, expected_duration, duration_tolerance)
