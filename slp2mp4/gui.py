# GUI frontend

import dataclasses
import tkinter as tk
import typing
from enum import Enum
from pathlib import Path
from tkinter import filedialog, ttk

import tomli_w

from slp2mp4 import config, util
from slp2mp4.config import DolphinBackend, DolphinResolution

try:
    from slp2mp4 import version

    __version__ = version.version
except ImportError:
    __version__ = "0.0.0+dev"


def enum_display_values(enum_type):
    return [enum_to_display(member) for member in enum_type]


def enum_to_display(enum_value):
    return getattr(enum_value, "display_name", enum_value.value)


def build_dataclass(variables, parent, obj, prefix=None):
    row = 0
    for field in dataclasses.fields(obj):
        value = getattr(obj, field.name)
        key = (prefix or ()) + (field.name,)
        ttk.Label(parent, text=field.name.replace("_", " ").title()).grid(
            row=row, column=0, sticky="w"
        )
        widget = build_widget(
            variables=variables, parent=parent, key=key, value=value, field_type=field.type
        )
        widget.grid(row=row, column=1, sticky="ew")
        row += 1

        if (metadata := getattr(field, "metadata")):
            if (help_text := metadata.get("help")):
                label = ttk.Label(parent, text=help_text, foreground="gray40")
                label.grid(row=row, column=0, columnspan=2, sticky="w")
                row += 1


def get_optional_type(field_type):
    # Assumes Unions are [X, None]
    args = typing.get_args(field_type)
    return list(filter(lambda x: x is not None, args))[0]


def is_dict_of_type(d, t):
    return isinstance(d, dict) and all(isinstance(v, t) for v in d.values())


def build_widget(variables, parent, key, value, field_type):
    if typing.get_origin(field_type) is typing.Union:
        field_type = get_optional_type(field_type)
        default_value = None
        if (field_type is Path) or (field_type is str):
            default_value = ""
        value = value if (value is not None) else default_value
        return build_widget(variables, parent, key, value, field_type)
    elif field_type is bool:
        var = tk.BooleanVar(value=value)
        widget = ttk.Checkbutton(parent, variable=var)
    elif isinstance(value, Enum):
        enum_type = type(value)
        options = enum_display_values(enum_type)
        var = tk.StringVar(value=enum_to_display(value))
        widget = ttk.Combobox(parent, textvariable=var, values=options, state="readonly")
    elif field_type is int:
        # TODO: Spinners for some with min/max
        var = tk.IntVar(value=value)
        widget = ttk.Entry(parent, textvariable=var)
    elif field_type is Path:
        var = tk.StringVar(value=str(value))
        widget = create_path_widget(parent, var)
    elif is_dict_of_type(value, bool):
        return create_bool_dict_widget(variables, parent, key, value)
    elif is_dict_of_type(value, str):
        return create_str_dict_widget(variables, parent, key, value)
    else:
        var = tk.StringVar(value=str(value))
        widget = ttk.Entry(parent, textvariable=var)
    variables[key] = var
    return widget


def create_path_widget(parent, var):
    frame = ttk.Frame(parent)
    ttk.Entry(frame, textvariable=var).pack(side="left", fill="x", expand=True)
    button = ttk.Button(frame, text="Browse", command=lambda: browse_path(var))
    button.pack(side="left")
    return frame


def browse_path(var):
    filename = filedialog.askopenfilename()
    if filename:
        var.set(filename)

def create_bool_dict_widget(variables, parent, prefix, values):
    frame = ttk.Frame(parent)
    for row, (name, enabled) in enumerate(values.items()):
        var = tk.BooleanVar(value=enabled)
        ttk.Checkbutton(frame, text=name, variable=var).grid(
            row=row, column=0, sticky="w"
        )
        key = (prefix or ()) + (name,)
        variables[key] = var
    return frame

def create_str_dict_widget(variables, parent, prefix, values):
    frame = ttk.Frame(parent)
    for row, (name, value) in enumerate(values.items()):
        var = tk.StringVar(value=value)
        ttk.Entry(frame, textvariable=var).grid(row=row, column=0, sticky="w")
        key = (prefix or ()) + (name,)
        variables[key] = var
    return frame


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
            build_dataclass(self.variables, frame, section_obj, prefix=(section_name,))
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

        backend = data["dolphin"]["backend"]
        data["dolphin"]["backend"] = DolphinBackend(backend).value
        res = data["dolphin"]["resolution"]
        data["dolphin"]["resolution"] = DolphinResolution.from_display_name(res).display_name
        if data["paths"]["ffprobe"].strip() == "":
            data["paths"]["ffprobe"] = None

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
            if isinstance(var, tk.StringVar):
                var.set(current or "")
            else:
                var.set(current)


class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"slp2mp4 {__version__}")
        self.create_menu()
        self.inputs = []
        self.variables: dict[str, tk.Variable] = {}
        self.runtime_options = config.RuntimeOptions()

        self.make_input_selector()
        self.make_runtime_options()

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

    def make_input_selector(self):
        frame = ttk.LabelFrame(self, text="Inputs")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.listbox = tk.Listbox(frame, selectmode=tk.EXTENDED, height=10)
        self.listbox.pack(fill="both", expand=True)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")

        ttk.Button(buttons, text="Add Files", command=self.add_files).pack(side="left")
        ttk.Button(buttons, text="Add Directory", command=self.add_directory).pack(side="left")
        ttk.Button(buttons, text="Remove", command=self.remove_selected).pack(side="left")
        ttk.Button(buttons, text="Clear All", command=self.clear_all).pack(side="left")

    def make_runtime_options(self):
        frame = ttk.LabelFrame(self, text="Runtime")
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        build_dataclass(self.variables, frame, self.runtime_options, prefix=())

    def add_files(self):
        filenames = filedialog.askopenfilenames()
        for filename in filenames:
            path = Path(filename)
            if path not in self.inputs:
                self.inputs.append(path)
                self.listbox.insert(tk.END, filename)

    def add_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            path = Path(directory)
            if path not in self.inputs:
                self.inputs.append(path)
                self.listbox.insert(tk.END, directory)

    def remove_selected(self):
        indices = reversed(self.listbox.curselection())
        for index in indices:
            del self.inputs[index]
            self.listbox.delete(index)

    def clear_all(self):
        self.inputs.clear()
        self.listbox.delete(0, tk.END)


def main():
    app = Application()
    app.mainloop()


if __name__ == "__main__":
    main()
