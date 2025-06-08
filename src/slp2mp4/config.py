# Handles configuration options

import importlib.resources
import os
import pathlib
import shutil
import tomllib
import typing

import slp2mp4
import slp2mp4.util as util

DEFAULT_CONFIG_FILE = importlib.resources.files(slp2mp4).joinpath("defaults.toml")
USER_CONFIG_FILE = pathlib.Path("~/.slp2mp4.toml").expanduser()

RESOLUTIONS = {"480p": "2", "720p": "3", "1080p": "5", "1440p": "6", "2160p": "8"}

DOLPHIN_BACKENDS = ["OGL", "D3D", "D3D12", "Vulkan", "Software"]


def _path(p):
    return pathlib.Path(p).expanduser()


def _parse_resolution(r):
    return RESOLUTIONS[r]


def _get_cpus():
    return len(os.sched_getaffinity(0))


def _parse_parallel(p):
    return max(_get_cpus() - 1, 1) if (p == 0) else p


CONSTRUCTORS = {
    "paths": {
        "ffmpeg": _path,
        "slippi_playback": _path,
        "ssbm_iso": _path,
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
    conf = {}
    for file in config_files:
        try:
            with open(file, "rb") as f:
                data = tomllib.load(f)
                util.update_dict(conf, data)
        except FileNotFoundError:
            print(f"Could not find config file {file} - skipping")
    return conf


def get_default_config():
    return _load_configs([DEFAULT_CONFIG_FILE])


def get_config():
    return _load_configs([DEFAULT_CONFIG_FILE, USER_CONFIG_FILE])


def translate_config(conf):
    _apply_constructors(conf, CONSTRUCTORS)


def validate_config(conf):
    # Paths
    if not shutil.which(conf["paths"]["ffmpeg"]):
        raise RuntimeError(f"Could not find ffmpeg; path={conf['paths']['ffmpeg']}")
    if not pathlib.Path(conf["paths"]["slippi_playback"]).exists():
        raise RuntimeError(
            f"Could not find slippi playback; path={conf['paths']['slippi_playback']}"
        )
    if not pathlib.Path(conf["paths"]["ssbm_iso"]).exists():
        raise RuntimeError(f"Could not find ssbm iso; path={conf['paths']['ssbm_iso']}")

    # Dolphin
    if conf["dolphin"]["backend"] not in DOLPHIN_BACKENDS:
        raise RuntimeError(
            f"Invalid dolphin.backend '{conf['dolphin']['backend']}'; must be one of {DOLPHIN_BACKENDS}"
        )
    if conf["dolphin"]["resolution"] not in RESOLUTIONS.keys():
        raise RuntimeError(
            f"Invalid dolphin.resolution '{conf['dolphin']['resolution']}'; must be one of {list(RESOLUTIONS.keys())}"
        )
    try:
        int(str(conf["dolphin"]["bitrate"]))
    except ValueError:
        raise RuntimeError(
            f"Invalid dolphin.bitrate '{conf['dolphin']['bitrate']}'; must be an integer"
        )
    try:
        volume = int(str(conf["dolphin"]["volume"]))
        if not (0 <= volume <= 100):
            raise ValueError
    except ValueError:
        raise RuntimeError(
            f"Invalid dolphin.volume '{conf['dolphin']['volume']}'; must be an integer [0-100]"
        )

    # Runtime
    max_cpus = _get_cpus()
    try:
        cpus = int(str(conf["runtime"]["parallel"]))
        if not (0 <= cpus <= max_cpus):
            raise ValueError
    except ValueError:
        raise RuntimeError(
            f"Invalid runtime.parallel '{conf['runtime']['parallel']}'; must be an integer [0-{max_cpus}]"
        )
    try:
        bool(conf["runtime"]["prepend_directory"])
    except ValueError:
        raise RuntimeError(
            f"Invalid runtime.prepend_directory '{conf['runtime']['prepend_directory']}'; must be true/false"
        )
    try:
        bool(conf["runtime"]["youtubify_names"])
    except ValueError:
        raise RuntimeError(
            f"Invalid runtime.youtubify_names '{conf['runtime']['youtubify_names']}'; must be true/false"
        )
