# Handles configuration options

import importlib.resources
import os
import pathlib
import shutil
import tomllib
import typing

import slp2mp4
import slp2mp4.util as util
import slp2mp4.scoreboard as scoreboard

DEFAULT_CONFIG_FILE = importlib.resources.files(slp2mp4).joinpath("defaults.toml")
USER_CONFIG_FILE = pathlib.Path("~/.slp2mp4.toml").expanduser()

# https://github.com/project-slippi/Ishiiruka/blob/3e5b185ae080e8dca5e939369572d94d20049fea/Source/Core/VideoCommon/VideoConfig.h#L40
# https://github.com/project-slippi/Ishiiruka/blob/3e5b185ae080e8dca5e939369572d94d20049fea/Source/Core/DolphinWX/VideoConfigDiag.cpp#L450
RESOLUTIONS = {
    "480p": "2",
    "720p": "3",
    "1080p": "5",
    "1440p": "6",
    "2160p": "8",
}
RESOLUTIONS_LOOKUP = {v: k for k, v in RESOLUTIONS.items()}

# From https://github.com/project-slippi/Ishiiruka/tree/slippi/Source/Core/VideoBackends
DOLPHIN_BACKENDS = [
    "D3D12",
    "DX11",
    "DX9",
    "OGL",
    "Software Renderer",
    "Vulkan",
]


def _parse_to_type(string, totype):
    try:
        return True, totype(string)
    except ValueError:
        return False, string


def _parse_file_path(path_str):
    path = pathlib.Path(path_str).expanduser()
    return (path.exists() and path.is_file(), path)


def _parse_file_path_or_none(path_str):
    path = pathlib.Path(path_str).expanduser() if path_str != "" else None
    return ((path is None) or (path.exists() and path.is_file()), path)


def _parse_bin_path(path_str):
    status, path = _parse_file_path(path_str)
    if status and path.is_absolute():
        return (status, path)
    path = shutil.which(str(path))
    return (bool(path), path)


def _parse_from_dict(key, dictionary):
    return (key in dictionary, dictionary.get(key))


def _parse_from_list(key, input_list):
    return (key in input_list, key)


def _parse_int(int_str):
    # Convert to string first to catch int -> floats
    return _parse_to_type(str(int_str), int)


def _parse_bool(bool_str):
    return (isinstance(bool_str, bool), bool_str)


def _parse_str(str_str):
    return _parse_to_type(str_str, str)


def _parse_dict(replacements):
    return (isinstance(replacements, dict), replacements)


def _parse_backend(backend):
    return _parse_from_list(backend, DOLPHIN_BACKENDS)


def _parse_resolution(resolution):
    return _parse_from_dict(resolution, RESOLUTIONS)


def _parse_scoreboard_type(sb_type):
    return _parse_from_dict(sb_type, scoreboard.SCOREBOARDS)


def _parse_parallel(parallel):
    status, count = _parse_int(parallel)
    return (status, os.cpu_count() if count == 0 else count)


_TRANSFORMERS = {
    "paths": {
        "ffmpeg": _parse_bin_path,
        "slippi_playback": _parse_file_path,
        "ssbm_iso": _parse_file_path,
    },
    "dolphin": {
        "backend": _parse_backend,
        "resolution": _parse_resolution,
        "bitrate": _parse_int,
    },
    "ffmpeg": {
        "audio_args": _parse_str,
        "volume": _parse_int,
    },
    "runtime": {
        "parallel": _parse_parallel,
        "prepend_directory": _parse_bool,
        "preserve_directory_structure": _parse_bool,
        "youtubify_names": _parse_bool,
        "name_replacements": _parse_dict,
        "debug": _parse_bool,
    },
    "scoreboard": {
        "type": _parse_scoreboard_type,
        "default": {
            "logo_path": _parse_file_path_or_none,
        },
    },
}


def _apply_constructors(conf: dict, constructors: dict, path=pathlib.Path(".")):
    for k, constructor in constructors.items():
        new_path = path / k
        if isinstance(constructor, typing.Callable):
            success, value = constructor(conf[k])
            assert (
                success
            ), f"Config: Invalid value for {('.').join(new_path.parts)}: '{conf[k]}'"
            conf[k] = value
        elif isinstance(constructor, dict):
            _apply_constructors(conf[k], constructor, new_path)


def _load_configs(config_files: [pathlib.Path]) -> dict:
    conf = {}
    for file in config_files:
        try:
            with open(file, "rb") as f:
                data = tomllib.load(f)
                util.update_dict(conf, data)
        except FileNotFoundError:
            print(f"Could not find config file {file} - skipping")
        except tomllib.TOMLDecodeError:
            print(f"Invalid toml in file {file} - skipping")
    return conf


def get_default_config():
    return _load_configs([DEFAULT_CONFIG_FILE])


def get_config():
    return _load_configs([DEFAULT_CONFIG_FILE, USER_CONFIG_FILE])


def translate_and_validate_config(conf):
    _apply_constructors(conf, _TRANSFORMERS)


# NOTE: dolphin outputs the first scaled size that *exceeds* the specified
# resolution, so this won't match the actual output height without downscaling
# Assumes `conf` has been translated
def get_expected_height(conf):
    res_str = RESOLUTIONS_LOOKUP[conf["dolphin"]["resolution"]]
    return int(res_str.removesuffix("p"))
