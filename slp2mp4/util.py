# Misc. utilities

import re


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
