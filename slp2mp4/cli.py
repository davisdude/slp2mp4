import dataclasses
import signal
import typing
from argparse import SUPPRESS, ArgumentParser, ArgumentTypeError, BooleanOptionalAction
from enum import Enum
from multiprocessing import Event
from pathlib import Path

from slp2mp4 import config, log, util
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


def enum_parser(enum_type, display_values):
    display_to_member = dict(zip(display_values, enum_type))

    def parse(value):
        try:
            return display_to_member[value]
        except KeyError:
            raise ArgumentTypeError(
                f"invalid value: {value!r}; choose from {', '.join(display_values)}"
            )

    return parse


def add_config_option_to_parser(
    parser, config_type, prefix="", help_most=True, help_all=False
):
    for field in dataclasses.fields(config_type):
        metadata = getattr(field, "metadata", {})
        kwargs = {}
        name = field.name.replace("_", "-")
        if dataclasses.is_dataclass(field.type):
            add_config_option_to_parser(
                parser, field.type, f"{prefix}-{name}", help_most, help_all
            )
            continue
        if (default := field.default) is not None:
            kwargs["default"] = default
        metavar = metadata.get("metavar")
        if (not help_all) and metadata.get("help_all", False) and not metavar:
            if metavar := metadata.get("help_all_metavar"):
                kwargs["metavar"] = metavar
            else:
                kwargs["help"] = SUPPRESS
        elif not help_most:
            kwargs["help"] = SUPPRESS
        elif help_text := metadata.get("help"):
            kwargs["help"] = help_text
        if config.is_optional_type(field.type):
            field.type = config.get_optional_type(field.type)
        if field.type is bool:
            if (default is True) or (default is False):
                kwargs["action"] = "store_false" if default else "store_true"
            else:
                kwargs["action"] = BooleanOptionalAction
        elif isinstance(field.type, type) and issubclass(field.type, Enum):
            display_values = util.get_enum_display_values(field.type)
            kwargs["type"] = enum_parser(field.type, display_values)
            kwargs["choices"] = list(field.type)
            if "metavar" not in kwargs:
                kwargs["metavar"] = "{" + ",".join(display_values) + "}"
        else:
            kwargs["type"] = field.type
        args = []
        if short := metadata.get("short"):
            args.append(f"-{short}")
        long_name = f"--{prefix}-{name}" if prefix else f"--{name}"
        args.append(long_name)
        not_dict = typing.get_origin(field.type) is not dict
        if not_dict and not metadata.get("multiline", False):
            parser.add_argument(*args, **kwargs)


def update_conf_from_args(args, conf, obj=None, prefix=""):
    if obj is None:
        obj = conf
    for field in dataclasses.fields(obj):
        value = getattr(obj, field.name)
        arg_name = f"{prefix}_{field.name}" if prefix else field.name
        if dataclasses.is_dataclass(value):
            update_conf_from_args(args, conf, value, arg_name)
            continue
        if not hasattr(args, arg_name):
            continue
        arg_value = getattr(args, arg_name)
        if (arg_value is not dataclasses.MISSING) and (arg_value is not None):
            setattr(obj, field.name, arg_value)


def make_parser(help_most=False, help_all=False):
    if help_all:
        help_most = True
    parser = ArgumentParser(prog="slp2mp4")
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--help-most", help="show most help", action="help")
    parser.add_argument("--help-all", help="show all help", action="help")
    parser.add_argument("-v", "--version", action="version", version=__version__)
    add_config_option_to_parser(parser, RuntimeOptions)
    for field in dataclasses.fields(Config):
        add_config_option_to_parser(parser, field.type, field.name, help_most, help_all)
    return parser


def main():
    initial = ArgumentParser(add_help=False)
    initial.add_argument("--help-most", action="store_true")
    initial.add_argument("--help-all", action="store_true")
    initial_args, _ = initial.parse_known_args()

    parser = make_parser(initial_args.help_most, initial_args.help_all)
    args = parser.parse_args()

    stop_event = Event()
    kill_event = Event()
    conf = config.get_config()
    logger = log.update_logger(args.debug)
    update_conf_from_args(args, conf)
    conf.validate()

    signal.signal(signal.SIGINT, make_sigint_handler(logger, stop_event, kill_event))

    if args.monitor:
        logger.info("Monitoring enabled - use CTRL-C to stop monitoring.")
        logger.info(
            "Note that queued replays are still rendered; CTRL-C again to kill."
        )

    collector = Collector(
        inputs=args.inputs,
        stop_event=stop_event,
        monitor=args.monitor,
        workdir=args.temporary_directory,
    )

    orchestrator = Orchestrator(
        conf=conf,
        kill_event=kill_event,
        collector=collector,
        combine_mode=args.combine_mode,
        dry_run=args.dry_run,
        workdir=args.temporary_directory,
        output_directory=args.output_directory,
        debug=args.debug,
    )
    orchestrator.run()


if __name__ == "__main__":
    main()
