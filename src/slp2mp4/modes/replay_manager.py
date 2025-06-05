import argparse
import atexit
import os
import pathlib
import shutil
import tempfile
import zipfile

from .directory import get_inputs_and_outputs

# TODO: Use context.json to get names?


def _recursively_unzip(zip_file, to_dir):
    with zipfile.ZipFile(zip_file, "r") as zfile:
        zfile.extractall(path=to_dir)
    # Use os.walk instead of Path.walk() for Python 3.11 compatibility
    for root, dirs, files in os.walk(to_dir):
        root_path = pathlib.Path(root)
        for file in files:
            file_path = root_path / file
            if zipfile.is_zipfile(file_path):
                _recursively_unzip(file_path, root_path)


def run(conf, args):
    if not args.path.exists():
        raise FileNotFoundError(args.path.name)
    if not args.path.is_dir() and zipfile.is_zipfile(args.path):
        parent_name = args.path.resolve().absolute().parent.name
        files = [args.path]
    else:
        parent_name = args.path.resolve().absolute().name
        files = []
        # Use os.walk instead of Path.walk() for Python 3.11 compatibility
        for root, _, walk_files in os.walk(args.path):
            root_path = pathlib.Path(root)
            for file in walk_files:
                path = root_path / file
                if zipfile.is_zipfile(path):
                    files.append(path)
    # Create a temporary directory manually without the delete parameter
    tmpdir = pathlib.Path(tempfile.mkdtemp())

    # Register cleanup function
    atexit.register(shutil.rmtree, tmpdir)

    try:
        tmpdir_main = tmpdir / parent_name
        tmpdir_main.mkdir()

        for file in files:
            _recursively_unzip(file, tmpdir_main / file.stem)

        return get_inputs_and_outputs(tmpdir_main, tmpdir_main, args.output_directory, args.no_prepend_folder)
    except Exception:
        # Clean up on error
        shutil.rmtree(tmpdir)
        raise



def register(subparser):
    parser = subparser.add_parser(
        "replay_manager",
        help="render and combine replay manager zips",
    )
    parser.add_argument("path", type=pathlib.Path)
    parser.set_defaults(run=run)
