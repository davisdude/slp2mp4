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
    # inputs[0]=dumped audio; inputs[1]=dumped video; rest are from scoreboard
    def combine_audio_and_video_and_apply_filters(
        self,
        inputs: list[pathlib.Path],
        output_file: pathlib.Path,
        video_filter: tuple[str],
    ):
        input_args = tuple(("-i", file) for file in inputs)
        if video_filter:
            filter_args = (
                "-filter_complex",
                (",").join(video_filter),
            )
            video_map = (filter_args,) + (
                ("-map", "[v]"),
                ("-codec:v", "h264"),
            )
        else:
            video_map = (
                ("-map", "1:v"),
                ("-codec:v", "copy"),
            )
        args = (
            ("-y",),
            *input_args,
            *video_map,
            ("-map", "0:a"),
            ("-codec:a", "copy"),
            ("-avoid_negative_ts", "make_zero"),
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
