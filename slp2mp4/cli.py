import dataclasses
import signal
import typing
from argparse import SUPPRESS, ArgumentParser, BooleanOptionalAction
from multiprocessing import Event
from pathlib import Path

from slp2mp4 import config, log
from slp2mp4.collector import Collector
from slp2mp4.config import Config, RuntimeOptions
from slp2mp4.orchestrator import Orchestrator

try:
    from slp2mp4 import version

    __version__ = version.version
except ImportError:
    __version__ = "0.0.0+dev"


def make_sigint_handler(logger, stop_event: Event, kill_event: Event):
    def func(_sig, _frame):
        if not stop_event.is_set():
            logger.info("Got first sigint - stopping")
            stop_event.set()
            return
        logger.info("Got second sigint - killing")
        kill_event.set()

    return func


def add_config_option_to_parser(
    parser, config_type, help_most=True, help_all=False, prefix=None
):
    if prefix is None:
        prefix = ()

    for field in dataclasses.fields(config_type):
        new_prefix = prefix + (field.name.replace("_", "-"),)
        if dataclasses.is_dataclass(field.type):
            add_config_option_to_parser(
                parser, field.type, help_most, help_all, new_prefix
            )
            continue
        metadata = getattr(field, "metadata", {})
        kwargs = {}
        if dataclasses.is_dataclass(field.type):
            add_config_option_to_parser(
                parser, field.type, help_most, help_all, new_prefix
            )
            continue
        if (default := field.default) is not None:
            kwargs["default"] = default
        metavar = metadata.get("metavar")
        if (not help_all) and metadata.get("help_all", False) and not metavar:
            if help_most and (metavar := metadata.get("help_all_metavar")):
                kwargs["metavar"] = metavar
            else:
                kwargs["help"] = SUPPRESS
        elif not help_most:
            kwargs["help"] = SUPPRESS
        elif help_text := metadata.get("help"):
            kwargs["help"] = help_text
        if field.type is bool:
            if (field.default is True) or (field.default is False):
                kwargs["action"] = "store_false" if field.default else "store_true"
            else:
                kwargs["action"] = BooleanOptionalAction
        elif choices := metadata.get("choices"):
            kwargs["choices"] = choices
        else:
            kwargs["type"] = field.type
        args = []
        if short := metadata.get("short"):
            args.append(f"-{short}")
        long_name = "--" + ("-").join(new_prefix)
        args.append(long_name)
        not_dict = typing.get_origin(field.type) is not dict
        if not_dict and not metadata.get("multiline", False):
            parser.add_argument(*args, **kwargs)


def make_parser(help_most=False, help_all=False):
    if help_all:
        help_most = True
    parser = ArgumentParser(prog="slp2mp4")
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--help-most", help="show most help", action="help")
    parser.add_argument("--help-all", help="show all help", action="help")
    parser.add_argument("-v", "--version", action="version", version=__version__)
    add_config_option_to_parser(parser, RuntimeOptions, True, help_all)
    add_config_option_to_parser(parser, Config, help_most, help_all)
    return parser


def main():
    initial = ArgumentParser(add_help=False)
    initial.add_argument("--help-most", action="store_true")
    initial.add_argument("--help-all", action="store_true")
    initial_args, _ = initial.parse_known_args()

    parser = make_parser(initial_args.help_most, initial_args.help_all)
    args = parser.parse_args()
    runtime_args = RuntimeOptions.dict_from_namespace(args)
    config_args = Config.dict_from_namespace(args)

    conf = config.get_config()
    conf.override(config_args)
    conf.validate()

    runtime = RuntimeOptions()
    runtime.override(runtime_args)

    stop_event = Event()
    kill_event = Event()
    logger = log.update_logger(args.debug)
    signal.signal(signal.SIGINT, make_sigint_handler(logger, stop_event, kill_event))

    if args.monitor:
        logger.info("Monitoring enabled - use CTRL-C to stop monitoring.")
        logger.info(
            "Note that queued replays are still rendered; CTRL-C again to kill."
        )

    collector = Collector(
        inputs=args.inputs,
        stop_event=stop_event,
        monitor=runtime.monitor,
        workdir=runtime.temporary_directory_path,
    )

    orchestrator = Orchestrator(
        conf=conf,
        kill_event=kill_event,
        collector=collector,
        combine_mode=runtime.combine_mode_enum,
        dry_run=runtime.dry_run,
        workdir=runtime.temporary_directory_path,
        output_directory=runtime.output_directory_path,
        debug=runtime.debug,
    )
    orchestrator.run()


if __name__ == "__main__":
    main()
