# Misc. utilities

import pathlib
import re
import subprocess


def update_dict(d1: dict, d2: dict):
    for k, v in d2.items():
        if isinstance(v, dict):
            if k not in d1:
                d1[k] = {}
            update_dict(d1[k], d2[k])
        else:
            d1[k] = v


def flatten_arg_tuples(args):
    return [arg for arg_tuple in args for arg in arg_tuple]


# https://stackoverflow.com/a/78930347/2238176
def natsort(s):
    a = re.split(r"(\d+)", str(s).casefold())
    a[1::2] = map(int, a[1::2])
    return a


def get_parent_as_path(p):
    return pathlib.Path(p.absolute().parent.parts[-1])


# Like str.replace, but with a dict
def translate(string: str, mapping: dict[str, str]):
    for old, new in mapping.items():
        string = string.replace(old, new)
    return string
