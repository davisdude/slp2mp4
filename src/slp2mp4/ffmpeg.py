# Logic for joining audio / video files

import pathlib
import tempfile
import subprocess
import shlex

import slp2mp4.util as util


class FfmpegRunner:
    def __init__(self, config):
        self.conf = config

    def run(self, args):
        ffmpeg_args = [self.conf["paths"]["ffmpeg"]] + util.flatten_arg_tuples(args)
        subprocess.run(ffmpeg_args, check=True)

    def get_audio_filter(self):
        return (
            shlex.split(self.conf["ffmpeg"]["audio_args"]),
            (
                "-filter:a",
                f"volume='{self.conf['ffmpeg']['volume']/100}'",
            ),
        )

    def get_video_filter(self, video_filter):
        codec = ("-c:v", "mpeg4") if video_filter else ("-c:v", "copy")
        video_args = video_filter + codec
        return (
            video_args,
            (
                "-b:v",
                "7500k",  # TODO follow setting
            ),
            (
                "-avoid_negative_ts",
                "make_zero",
            ),
        )

    # Assumes output file can handle no reencoding for concat
    # Returns True if ffmpeg ran successfully, False otherwise
    def combine_audio_and_video_and_apply_filters(
        self,
        inputs: list[pathlib.Path],
        output_file: pathlib.Path,
        audio_filter: tuple[str],
        video_filter: tuple[str],
    ):
        input_args = tuple(("-i", file) for file in inputs)
        args = (
            ("-y",),
            *input_args,
            #*audio_filter,
            *video_filter,
            ("-xerror",),
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
                    (
                        "-f",
                        "concat",
                    ),
                    (
                        "-safe",
                        "0",
                    ),
                    (
                        "-i",
                        concat_file.name,
                    ),
                    (
                        "-c",
                        "copy",
                    ),
                    ("-xerror",),
                    (output_file,),
                )
                self.run(args)
