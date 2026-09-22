import dataclasses
import signal
from argparse import ArgumentParser
from multiprocessing import Event
from pathlib import Path

from slp2mp4 import config, log
from slp2mp4.config import RuntimeOptions
from slp2mp4.orchestrator import Orchestrator


def make_sigint_handler(logger, event: Event):
    def func(_sig, _frame):
        logger.info("Got sigint - stopping")
        event.set()

    return func


def main():
    parser = ArgumentParser()
    parser.add_argument("inputs", type=Path, nargs="+")
    for field in dataclasses.fields(RuntimeOptions):
        field_type = field.type
        kwargs = {}
        metadata = getattr(field, "metadata", {})
        if default := field.default:
            kwargs["default"] = default
        if help_text := metadata.get("help"):
            kwargs["help"] = help_text
        if config.is_optional_type(field_type):
            field_type = config.get_optional_type(field_type)
        if (field_type is bool) and (default is not None):
            kwargs["action"] = "store_false" if default else "store_true"
        else:
            kwargs["type"] = field_type
        name = field.name.replace("_", "-")
        args = []
        if short := metadata.get("short"):
            args.append(f"-{short}")
        args.append(f"--{name}")
        parser.add_argument(*args, **kwargs)
    args = parser.parse_args()

    kill_event = Event()
    conf = config.get_config()
    logger = log.update_logger(args.debug)

    signal.signal(signal.SIGINT, make_sigint_handler(logger, kill_event))

    orchestrator = Orchestrator(
        inputs=args.inputs,
        conf=conf,
        kill_event=kill_event,
        monitor=args.monitor,
        dry_run=args.dry_run,
        workdir=args.temporary_directory,
    )
    orchestrator.run()


if __name__ == "__main__":
    main()
