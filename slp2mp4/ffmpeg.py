# Logic for joining audio / video files

import dataclasses
import subprocess
import tempfile
from logging import Logger
from multiprocessing import Event
from pathlib import Path

from slp2mp4 import log, util
from slp2mp4.config import Config


@dataclasses.dataclass
class FfmpegRunner:
    config: Config
    kill_event: Event

    log: Logger = dataclasses.field(init=False)

    def __post_init__(self):
        self.log = log.get_logger()

    def _run(self, args: list[str]):
        proc = subprocess.Popen(
            args=args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=util.get_env(),
        )
        while True:
            try:
                stdout, stderr = proc.communicate(timeout=1)
                break
            except subprocess.TimeoutExpired:
                if not self.kill_event.is_set():
                    continue
                proc.terminate()
                try:
                    stdout, stderr = proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, stderr = proc.communicate()
        if proc.returncode == 0:
            self.log.debug(f"{args = }")
        else:
            self.log.error(f"{args = }:\nstdout: {stdout}\nstderr: {stderr}")
        return subprocess.CompletedProcess(
            args=args,
            returncode=proc.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    def run(self, args):
        return self._run([self.config.paths.ffmpeg_path] + args)

    def reencode_audio(self, audio_file_path: Path):
        reencoded_path = audio_file_path.parent / "fixed.out"
        args = (
            self.config.paths.ffmpeg_path,
            "-y",
            "-i",
            audio_file_path,
            *self.config.ffmpeg.split_audio_args,
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
            self.config.paths.ffmpeg_path,
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
                self.config.paths.ffmpeg_path,
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
            self.config.paths.ffprobe_path,
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
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to get duration of '{video}'")
        return float(proc.stdout)

    def get_video_dimensions(self, video: Path):
        args = (
            str(self.config.paths.ffprobe_path),
            "-v",
            "quiet",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            str(video),
        )
        proc = self._run(args)
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to get dimensions of '{video}'")
        return [int(v) for v in proc.stdout.split(",")]
