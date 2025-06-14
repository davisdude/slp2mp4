# Logic to orchestrate making a video file from a slippi replay

import contextlib
import pathlib
import tempfile

import slp2mp4.ffmpeg as ffmpeg
import slp2mp4.replay as replay
import slp2mp4.dolphin.runner as dolphin_runner


@contextlib.contextmanager
def _no_context():
    try:
        yield tuple()
    finally:
        pass


# Returns True if the render succeeded, False otherwise
# output_path must be a container that requires no reencoding, e.g. mkv
def render(conf, slp_path: pathlib.Path, output_path: pathlib.Path, context: pathlib.Path, index):
    Ffmpeg = ffmpeg.FfmpegRunner(conf)
    Dolphin = dolphin_runner.DolphinRunner(conf)
    if context:
        sb = conf["scoreboard"]["type"](context, index)
        context_cm = sb.get_args
    else:
        context_cm = _no_context
    with (
        tempfile.TemporaryDirectory() as tmpdir_str,
        context_cm() as video_filter_args,
    ):
        tmpdir = pathlib.Path(tmpdir_str)
        r = replay.ReplayFile(slp_path)
        audio_file, video_file = Dolphin.run_dolphin(r, tmpdir)
        reencoded_audio_file = Ffmpeg.reencode_audio(audio_file)
        Ffmpeg.merge_audio_and_video(
            reencoded_audio_file,
            video_file,
            output_path,
            video_filter_args,
        )
