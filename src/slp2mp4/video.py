# Logic to orchestrate making a video file from a slippi replay

import contextlib
import pathlib
import shutil
import tempfile

import slp2mp4.config as config
import slp2mp4.ffmpeg as ffmpeg
import slp2mp4.replay as replay
import slp2mp4.dolphin.runner as dolphin_runner
from slp2mp4.context_helper import GameContextInfo


@contextlib.contextmanager
def _no_context():
    try:
        yield [], tuple()
    finally:
        pass


# Returns True if the render succeeded, False otherwise
# output_path must be a container that requires no reencoding, e.g. mkv
def render(
    conf,
    slp_path: pathlib.Path,
    output_path: pathlib.Path,
    context: GameContextInfo | None,
    final_path: pathlib.Path,
):
    Ffmpeg = ffmpeg.FfmpegRunner(conf)
    Dolphin = dolphin_runner.DolphinRunner(conf)
    if context:
        height = config.get_expected_height(conf)
        sb = conf["scoreboard"]["type"](context, conf, height)
        context_cm = sb.get_args
    else:
        context_cm = _no_context
    with (
        tempfile.TemporaryDirectory() as tmpdir_str,
        context_cm() as (inputs, video_filter_args),
    ):
        tmpdir = pathlib.Path(tmpdir_str)
        r = replay.ReplayFile(slp_path)
        audio_file, video_file = Dolphin.run_dolphin(r, tmpdir)
        reencoded_audio_file = Ffmpeg.reencode_audio(audio_file)
        inputs = [reencoded_audio_file, video_file] + inputs
        if conf["runtime"]["debug"]:
            for i in inputs:
                shutil.copyfile(i, final_path.parent / f"{slp_path.name}_{i.name}")
        Ffmpeg.combine_audio_and_video_and_apply_filters(
            inputs,
            output_path,
            video_filter_args,
        )
        if conf["runtime"]["debug"]:
            shutil.copyfile(
                output_path, final_path.parent / f"{slp_path.name}_{output_path.name}"
            )
