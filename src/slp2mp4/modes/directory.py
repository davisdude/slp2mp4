import argparse
import pathlib

import slp2mp4.util as util


def get_inputs_and_outputs(
    root: pathlib.Path, in_dir: pathlib.Path, out_dir: pathlib.Path, no_prepend_folder: bool = False, youtube_mode: bool = False
):
    outputs = {}
    root = root.resolve().absolute()
    in_dir = in_dir.resolve().absolute()
    slps = list(sorted(in_dir.glob("*.slp"), key=util.natsort))
    root_name = pathlib.Path(root.name)
    relative_path = root_name.joinpath(in_dir.relative_to(root))
    
    if no_prepend_folder:
        # Just use the last directory name
        name = f"""{out_dir.joinpath(relative_path.name)}.mp4"""
    else:
        # Prepend folder names as before
        name = f"""{out_dir.joinpath(("_").join(relative_path.parts))}.mp4"""

    if youtube_mode:
        name = name.replace("-", "—")
        name = name.replace("(", "⟮")
        name = name.replace(")", "⟯")
    
    if len(slps) > 0:
        outputs[name] = slps
    for child in in_dir.iterdir():
        if child.is_dir():
            outputs = outputs | get_inputs_and_outputs(root, child, out_dir, no_prepend_folder, youtube_mode)
    return outputs


def run(conf, args):
    if not args.path.exists() or not args.path.is_dir():
        raise FileNotFoundError(args.path.name)
    return get_inputs_and_outputs(args.path, args.path, args.output_directory, args.no_prepend_folder, args.youtube_mode)


def register(subparser):
    parser = subparser.add_parser(
        "directory",
        help="render and combine .slp files in a directory to a video, recursively",
    )
    parser.add_argument("path", type=pathlib.Path)
    parser.set_defaults(run=run)
