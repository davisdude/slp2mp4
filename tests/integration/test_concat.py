import time
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Event
from pathlib import Path

from slp2mp4 import config
from slp2mp4.artifact import Mp4Artifact, SlippiArtifact
from slp2mp4.task import ConcatVideosTask, RenderGameTask, Worker


def test_concat(make_file, get_duration, check_duration):
    test_slp_artifact = SlippiArtifact(Path("tests/integration/test.slp"))
    test_mp4_file = make_file("test.mp4")
    test_mp4_artifact = Mp4Artifact(test_mp4_file.path)
    render_task = RenderGameTask("render", [test_slp_artifact], [test_mp4_artifact])
    concat_file = make_file("out.mp4")
    concat_mp4_artifact = Mp4Artifact(concat_file.path)
    concat_task = ConcatVideosTask(
        "concat", 3 * [test_mp4_artifact], [concat_mp4_artifact]
    )

    conf = config.get_config()
    default_conf = config.get_default_config()
    default_conf.paths = conf.paths
    kill_event = Event()

    worker = Worker(default_conf, kill_event)

    def _kill():
        time.sleep(10)
        kill_event.set()

    with ThreadPoolExecutor(2) as executor:
        executor.submit(worker.submit, render_task)
        executor.submit(_kill)

    duration = get_duration(test_mp4_file.path)
    expected_duration = 3 * duration
    duration_tolerance = 0.1

    kill_event.clear()
    worker.submit(concat_task)
    check_duration(concat_file.path, expected_duration, duration_tolerance)
