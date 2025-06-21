# Commonizes the batching / concatenating of slippi files
# There are to threads here:
#   1. The "render" thread, which runs dolphin / does frame dumps
#   2. The "concat" thread, which contatenates frame-dumps into a single mp4

import multiprocessing
import pathlib
import queue
import tempfile
import os

import slp2mp4.ffmpeg as ffmpeg
import slp2mp4.video as video
from slp2mp4.output import Output, OutputComponent


def _render(conf, slp_queue, video_queue):
    while True:
        data = slp_queue.get()
        if data is None:
            break
        output, component = data
        print(f"_render start ({os.getpid()}): {output=} {component=}")
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        out = pathlib.Path(tmp.name)
        video.render(conf, component, out, output.output)
        print(f"_render rendered ({os.getpid()}): {output=} {component=}")
        video_queue.put((output, component, out))


def _concat(conf, video_queue, outputs):
    Ffmpeg = ffmpeg.FfmpegRunner(conf)
    mp4s = {}
    while not video_queue.empty():
        output, component, mp4_path = video_queue.get()
        print(f"_concat start: {output=} {component=} {mp4_path=}")
        if output.output not in mp4s:
            mp4s[output.output] = {}
        mp4s[output.output][component.index] = mp4_path
        if len(mp4s[output.output]) < len(output.components):
            print(f"_concat continue: {mp4s[output.output]=} {len(output.components)=}")
            continue
        if output.context:
            for index in range(len(output.components)):
                in_video = mp4s[output.output][index]
                component = output.components[index]
                new_tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
                out_video = pathlib.Path(new_tmp.name)
                Ffmpeg.add_scoreboard(in_video, component.context, out_video)
                in_video.unlink()
                mp4s[output.output][index] = out_video
        inputs = [mp4s[output.output][index] for index in range(len(output.components))]
        print(f"_concat concat: {inputs=} {output.output=}")
        Ffmpeg.concat_videos(inputs, output.output)
        for tmp in inputs:
            tmp.unlink()


def run(conf, outputs: list[Output]):
    num_procs = conf["runtime"]["parallel"]
    slp_queue = multiprocessing.Queue()
    video_queue = multiprocessing.Queue()
    slp_pool = multiprocessing.Pool(
        num_procs,
        _render,
        (
            conf,
            slp_queue,
            video_queue,
        ),
    )

    for output in outputs:
        for component in output.components:
            slp_queue.put((output, component))

    for i in range(num_procs):
        slp_queue.put(None)

    slp_queue.close()
    slp_queue.join_thread()

    slp_pool.close()
    slp_pool.join()

    _concat(conf, video_queue, outputs)
    video_queue.close()
    video_queue.join_thread()
