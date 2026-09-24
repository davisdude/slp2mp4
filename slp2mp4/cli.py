import dataclasses
import signal
from argparse import ArgumentParser, BooleanOptionalAction
from multiprocessing import Event
from pathlib import Path

from slp2mp4 import config, log
from slp2mp4.config import Config, RuntimeOptions
from slp2mp4.orchestrator import Orchestrator

try:
    from slp2mp4 import version

    __version__ = version.version
except ImportError:
    __version__ = "0.0.0+dev"


def make_sigint_handler(logger, event: Event):
    def func(_sig, _frame):
        logger.info("Got sigint - stopping")
        event.set()

    return func


def add_config_option_to_parser(parser, config_type, prefix=""):
    for field in dataclasses.fields(config_type):
        field_type = field.type
        kwargs = {}
        metadata = getattr(field, "metadata", {})
        if (default := field.default) is not None:
            kwargs["default"] = default
        if help_text := metadata.get("help"):
            kwargs["help"] = help_text
        if config.is_optional_type(field_type):
            field_type = config.get_optional_type(field_type)
        if field_type is bool:
            if (default is True) or (default is False):
                kwargs["action"] = "store_false" if default else "store_true"
            else:
                kwargs["action"] = BooleanOptionalAction
        else:
            kwargs["type"] = field_type
        name = field.name.replace("_", "-")
        args = []
        if short := metadata.get("short"):
            args.append(f"-{short}")
        long_name = f"--{prefix}-{name}" if prefix else f"--{name}"
        args.append(long_name)
        if field_type is not dict:
            parser.add_argument(*args, **kwargs)


def update_conf_from_args(args, conf):
    for top_field in dataclasses.fields(Config):
        prefix = top_field.name
        current = getattr(conf, top_field.name)
        for field in dataclasses.fields(top_field.type):
            name = field.name
            val = getattr(args, f"{prefix}_{name}")
            if val is not dataclasses.MISSING:
                setattr(current, name, val)


def main():
    parser = ArgumentParser(prog="slp2mp4")
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("-v", "--version", action="version", version=__version__)

    add_config_option_to_parser(parser, RuntimeOptions)
    for field in dataclasses.fields(Config):
        add_config_option_to_parser(parser, field.type, field.name)

    args = parser.parse_args()

    kill_event = Event()
    conf = config.get_config()
    conf.validate()
    logger = log.update_logger(args.debug)
    update_conf_from_args(args, conf)

    signal.signal(signal.SIGINT, make_sigint_handler(logger, kill_event))

    orchestrator = Orchestrator(
        inputs=args.inputs,
        conf=conf,
        kill_event=kill_event,
        monitor=args.monitor,
        dry_run=args.dry_run,
        workdir=args.temporary_directory,
        output_directory=args.output_directory,
    )
    orchestrator.run()


if __name__ == "__main__":
    main()
