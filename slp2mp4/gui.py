# GUI frontend

import dataclasses
import math
import threading
import tkinter as tk
import webbrowser
from multiprocessing import Event, freeze_support
from pathlib import Path
from tkinter import filedialog, scrolledtext, ttk

import tomli_w

from slp2mp4 import config, log, util
from slp2mp4.collector import Collector
from slp2mp4.orchestrator import Orchestrator

try:
    from slp2mp4 import version

    __version__ = version.version
except ImportError:
    __version__ = "0.0.0+dev"


HOME_PAGE = "https://github.com/davisdude/slp2mp4"
LICENSE_PAGE = f"{HOME_PAGE}/blob/master/LICENSE.md"
FFMPEG_LICENSE_PATH = Path("_internal/lib/ffmpeg/LICENSE")
CHROME_ABOUT_PATH = Path("_internal/lib/chrome/ABOUT")


def build_notebook(variables, parent, config_data, prefix=None):
    if prefix is None:
        prefix = ()
    notebook = ttk.Notebook(parent)
    for section_field in dataclasses.fields(config_data):
        section_name = section_field.name
        section_obj = getattr(config_data, section_name)
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=section_name)
        new_prefix = prefix + (section_name,)
        add_config_option_to_gui(variables, frame, section_obj, prefix=new_prefix)
        frame.columnconfigure(1, weight=1)
    return notebook


def select_all(event):
    event.widget.tag_add("sel", "1.0", "end-1c")
    event.widget.mark_set(tk.INSERT, "1.0")
    event.widget.see(tk.INSERT)
    return "break"


@dataclasses.dataclass
class ScrolledTextwrapper:
    widget: scrolledtext.ScrolledText
    start: str

    def __post_init__(self):
        self.set(self.start)

    def get(self):
        return self.widget.get("1.0", tk.END)

    def set(self, s):
        self.widget.delete("1.0", tk.END)
        return self.widget.insert("1.0", s)


def add_config_option_to_gui(variables, parent, config_type, prefix=None, cols=1):
    if prefix is None:
        prefix = ()

    fields = dataclasses.fields(config_type)
    rows_per_column = math.ceil(len(fields) / cols)
    for i, field in enumerate(fields):
        row = 2 * (i % rows_per_column)
        col = 2 * math.floor(i / rows_per_column)
        value = getattr(config_type, field.name)
        new_prefix = prefix + (field.name,)
        if dataclasses.is_dataclass(value):
            widget = ttk.LabelFrame(parent, text=field.name.title())
            add_config_option_to_gui(
                variables, widget, value, prefix=new_prefix, cols=cols
            )
        else:
            label = ttk.Label(parent, text=field.name.replace("_", " ").title())
            label.grid(row=row, column=col, sticky="w")
            widget = build_widget(
                variables=variables,
                parent=parent,
                prefix=new_prefix,
                value=value,
                field=field,
            )
        widget.grid(row=row, column=col + 1, sticky="ew")
        if (metadata := field.metadata) and (help_text := metadata.get("help")):
            label = ttk.Label(parent, text=help_text, foreground="gray40")
            label.grid(row=row + 1, column=col, columnspan=2, sticky="w")


def build_widget(variables, parent, prefix, value, field):
    metadata = getattr(field, "metadata", {})
    if field.type is bool:
        var = tk.BooleanVar(value=value)
        widget = ttk.Checkbutton(parent, variable=var)
    elif choices := metadata.get("choices"):
        var = tk.StringVar(value=value)
        widget = ttk.Combobox(
            parent, textvariable=var, values=choices, state="readonly"
        )
    elif field.type is int:
        from_ = metadata.get("min", -math.inf)
        to = metadata.get("max", math.inf)
        var = tk.IntVar(value=value)
        widget = ttk.Spinbox(parent, from_=from_, to=to, textvariable=var)
    elif metadata.get("is_path"):
        var = tk.StringVar(value=value)
        widget = create_path_widget(parent, var)
    elif metadata.get("is_directory"):
        var = tk.StringVar(value=value)
        widget = create_dir_widget(parent, var)
    elif is_dict_of_type(value, bool):
        return create_bool_dict_widget(variables, parent, prefix, value)
    elif is_dict_of_type(value, str):
        return create_str_dict_widget(variables, parent, prefix, value)
    else:
        if field.metadata.get("multiline"):
            widget = scrolledtext.ScrolledText(parent, height=10, wrap=tk.WORD)
            widget.bind("<Control-a>", select_all)
            var = ScrolledTextwrapper(widget, str(value))
        else:
            var = tk.StringVar(value=str(value))
            widget = ttk.Entry(parent, textvariable=var)
    variables[prefix] = var
    return widget


def create_path_widget(parent, var):
    frame = ttk.Frame(parent)
    ttk.Entry(frame, textvariable=var).pack(side="left", fill="x", expand=True)
    button = ttk.Button(frame, text="Browse", command=lambda: browse_path(var))
    button.pack(side="left")
    return frame


