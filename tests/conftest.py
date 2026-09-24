import subprocess
from pathlib import Path

from pytest import fixture

from slp2mp4 import artifact


@fixture
def make_file(tmp_path: Path):
    def build(name: str, create: bool = False, cls=artifact.Artifact):
        path = tmp_path / name
        if create:
            path.touch()
        return cls(Path(path))

    return build


def _get_duration(path: Path):
    result = subprocess.run(
        [
            "ffprobe",
            "-i",
            str(path),
            "-show_entries",
            "format=duration",
            "-v",
            "quiet",
            "-of",
            "csv=p=0",
        ],
        check=True,
        capture_output=True,
    )
    return float(result.stdout)


@fixture
def get_duration():
    return _get_duration


@fixture
def check_duration():
    def func(path: Path, expected: float, tolerance: float):
        duration = _get_duration(path)
        assert abs(duration - expected) <= tolerance

    return func
