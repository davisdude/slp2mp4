import argparse
import multiprocessing
import pathlib
import signal
import sys

import slp2mp4.modes as modes
import slp2mp4.version as version
import slp2mp4.log as log


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
        "-d",
        "--debug",
        action="store_true",
        help="log more info",
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
    args = vars(parser.parse_args())
    run = args.pop("run")
    debug = args.pop("debug")
    mode = run(**args)
    manager = multiprocessing.Manager()
    event = manager.Event()
    logger = log.update_logger(debug)

    def _sigint_handler(sig, frame):
        logger.info("Got interrupt - stopping")
        event.set()
        mode.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sigint_handler)

    with mode.run(event) as (executor, future):
        if executor is not None:
            future.result()
    mode.cleanup()


if __name__ == "__main__":
    main()