def browse_path(var):
    path = filedialog.askopenfilename()
    if path:
        var.set(path)


def create_dir_widget(parent, var):
    frame = ttk.Frame(parent)
    ttk.Entry(frame, textvariable=var).pack(side="left", fill="x", expand=True)
    button = ttk.Button(frame, text="Browse", command=lambda: browse_dir(var))
    button.pack(side="left")
    return frame


def browse_dir(var):
    path = filedialog.askdirectory()
    if path:
        var.set(path)


def is_dict_of_type(d, t):
    return isinstance(d, dict) and all(isinstance(v, t) for v in d.values())


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
        ttk.Label(frame, text=name.title()).grid(row=row, column=0, sticky="w")
        ttk.Entry(frame, textvariable=var).grid(row=row, column=1, sticky="w")
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
        notebook = build_notebook(self.variables, self, self.config_data)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
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

        defaults = config.get_default_config().to_dict()
        unique_items = util.get_unique_items(defaults, data)
        config_path = Path(config.USER_CONFIG_PATH).expanduser()
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
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        links = (
            ("home_page", HOME_PAGE),
            ("license_page", LICENSE_PAGE),
            ("ffmpeg", "https://ffmpeg.org/"),
            ("ffmpeg_license", str(FFMPEG_LICENSE_PATH)),
            (
                "chrome-headless-shell",
                "https://googlechromelabs.github.io/chrome-for-testing/",
            ),
        )
        text = tk.Text(self, borderwidth=0, wrap=tk.WORD)
        text.grid(row=0, column=0, sticky="ew")
        text.insert("end", f"slp2mp4 {__version__}\n\n")
        text.insert("end", "Homepage: ")
        text.insert("end", HOME_PAGE, "home_page")
        text.insert("end", "\nLicense: ")
        text.insert("end", LICENSE_PAGE, "license_page")

        if FFMPEG_LICENSE_PATH.exists():
            text.insert("end", "\n\nThis build includes a bundled version of ")
            text.insert("end", "FFmpeg", "ffmpeg")
            text.insert("end", ". Its license can be found at ")
            text.insert("end", str(FFMPEG_LICENSE_PATH), "ffmpeg_license")

        if CHROME_ABOUT_PATH.exists():
            text.insert("end", "\n\nThis build includes a bundled version of ")
            text.insert("end", "chrome-headless-shell", "chrome-headless-shell")
            text.insert("end", ".")

        for link_tag, link_location in links:
            text.tag_config(link_tag, foreground="blue", underline=True)
            text.tag_bind(
                link_tag,
                "<Button-1>",
                lambda _, url=link_location: webbrowser.open(url),
            )


class Application(tk.Tk):
    def __init__(self, logger=None):
        super().__init__()
        self.title("slp2mp4")
        self.create_menu()
        self.inputs = []
        self.variables: dict[str, tk.Variable] = {}
        self.runtime_options = config.RuntimeOptions()
        self.stop_event = Event()
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
        add_config_option_to_gui(self.variables, frame, self.runtime_options, cols=2)

    def make_actions(self):
        frame = ttk.LabelFrame(self, text="Actions")
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        ttk.Button(frame, text="Run", command=self.run).pack(side="left")
        ttk.Button(frame, text="Stop", command=self.stop).pack(side="left")
        ttk.Button(frame, text="Kill", command=self.kill).pack(side="left")

    def make_log_text(self):
        self.log_text = scrolledtext.ScrolledText(self, height=10, wrap=tk.WORD)
        self.log_text.bind("<Control-a>", select_all)
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
        override = {}
        for key, var in self.variables.items():
            current = override
            for part in key[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[key[-1]] = var.get()
        self.runtime_options.override(override)

        self.log = log.update_logger(self.runtime_options.debug, self.log_text)

        self.stop_event.clear()
        self.kill_event.clear()
        conf = config.get_config()
        conf.validate()
        workdir = self.runtime_options.temporary_directory_path

        collector = Collector(
            inputs=self.inputs,
            stop_event=self.stop_event,
            monitor=self.runtime_options.monitor,
            workdir=workdir,
        )

        orchestrator = Orchestrator(
            conf=conf,
            kill_event=self.kill_event,
            collector=collector,
            combine_mode=self.runtime_options.combine_mode_enum,
            dry_run=self.runtime_options.dry_run,
            workdir=workdir,
            output_directory=self.runtime_options.output_directory_path,
            debug=self.runtime_options.debug,
        )
        threading.Thread(target=orchestrator.run).start()

    def stop(self):
        self.log.info("Received stop event")
        self.stop_event.set()

    def kill(self):
        self.log.info("Received kill event")
        self.kill_event.set()


def main():
    app = Application()
    app.mainloop()


if __name__ == "__main__":
    # https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#multi-processing
    freeze_support()
    main()
