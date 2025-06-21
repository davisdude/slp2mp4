# Logic to orchestrate making a video file from a slippi replay

import contextlib
import pathlib
import tempfile

import slp2mp4.dolphin.runner as dolphin_runner
from slp2mp4 import ffmpeg, output, replay, util


# Returns True if the render succeeded, False otherwise
# output_path must be a container that requires no reencoding, e.g. mkv
def render(
    conf,
    component: output.OutputComponent,
    output_path: pathlib.Path,
    final_path: pathlib.Path,
):
    Ffmpeg = ffmpeg.FfmpegRunner(conf)
    Dolphin = dolphin_runner.DolphinRunner(conf)
    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = pathlib.Path(tmpdir_str)
        r = replay.ReplayFile(component.slp)
        tmp_audio_file, video_file = Dolphin.run_dolphin(r, tmpdir)
        audio_file = Ffmpeg.reencode_audio(tmp_audio_file)
        util.copy_for_debugging(conf, video_file, final_path, component.slp.name)
        util.copy_for_debugging(conf, audio_file, final_path, component.slp.name)
        Ffmpeg.combine_audio_and_video(audio_file, video_file, output_path)
        util.copy_for_debugging(conf, output_path, final_path, component.slp.name)
