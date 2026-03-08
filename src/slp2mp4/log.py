from __future__ import annotations

import io
import logging

__TK_FOUND = True
try:
    import tkinter as tk
except (ImportError, ModuleNotFoundError):
    __TK_FOUND = False

class TkStream(io.StringIO):
    def __init__(self, textobj: "tk.Text", *args, **kwargs):
        if not __TK_FOUND:
            return
        super().__init__(*args, **kwargs)
        self.textobj = textobj

    def write(self, s):
        if not __TK_FOUND:
            return
        super().write(s)
        new_text = self.read()
        self.textobj.insert("end", s)
        self.textobj.see("end")


# Only call this from bin scripts
def update_logger(debug=False, tk_log_text=None):
    logger = logging.getLogger("slp2mp4")
    logger.handlers.clear()

    level = logging.DEBUG if debug else logging.INFO
    logger.setLevel(level)

    debug_formatter = logging.Formatter(
        "%(asctime)s|%(filename)s.%(lineno)s|%(levelname)s: %(message)s"
    )
    formatter = debug_formatter if debug else None

    stdout_stream = logging.StreamHandler()
    stdout_stream.setFormatter(formatter)
    logger.addHandler(stdout_stream)

    if tk_log_text and __TK_FOUND:
        tk_stream = logging.StreamHandler(TkStream(tk_log_text))
        tk_stream.setFormatter(formatter)
        logger.addHandler(tk_stream)

    return logger


def get_logger():
    return logging.getLogger("slp2mp4")
