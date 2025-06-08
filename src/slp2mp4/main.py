import argparse
import pathlib

import slp2mp4.modes as modes
import slp2mp4.version as version


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=modes.MODES.keys(),
        help="Run mode",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Paths to convert",
        type=pathlib.Path,
    )
    parser.add_argument(
        "-o",
        "--output-directory",
        type=pathlib.Path,
        default=".",
        help="Output videos to this directory",
    )
    parser.add_argument("-n", "--dry-run", action="store_true")
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=version.version,
    )

    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()
    mode = modes.MODES[args.mode](args.paths, args.output_directory)
    output = mode.run(args.dry_run)
    if output:
        print(output.rstrip())


if __name__ == "__main__":
    main()
