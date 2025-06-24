# Commonizes the batching / concatenating of slippi files
# There are to threads here:
#   1. The "render" thread, which runs dolphin / does frame dumps
#   2. The "concat" thread, which contatenates frame-dumps into a single mp4
#      and renders scoreboards

import multiprocessing
import pathlib
import tempfile
import os

import slp2mp4.ffmpeg as ffmpeg
import slp2mp4.video as video
from slp2mp4.output import Output, OutputComponent


def _render(conf, video_dict, output, component):
    print(f"_render start ({os.getpid()}): {output=} {component=}")
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    out = pathlib.Path(tmp.name)
    video.render(conf, component, out, output.output)
    print(f"_render rendered ({os.getpid()}): {output=} {component=}")
    data = video_dict.get(output.output, {
        "output": output,
        "mp4s": {},
    })
    data["mp4s"][component.index] = out
    video_dict[output.output] = data
    print(video_dict)


def _concat(conf, video_dict, outputs):
    Ffmpeg = ffmpeg.FfmpegRunner(conf)
    for data in video_dict.values():
        output = data["output"]
        mp4s = data["mp4s"]
        if output.context:
            for index in range(len(output.components)):
                in_video = mp4s[index]
                component = output.components[index]
                new_tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
                out_video = pathlib.Path(new_tmp.name)
                Ffmpeg.add_scoreboard(in_video, component.context, out_video)
                in_video.unlink()
                mp4s[index] = out_video
        inputs = [mp4s[index] for index in range(len(output.components))]
        print(f"_concat concat: {inputs=} {output.output=}")
        Ffmpeg.concat_videos(inputs, output.output)
        for tmp in inputs:
            tmp.unlink()


def run(conf, outputs: list[Output]):
    num_procs = conf["runtime"]["parallel"]
    manager = multiprocessing.Manager()
    video_dict = manager.dict()

    with multiprocessing.Pool(num_procs) as pool:
        args = [
            (conf, video_dict, output, component)
            for output in outputs
            for component in output.components
        ]
        pool.starmap(_render, args)

    _concat(conf, video_dict, outputs)
