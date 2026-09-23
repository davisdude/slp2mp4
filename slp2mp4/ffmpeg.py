# Logic for joining audio / video files

import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from slp2mp4 import log


class FfmpegRunner:
    def __init__(self, config):
        self.config = config
        self.ffmpeg_path = shutil.which(config.paths.ffmpeg)
        self.ffprobe_path = config.paths.get_ffprobe()
        self.audio_args = shlex.split(config.ffmpeg.audio_args)
        self.log = log.get_logger()

    # TODO: Pass kill_event
    def _run(self, args, kwargs=None):
        if kwargs is None:
            kwargs = {
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
            }
        proc = subprocess.run(args, check=False, **kwargs)
        stdout = proc.stdout.decode(errors="backslashreplace")
        if proc.returncode != 0:
            self.log.error(f"{args = }: {stdout}")
        else:
            self.log.debug(f"{args = }: {stdout}")
        return proc

    def reencode_audio(self, audio_file_path: Path):
        reencoded_path = audio_file_path.parent / "fixed.out"
        args = (
            self.ffmpeg_path,
            "-y",
            "-i",
            audio_file_path,
            *self.audio_args,
            "-filter:a",
            f"volume='{self.config.ffmpeg.volume / 100}'",
            reencoded_path,
        )
        proc = self._run(args)
        if proc.returncode == 0:
            return reencoded_path

    # Assumes output file can handle no reencoding for concat
    # Returns True if ffmpeg ran successfully, False otherwise
    def merge_audio_and_video(
        self,
        audio_file: Path,
        video_file: Path,
        output_file: Path,
    ):
        args = (
            self.ffmpeg_path,
            "-y",
            "-i",
            audio_file,
            "-i",
            video_file,
            "-c:a",
            "copy",
            "-c:v",
            "copy",
            "-b:v",  # TODO follow setting; this is ignored with -c:v
            "7500k",
            "-avoid_negative_ts",
            "make_zero",
            "-xerror",
            output_file,
        )
        proc = self._run(args)
        return proc.returncode == 0

    # Assumes all videos have the same encoding
    def concat_videos(self, videos: list[Path], output_file: Path):
        # Make a temp directory because windows doesn't like NamedTemporaryFiles :(
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            open(Path(tmpdir) / "concat.txt", "w") as concat_file,
        ):
            files = ("\n").join(f"file '{video.resolve()}'" for video in videos)
            concat_file.write(files)
            concat_file.flush()
            args = (
                self.ffmpeg_path,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_file.name,
                "-c",
                "copy",
                "-xerror",
                str(output_file),
            )
            proc = self._run(args)
            return proc.returncode == 0

    def get_video_duration(self, video: Path):
        args = (
            self.ffprobe_path,
            "-i",
            str(video),
            "-show_entries",
            "format=duration",
            "-v",
            "quiet",
            "-of",
            "csv=p=0",
        )
        proc = self._run(args)
        return float(proc.stdout)
