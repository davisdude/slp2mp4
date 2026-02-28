# Logic for joining audio / video files

import pathlib
import tempfile
import subprocess
import shlex

import slp2mp4.log as log
import slp2mp4.util as util


class FfmpegRunner:
    def __init__(self, config):
        self.conf = config
        self.ffmpeg_path = config["paths"]["ffmpeg"]
        self.audio_args = shlex.split(config["ffmpeg"]["audio_args"])
        self.log = log.get_logger()

    def _run(self, args):
        ffmpeg_args = [self.ffmpeg_path] + util.flatten_arg_tuples(args)
        proc = subprocess.run(
            ffmpeg_args,
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if proc.returncode != 0:
            error = proc.stdout.decode(errors="backslashreplace")
            self.log.error(f"Error while running ffmpeg {ffmpeg_args}: {error}")

    def reencode_audio(self, audio_file_path: pathlib.Path):
        reencoded_path = audio_file_path.parent / "fixed.out"
        args = (
            ("-y",),
            (
                "-i",
                audio_file_path,
            ),
            self.audio_args,
            (
                "-filter:a",
                f"volume='{self.conf['ffmpeg']['volume']/100}'",
            ),
            (reencoded_path,),
        )
        self._run(args)
        return reencoded_path

    # Assumes output file can handle no reencoding for concat
    # Returns True if ffmpeg ran successfully, False otherwise
    def merge_audio_and_video(
        self,
        audio_file: pathlib.Path,
        video_file: pathlib.Path,
        output_file: pathlib.Path,
    ):
        args = (
            ("-y",),
            (
                "-i",
                audio_file,
            ),
            (
                "-i",
                video_file,
            ),
            (
                "-c:a",
                "copy",
            ),
            (
                "-c:v",
                "copy",
            ),
            (
                "-b:v",
                "7500k",  # TODO follow setting
            ),
            (
                "-avoid_negative_ts",
                "make_zero",
            ),
            ("-xerror",),
            (output_file,),
        )
        self._run(args)

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
                self._run(args)
