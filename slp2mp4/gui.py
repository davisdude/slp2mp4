# GUI frontend

import dataclasses
import threading
import tkinter as tk
import webbrowser
from enum import Enum
from multiprocessing import Event
from pathlib import Path
from tkinter import filedialog, scrolledtext, ttk

import tomli_w

from slp2mp4 import config, log, util
from slp2mp4.collector import Collector
from slp2mp4.config import DolphinBackend, DolphinResolution
from slp2mp4.orchestrator import Orchestrator

try:
    from slp2mp4 import version

    __version__ = version.version
except ImportError:
    __version__ = "0.0.0+dev"


HOME_PAGE = "https://github.com/davisdude/slp2mp4"
LICENSE_PAGE = f"{HOME_PAGE}/blob/master/LICENSE.md"


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
            variables=variables,
            parent=parent,
            key=key,
            value=value,
            field=field,
        )
        widget.grid(row=row, column=1, sticky="ew")
        row += 1

        if (metadata := field.metadata) and (help_text := metadata.get("help")):
            label = ttk.Label(parent, text=help_text, foreground="gray40")
            label.grid(row=row, column=0, columnspan=2, sticky="w")
            row += 1


def is_dict_of_type(d, t):
    return isinstance(d, dict) and all(isinstance(v, t) for v in d.values())


def build_widget(variables, parent, key, value, field):
    if config.is_optional_type(field.type):
        field.type = config.get_optional_type(field.type)
        default_value = None
        if (field.type is Path) or (field.type is str):
            default_value = ""
        value = value if (value is not None) else default_value
        return build_widget(variables, parent, key, value, field)
    elif field.type is bool:
        var = tk.BooleanVar(value=value)
        widget = ttk.Checkbutton(parent, variable=var)
    elif isinstance(value, Enum):
        enum_type = type(value)
        options = enum_display_values(enum_type)
        var = tk.StringVar(value=enum_to_display(value))
        widget = ttk.Combobox(
            parent, textvariable=var, values=options, state="readonly"
        )
    elif field.type is int:
        # TODO: Spinners for some with min/max
        var = tk.IntVar(value=value)
        widget = ttk.Entry(parent, textvariable=var)
    elif field.type is Path:
        var = tk.StringVar(value=str(value))
        is_directory = field.metadata.get("is_directory")
        widget = create_path_widget(parent, var, is_directory)
    elif is_dict_of_type(value, bool):
        return create_bool_dict_widget(variables, parent, key, value)
    elif is_dict_of_type(value, str):
        return create_str_dict_widget(variables, parent, key, value)
    else:
        var = tk.StringVar(value=str(value))
        widget = ttk.Entry(parent, textvariable=var)
    variables[key] = var
    return widget


def create_path_widget(parent, var, is_dir):
    frame = ttk.Frame(parent)
    ttk.Entry(frame, textvariable=var).pack(side="left", fill="x", expand=True)
    button = ttk.Button(frame, text="Browse", command=lambda: browse_path(var, is_dir))
    button.pack(side="left")
    return frame


def browse_path(var, is_dir):
    if is_dir:
        path = filedialog.askdirectory()
    else:
        path = filedialog.askopenfilename()
    if path:
        var.set(path)


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
        self.log = log.get_logger()

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
        data["dolphin"]["resolution"] = DolphinResolution.from_display_name(
            res
        ).display_name
        if data["paths"]["ffprobe"].strip() == "":
            data["paths"]["ffprobe"] = None

        config_path = Path(config.USER_CONFIG_PATH).expanduser()
        defaults = config.get_default_config().to_dict()
        unique_items = util.get_unique_items(defaults, data)
        try:
            with open(config_path, "wb") as f:
                tomli_w.dump(unique_items, f)
        except Exception as e:  # noqa: BLE001
            self.log.error(f"Error saving TOML: {e}")
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


class AboutDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("slp2mp4 info")

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

        self.create_widgets()

    def create_widgets(self):
        frame = ttk.LabelFrame(self, text="About")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Version").grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text=__version__).grid(row=0, column=1, sticky="w")

        ttk.Label(frame, text="Hopepage").grid(row=1, column=0, sticky="w")
        link = ttk.Label(frame, text=HOME_PAGE, foreground="blue", cursor="hand2")
        link.grid(row=1, column=1, sticky="w")
        link.bind("<Button-1>", lambda _: webbrowser.open(HOME_PAGE))

        ttk.Label(frame, text="License").grid(row=2, column=0, sticky="w")
        link = ttk.Label(frame, text=LICENSE_PAGE, foreground="blue", cursor="hand2")
        link.grid(row=2, column=1, sticky="w")
        link.bind("<Button-1>", lambda _: webbrowser.open(LICENSE_PAGE))


class Application(tk.Tk):
    def __init__(self, logger=None):
        super().__init__()
        self.title("slp2mp4")
        self.create_menu()
        self.inputs = []
        self.variables: dict[str, tk.Variable] = {}
        self.runtime_options = config.RuntimeOptions()
        self.kill_event = Event()

        self.make_input_selector()
        self.make_runtime_options()
        self.make_actions()
        self.make_log_text()
        self.log = logger or log.update_logger(False, self.log_text)

    def create_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="Menu", menu=file_menu)
        file_menu.add_command(label="Configure", command=self.show_config_dialog)
        file_menu.add_command(label="About", command=self.show_about_dialog)
        file_menu.add_command(label="Exit", command=self.destroy)

    def show_config_dialog(self):
        dialog = ConfigDialog(self)
        self.wait_window(dialog)

    def show_about_dialog(self):
        dialog = AboutDialog(self)
        self.wait_window(dialog)

    def make_input_selector(self):
        frame = ttk.LabelFrame(self, text="Inputs")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.listbox = tk.Listbox(frame, selectmode=tk.EXTENDED, height=5)
        self.listbox.pack(fill="both", expand=True)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")

        ttk.Button(buttons, text="Add Files", command=self.add_files).pack(side="left")
        ttk.Button(buttons, text="Add Directory", command=self.add_directory).pack(
            side="left"
        )
        ttk.Button(buttons, text="Remove", command=self.remove_selected).pack(
            side="left"
        )
        ttk.Button(buttons, text="Clear All", command=self.clear_all).pack(side="left")

    def make_runtime_options(self):
        frame = ttk.LabelFrame(self, text="Runtime")
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        build_dataclass(self.variables, frame, self.runtime_options, prefix=())

    def make_actions(self):
        frame = ttk.LabelFrame(self, text="Actions")
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        ttk.Button(frame, text="Run", command=self.run).pack(side="left")
        ttk.Button(frame, text="Stop", command=self.stop).pack(side="left")

    def make_log_text(self):
        self.log_text = scrolledtext.ScrolledText(self, height=10, wrap=tk.WORD)
        self.log_text.pack(fill="both", expand=True)

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

    def run(self):
        # TODO: Output directory
        debug = self.variables[("debug",)].get()
        self.log = log.update_logger(debug, self.log_text)
        self.log.debug("Debug")

        self.kill_event.clear()
        conf = config.get_config()
        conf.validate()
        workdir = self.variables[("temporary_directory",)].get()
        if workdir.strip() != "":
            workdir = Path(workdir)
        else:
            workdir = None

        collector = Collector(
            inputs=self.inputs,
            kill_event=self.kill_event,
            monitor=self.variables[("monitor",)].get(),
            workdir=workdir,
        )

        orchestrator = Orchestrator(
            conf=conf,
            kill_event=self.kill_event,
            collector=collector,
            dry_run=self.variables[("dry_run",)].get(),
            workdir=workdir,
            output_directory=Path(self.variables[("output_directory",)].get()),
        )
        threading.Thread(target=orchestrator.run).start()

    def stop(self):
        self.kill_event.set()


def main():
    app = Application()
    app.mainloop()


if __name__ == "__main__":
    main()
