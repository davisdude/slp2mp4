from pathlib import Path

from slp2mp4.artifact import Artifact

def test_artifacts_equal():
    file1 = Artifact(Path("file.txt"))
    file2 = Artifact(Path("file.txt"))
    other = Artifact(Path("other.txt"))
    assert file1 == file2
    assert file1 != other

def test_artifact_hashable():
    file = Artifact(Path("file.txt"))
    files = {file}
    assert file in files
