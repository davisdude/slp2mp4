# GUI frontend

import dataclasses
from enum import Enum
from multiprocessing import Event
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog

import tomli_w
from slp2mp4 import config
from slp2mp4 import util

try:
    from slp2mp4 import version

    __version__ = version.version
except ImportError:
    __version__ = "0.0.0+dev"


def enum_display_values(enum_type):
    return [enum_to_display(member) for member in enum_type]


def enum_to_display(enum_value):
    return getattr(enum_value, "display_name", enum_value.value)


class ConfigDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("slp2mp4 configuration")
        self.config_data = config.get_config()
        self.variables: dict[str, tk.Variable] = {}

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

        self.create_widgets()

    def create_widgets(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        for section_field in dataclasses.fields(self.config_data):
            section_name = section_field.name
            section_obj = getattr(self.config_data, section_name)
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=section_name)
            self.build_dataclass(frame, section_obj, prefix=(section_name,))
            frame.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(self)
        button_frame.pack(fill="both", padx=10, pady=10)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(button_frame, text="Save", command=self.save).pack(side="left")
        ttk.Button(button_frame, text="Reset", command=self.reset).pack(side="left")

    def save(self):
        data = self.config_data.to_dict()
        for key, var in self.variables.items():
            current = data
            for part in key[:-1]:
                current = current[part]
            current[key[-1]] = var.get()

        data["dolphin"]["backend"] = config.DolphinBackend(
            data["dolphin"]["backend"]
        ).value
        data["dolphin"]["resolution"] = config.DolphinResolution.from_display_name(
            data["dolphin"]["resolution"]
        ).display_name

        config_path = Path(config.USER_CONFIG_PATH).expanduser()
        defaults = config.get_default_config().to_dict()
        unique_items = util.get_unique_items(defaults, data)
        # TODO: Exception catching / logging
        with open(config_path, "wb") as f:
            tomli_w.dump(unique_items, f)
        self.destroy()

    def reset(self):
        self.config_data = config.get_default_config()
        data = self.config_data.to_dict()
        for key, var in self.variables.items():
            current = data
            for part in key:
                current = current[part]
            var.set(current)

    def build_dataclass(self, parent, obj, prefix=None):
        for row, field in enumerate(dataclasses.fields(obj)):
            value = getattr(obj, field.name)
            key = (prefix or ()) + (field.name,)
            ttk.Label(parent, text=field.name.replace("_", " ")).grid(
                row=row, column=0, sticky="w"
            )
            widget = self.build_widget(
                parent=parent, key=key, value=value, field_type=field.type
            )
            widget.grid(row=row, column=1, sticky="ew")

    def build_widget(self, parent, key, value, field_type):
        if field_type is bool:
            var = tk.BooleanVar(value=value)
            widget = ttk.Checkbutton(parent, variable=var)
        elif isinstance(value, Enum):
            enum_type = type(value)
            options = enum_display_values(enum_type)
            var = tk.StringVar(value=enum_to_display(value))
            widget = ttk.Combobox(
                parent, textvariable=var, values=options, state="readonly"
            )
        elif field_type is int:
            # TODO: Spinners for some with min/max
            var = tk.IntVar(value=value)
            widget = ttk.Entry(parent, textvariable=var)
        elif field_type is Path:
            var = tk.StringVar(value=str(value))
            widget = self.create_path_widget(parent, var)
        elif isinstance(value, dict) and all(
            isinstance(v, bool) for v in value.values()
        ):
            return self.create_bool_dict_widget(parent, key, value)
        elif isinstance(value, dict) and all(
            isinstance(v, str) for v in value.values()
        ):
            return self.create_str_dict_widget(parent, key, value)
        else:
            var = tk.StringVar(value=str(value))
            widget = ttk.Entry(parent, textvariable=var)
        self.variables[key] = var
        return widget

    def create_path_widget(self, parent, var):
        frame = ttk.Frame(parent)
        entry = ttk.Entry(frame, textvariable=var).pack(
            side="left", fill="x", expand=True
        )
        button = ttk.Button(
            frame, text="Browse", command=lambda: self.browse_path(var)
        ).pack(side="left")
        return frame

    def browse_path(self, var):
        filename = filedialog.askopenfilename()
        if filename:
            var.set(filename)

    def create_bool_dict_widget(self, parent, prefix, values):
        frame = ttk.Frame(parent)
        for row, (name, enabled) in enumerate(values.items()):
            var = tk.BooleanVar(value=enabled)
            ttk.Checkbutton(frame, text=name, variable=var).grid(
                row=row, column=0, sticky="w"
            )
            key = (prefix or ()) + (name,)
            self.variables[key] = var
        return frame

    def create_str_dict_widget(self, parent, prefix, values):
        frame = ttk.Frame(parent)
        for row, (name, value) in enumerate(values.items()):
            var = tk.StringVar(value=value)
            ttk.Entry(frame, textvariable=var).grid(row=row, column=0, sticky="w")
            key = (prefix or ()) + (name,)
            self.variables[key] = var
        return frame


class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"slp2mp4 {__version__}")
        self.create_menu()

    def create_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        # File
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        # Settings
        settings_menu = tk.Menu(menubar, tearoff=False)
        settings_menu.add_command(label="Settings", command=self.show_config_dialog)
        menubar.add_cascade(label="Configure", menu=settings_menu)

    def show_config_dialog(self):
        dialog = ConfigDialog(self)
        self.wait_window(dialog)


def main():
    app = Application()
    app.mainloop()


if __name__ == "__main__":
    main()
