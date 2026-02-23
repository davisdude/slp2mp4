# Logic for joining audio / video files

import pathlib
import tempfile
import subprocess
import shlex

from slp2mp4 import config, util


class FfmpegRunner:
    def __init__(self, conf):
        self.conf = conf

    def run(self, args):
        ffmpeg_args = [self.conf["paths"]["ffmpeg"]] + util.flatten_arg_tuples(args)
        subprocess.run(
            ffmpeg_args,
            check=True,
            stdin=subprocess.DEVNULL,
        )

    # Audio reencoding has to be done separately - see "corrupt input packet"
    # complaints otherwise
    def reencode_audio(self, audio_file_path: pathlib.Path):
        reencoded_path = audio_file_path.parent / "fixed.out"
        args = (
            ("-y",),
            (
                "-i",
                audio_file_path,
            ),
            shlex.split(self.conf["ffmpeg"]["audio_args"]),
            (
                "-filter:a",
                f"volume='{self.conf['ffmpeg']['volume']/100}'",
            ),
            (reencoded_path,),
        )
        self.run(args)
        return reencoded_path

    # Assumes output file can handle no reencoding for concat
    # Returns True if ffmpeg ran successfully, False otherwise
    def combine_audio_and_video(
        self,
        audio_file: pathlib.Path,
        video_file: pathlib.Path,
        output_file: pathlib.Path,
    ):
        args = (
            ("-y",),
            ("-i", audio_file),
            ("-i", video_file),
            ("-c", "copy"),
            ("-avoid_negative_ts", "make_zero"),
            ("-xerror",),
            (output_file,),
        )
        self.run(args)

    def add_scoreboard(self, replay: pathlib.Path, context, output_file: pathlib.Path):
        height = config.get_expected_height(self.conf)
        sb = self.conf["scoreboard"]["type"](context, self.conf, height)
        with sb.get_args() as (inputs, video_filter):
            sb_inputs = tuple(("-i", i) for i in inputs)
            filter_args = (
                "-filter_complex",
                (",").join(video_filter),
            )
            args = (
                ("-y",),
                ("-i", replay),
                *sb_inputs,
                filter_args,
                ("-map", "[v]"),
                ("-codec:v", "h264"),
                ("-map", "0:a"),
                ("-codec:a", "copy"),
                (output_file,),
            )
            self.run(args)

    # Assumes all videos have the same encoding
    def concat_videos(self, videos: [pathlib.Path], output_file: pathlib.Path):
        # Make a temp directory because windows doesn't like NamedTemporaryFiles :(
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(pathlib.Path(tmpdir) / "concat.txt", "w") as concat_file:
                files = ("\n").join(f"file '{video.resolve()}'" for video in videos)
                concat_file.write(files)
                concat_file.flush()
                args = (
                    ("-y",),
                    ("-f", "concat"),
                    ("-fflags", "+igndts"),
                    ("-safe", "0"),
                    ("-i", concat_file.name),
                    ("-c", "copy"),
                    ("-xerror",),
                    (output_file,),
                )
                self.run(args)
