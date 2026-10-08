# Misc. utilities

import ctypes
import os
import re
import sys
from datetime import datetime, tzinfo
from pathlib import Path


def update_dict(d1: dict, d2: dict):
    for k, v in d2.items():
        if isinstance(v, dict):
            if k not in d1:
                d1[k] = {}
            update_dict(d1[k], v)
        else:
            d1[k] = v


# https://stackoverflow.com/a/78930347/2238176
def natsort(s):
    a = re.split(r"(\d+)", str(s).casefold())
    a[1::2] = map(int, a[1::2])
    return a


# Like str.replace, but with a dict
def translate(string: str, mapping: dict[str, str]):
    for old, new in mapping.items():
        string = string.replace(old, new)
    return string


def get_unique_items(d1: dict, d2: dict):
    out = {}
    for k, v in d2.items():
        in_d1 = k in d1
        eq_d1 = in_d1 and (v == d1[k])
        if isinstance(v, dict) and in_d1:
            if isinstance(d1[k], dict):
                new = get_unique_items(d1[k], v)
                if new:
                    out[k] = new
            else:
                out[k] = v
        elif in_d1 and not eq_d1:
            out[k] = v
    return out


def split_by_blank_line(s):
    if not (stripped := s.strip()):
        return []
    return re.split(r"\r?\n\s*\n", stripped)


def enum_to_display(enum_value):
    return getattr(enum_value, "display_name", enum_value.value)


def get_enum_display_values(enum_type):
    return [enum_to_display(member) for member in enum_type]


# Workaround for pyinstaller
# https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application
def get_env(bundled=False):
    env = os.environ.copy()

    # Unfrozen means running standalone
    # If running bundled, we don't want these overrides
    # (`bundled` is set to true in build.yml)
    if not getattr(sys, "frozen", False) or bundled:
        return env

    if sys.platform == "win32":
        ctypes.windll.kernel32.SetDllDirectoryW(None)
    else:
        orig = env.pop("LD_LIBRARY_PATH_ORIG", None)
        if orig is None:
            env.pop("LD_LIBRARY_PATH", None)
        else:
            env["LD_LIBRARY_PATH"] = orig
    return env


def check_file(path: Path):
    p = path.expanduser().resolve()
    return p.is_file() and p.exists()


def unix_ms_to_datetime(time_ms: int, timezone: tzinfo):
    return datetime.fromtimestamp(time_ms / 1000, tz=timezone)
