import argparse
import inspect
import os
import pathlib
import subprocess

import slp2mp4.config as config
import slp2mp4.modes as modes
import slp2mp4.orchestrator as orchestrator

submodules_tuple = inspect.getmembers(modes, inspect.ismodule)
submodules_dict = {mod[0]: mod[1] for mod in submodules_tuple}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output-directory",
        type=pathlib.Path,
        default=".",
        help="output videos to this directory",
    )
    parser.add_argument("-n", "--dry-run", action="store_true")
    parser.add_argument(
        "--no-prepend-folder",
        action="store_true",
        help="don't prepend folder names to output filenames"
    )
    subparser = parser.add_subparsers(help="run mode", required=True)
    for submodule in submodules_dict.values():
        submodule.register(subparser)
    args = parser.parse_args()

    conf = config.get_config()
    products = args.run(conf, args)
    if args.dry_run:
        for out_file, input_files in products.items():
            print(f"{out_file}:")
            for i in input_files:
                print(f"\t{i}")
    else:
        os.makedirs(args.output_directory, exist_ok=True)
        orchestrator.run(conf, products)


if __name__ == "__main__":
    main()
