# Logic to orchestrate making a video file from a slippi replay

import pathlib
import tempfile

import slp2mp4.replay as replay


# Returns True if the render succeeded, False otherwise
# output_path must be a container that requires no reencoding, e.g. mkv
def render(Ffmpeg, Dolphin, slp_path, output_path):
    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = pathlib.Path(tmpdir_str)
        r = replay.ReplayFile(slp_path)
        audio_file, video_file = Dolphin.run_dolphin(r, tmpdir)
        reencoded_audio_file = Ffmpeg.reencode_audio(audio_file)
        Ffmpeg.merge_audio_and_video(
            reencoded_audio_file,
            video_file,
            output_path,
        )
