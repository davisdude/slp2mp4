import io
import logging
import tkinter as tk


class TkStream(io.StringIO):
    def __init__(self, textobj: tk.Text, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.textobj = textobj

    def write(self, s):
        super().write(s)
        new_text = self.read()
        self.textobj.insert(tk.END, s)
        self.textobj.see(tk.END)


# Only call this from bin scripts
def update_logger(debug=False):
    logger = logging.getLogger("slp2mp4")
    logger.setLevel(logging.DEBUG)
    stream = logging.StreamHandler()
    # TODO: Configurable log-level
    stream.setLevel(logging.INFO)
    if debug:
        formatter = logging.Formatter(
            "%(asctime)s|%(filename)s.%(lineno)s|%(levelname)s: %(message)s"
        )
        stream.setFormatter(formatter)
    logger.addHandler(stream)
    return logger


def get_logger():
    return logging.getLogger("slp2mp4")
