import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from multiprocessing import Event

import slp2mp4.config as config
from slp2mp4.artifact import SlippiArtifact, Mp4Artifact
from slp2mp4.task import RenderGameTask


def test_render_full(make_file):
    expected_duration = 65.6165
    duration_tolerance = 0.1

    out_file = make_file("out.mp4")
    game = SlippiArtifact(Path("tests/integration/test.slp"))
    out = Mp4Artifact(out_file.path)
    task = RenderGameTask("render", [game], [out])
    kill_event = Event()

    # TODO: Don't rely on user config except for paths...
    conf = config.get_config()
    config.translate_and_validate_config(conf)

    task.work(kill_event, conf)

    result = subprocess.run(
        ["ffprobe", "-i", str(out_file.path), "-show_entries", "format=duration", "-v", "quiet", "-of", "csv=p=0"],
        check=True,
        capture_output=True,
    )
    duration = float(result.stdout)
    assert abs(duration - expected_duration) <= duration_tolerance


def test_render_short(make_file):
    expected_duration = 10.0

    # duration_tolerance is so high because launching can be quite slow. Plus, test_render_full
    # validates time more precisely.
    duration_tolerance = 5.0

    out_file = make_file("out.mp4")
    game = SlippiArtifact(Path("tests/integration/test.slp"))
    out = Mp4Artifact(out_file.path)
    task = RenderGameTask("render", [game], [out])
    kill_event = Event()

    # TODO: Don't rely on user config except for paths...
    conf = config.get_config()
    config.translate_and_validate_config(conf)

    def _kill():
        time.sleep(expected_duration)
        kill_event.set()

    with ThreadPoolExecutor(2) as executor:
        executor.submit(task.work, kill_event, conf)
        executor.submit(_kill)

    result = subprocess.run(
        ["ffprobe", "-i", str(out_file.path), "-show_entries", "format=duration", "-v", "quiet", "-of", "csv=p=0"],
        check=True,
        capture_output=True,
    )
    duration = float(result.stdout)
    assert abs(duration - expected_duration) <= duration_tolerance
