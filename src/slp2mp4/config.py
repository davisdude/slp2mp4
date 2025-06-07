# Handles configuration options

import dataclasses
import importlib.resources
import os
import pathlib
import tomllib
import typing

import slp2mp4
import slp2mp4.util as util

DEFAULT_CONFIG_FILE = importlib.resources.files(slp2mp4).joinpath("defaults.toml")
USER_CONFIG_FILE = pathlib.Path("~/.slp2mp4.toml").expanduser()


def _path(p):
    return pathlib.Path(p).expanduser()


def _parse_resolution(r):
    resolutions = {"480p": "2", "720p": "3", "1080p": "5", "1440p": "6", "2160p": "8"}
    return resolutions[r]


def _parse_parallel(p):
    return os.cpu_count() if (p == 0) else p


CONSTRUCTORS = {
    "paths": {
        "ffmpeg": _path,
        "slippi_playback": _path,
        "ssbm_ini": _path,
    },
    "dolphin": {
        "resolution": _parse_resolution,
        "bitrate": str,
        "volume": str,
    },
    "runtime": {
        "parallel": _parse_parallel,
    },
}


def _apply_constructors(conf: dict, constructors: dict):
    for k, constructor in constructors.items():
        if isinstance(constructor, typing.Callable):
            conf[k] = constructor(conf[k])
        elif isinstance(constructor, dict):
            _apply_constructors(conf[k], constructor)


def _load_configs(config_files: [pathlib.Path]) -> dict:
    # TODO: Try open; skip if not found
    conf = {}
    for file in config_files:
        try:
            with open(file, "rb") as f:
                data = tomllib.load(f)
                util.update_dict(conf, data)
        except FileNotFoundError:
            print(f"Could not find config file {file} - skipping")
    _apply_constructors(conf, CONSTRUCTORS)
    return conf


def get_config():
    return _load_configs([DEFAULT_CONFIG_FILE, USER_CONFIG_FILE])
