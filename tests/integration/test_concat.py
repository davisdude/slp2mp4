import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from multiprocessing import Event

import slp2mp4.config as config
from slp2mp4.artifact import SlippiArtifact, Mp4Artifact
from slp2mp4.task import RenderGameTask, ConcatVideosTask


def test_concat(make_file, get_duration, check_duration):
    test_slp_artifact = SlippiArtifact(Path("tests/integration/test.slp"))
    test_mp4_file = make_file("test.mp4")
    test_mp4_artifact = Mp4Artifact(test_mp4_file.path)
    render_task = RenderGameTask("render", [test_slp_artifact], [test_mp4_artifact])
    concat_file = make_file("out.mp4")
    concat_mp4_artifact = Mp4Artifact(concat_file.path)
    concat_task = ConcatVideosTask("concat", 3 * [test_mp4_artifact], [concat_mp4_artifact])

    # TODO: Don't rely on user config except for paths...
    kill_event = Event()
    conf = config.get_config()
    config.translate_and_validate_config(conf)

    def _kill():
        time.sleep(10)
        kill_event.set()

    with ThreadPoolExecutor(2) as executor:
        executor.submit(render_task.work, kill_event, conf)
        executor.submit(_kill)

    duration = get_duration(test_mp4_file.path)
    expected_duration = 3 * duration
    duration_tolerance = 0.1

    kill_event = Event()
    concat_task.work(kill_event, conf)
    check_duration(concat_file.path, expected_duration, duration_tolerance)
