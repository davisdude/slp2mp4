# Logic to orchestrate making a video file from a slippi replay

import contextlib
import pathlib
import tempfile

import slp2mp4.dolphin.runner as dolphin_runner
from slp2mp4 import ffmpeg, output, replay, util


# Returns True if the render succeeded, False otherwise
# output_path must be a container that requires no reencoding, e.g. mkv
def render(Ffmpeg, Dolphin, component: output.OutputComponent, output_path):
    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = pathlib.Path(tmpdir_str)
        r = replay.ReplayFile(component.slp)
        tmp_audio_file, video_file = Dolphin.run_dolphin(r, tmpdir)
        audio_file = Ffmpeg.reencode_audio(tmp_audio_file)
        if audio_file is None:
            return False
        return Ffmpeg.combine_audio_and_video(audio_file, video_file, output_path)
