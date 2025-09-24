import argparse
import multiprocessing
import pathlib

import slp2mp4.modes as modes
import slp2mp4.version as version


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output-directory",
        type=pathlib.Path,
        default=".",
        help="set path to output videos",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="show inputs and outputs and exit",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=version.version,
    )
    subparser = parser.add_subparsers(title="mode", required=True)
    for mode_name, mode in modes.MODES.items():
        mode_parser = subparser.add_parser(mode_name, help=mode.help)
        mode_parser.add_argument(
            "paths",
            nargs="+",
            help=mode.description,
            type=pathlib.Path,
        )
        mode_parser.set_defaults(run=mode.mode)

    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()
    mode = args.run(args.paths, args.output_directory)
    manager = multiprocessing.Manager()
    event = manager.Event()
    with mode.run(event, args.dry_run) as (executor, future):
        result = future.result()
        if isinstance(result, str):
            print(result.rstrip())


if __name__ == "__main__":
    main()
