from slp2mp4 import artifact, task
import pytest


def test_existing_file(make_file):
    file = make_file("text.txt", create=True)
    assert file.exists()


def test_missing_file(make_file):
    file = make_file("text.txt", create=False)
    assert not file.exists()


def test_existing_file_artifact_happy_path(make_file):
    file = make_file("text.txt", create=True, cls=artifact.ExistingFileArtifact)


def test_existing_file_artifact_sad_path(make_file):
    with pytest.raises(RuntimeError, match=r"^'.*text\.txt' does not exist\.$"):
        file = make_file("text.txt", create=False, cls=artifact.ExistingFileArtifact)

    with pytest.raises(RuntimeError, match=r"^'.*game\.slp' does not exist\.$"):
        game = make_file("game.slp", create=False, cls=artifact.SlippiArtifact)


def test_extension_checking(make_file):
    game = make_file("game.slp", create=True, cls=artifact.SlippiArtifact)

    with pytest.raises(
        RuntimeError,
        match=r"^'.*game\.xyz' has invalid file extension for a slippi file\.$",
    ):
        game = make_file("game.xyz", create=True, cls=artifact.SlippiArtifact)

    mp4 = make_file("vid.mp4", create=True, cls=artifact.Mp4Artifact)

    with pytest.raises(
        RuntimeError,
        match=r"^'.*vid\.xyz' has invalid file extension for an mp4 file\.$",
    ):
        mp4 = make_file("vid.xyz", create=True, cls=artifact.Mp4Artifact)
