import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import pathlib
import sys
import multiprocessing

import slp2mp4.config as config
import slp2mp4.modes as modes
import slp2mp4.version as version
import slp2mp4.scoreboards as scoreboards

import tomli_w


def _snake_to_title(string):
    return (" ").join(string.split("_")).title()


class ConfigDialog(tk.Toplevel):
    """Configuration dialog for slp2mp4 settings"""

    def __init__(self, parent, current_config):
        super().__init__(parent)
        self.title("slp2mp4 Configuration")
        self.config = current_config.copy()
        self.result = None

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

        self.create_widgets()
        self.load_config()

        # Center the dialog
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def create_widgets(self):
        # Create notebook for tabs
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Paths tab
        paths_frame = ttk.Frame(notebook)
        notebook.add(paths_frame, text="Paths")

        # FFmpeg path
        ttk.Label(paths_frame, text="FFmpeg Path:").grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )
        self.ffmpeg_var = tk.StringVar()
        ffmpeg_entry = ttk.Entry(paths_frame, textvariable=self.ffmpeg_var, width=40)
        ffmpeg_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(
            paths_frame,
            text="Browse",
            command=lambda: self.browse_file(
                self.ffmpeg_var,
                "FFmpeg",
                [("Executable", "*.exe"), ("All files", "*.*")],
            ),
        ).grid(row=0, column=2, padx=5, pady=5)

        # Slippi Playback path
        ttk.Label(paths_frame, text="Slippi Playback Path:").grid(
            row=1, column=0, sticky="w", padx=5, pady=5
        )
        self.slippi_var = tk.StringVar()
        slippi_entry = ttk.Entry(paths_frame, textvariable=self.slippi_var, width=40)
        slippi_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(
            paths_frame,
            text="Browse",
            command=lambda: self.browse_file(
                self.slippi_var,
                "Slippi Dolphin",
                [("Executable", "*.exe"), ("All files", "*.*")],
            ),
        ).grid(row=1, column=2, padx=5, pady=5)

        # SSBM ISO path
        ttk.Label(paths_frame, text="SSBM ISO Path:").grid(
            row=2, column=0, sticky="w", padx=5, pady=5
        )
        self.iso_var = tk.StringVar()
        iso_entry = ttk.Entry(paths_frame, textvariable=self.iso_var, width=40)
        iso_entry.grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(
            paths_frame,
            text="Browse",
            command=lambda: self.browse_file(
                self.iso_var, "SSBM ISO", [("ISO files", "*.iso"), ("All files", "*.*")]
            ),
        ).grid(row=2, column=2, padx=5, pady=5)

        # Dolphin settings tab
        dolphin_frame = ttk.Frame(notebook)
        notebook.add(dolphin_frame, text="Dolphin")

        # Video backend
        ttk.Label(dolphin_frame, text="Video Backend:").grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )
        self.backend_var = tk.StringVar()
        backend_combo = ttk.Combobox(
            dolphin_frame,
            textvariable=self.backend_var,
            values=config.DOLPHIN_BACKENDS,
            state="readonly",
        )
        backend_combo.grid(row=0, column=1, padx=5, pady=5)

        # Resolution
        ttk.Label(dolphin_frame, text="Resolution:").grid(
            row=1, column=0, sticky="w", padx=5, pady=5
        )
        self.resolution_var = tk.StringVar()
        resolution_combo = ttk.Combobox(
            dolphin_frame,
            textvariable=self.resolution_var,
            values=list(config.RESOLUTIONS.keys()),
            state="readonly",
        )
        resolution_combo.grid(row=1, column=1, padx=5, pady=5)

        # Bitrate
        ttk.Label(dolphin_frame, text="Bitrate (kbps):").grid(
            row=2, column=0, sticky="w", padx=5, pady=5
        )
        self.bitrate_var = tk.IntVar()
        bitrate_spin = ttk.Spinbox(
            dolphin_frame,
            from_=1000,
            to=50000,
            textvariable=self.bitrate_var,
            increment=1000,
        )
        bitrate_spin.grid(row=2, column=1, padx=5, pady=5)

        # FFmpeg settings tab
        ffmpeg_frame = ttk.Frame(notebook)
        ffmpeg_frame.pack(side="top", pady=5)
        notebook.add(ffmpeg_frame, text="FFmpeg")

        # Volume
        volume_frame = ttk.Frame(ffmpeg_frame)
        volume_frame.pack(side="top", pady=5)
        ttk.Label(volume_frame, text="Volume (%)").pack(side="left", padx=5)
        self.volume_var = tk.IntVar()
        volume_spin = ttk.Spinbox(
            volume_frame, from_=0, to=100, textvariable=self.volume_var, increment=1
        )
        volume_spin.pack(side="right", padx=5)

        # FFmpeg audio args
        ffmpeg_args_frame = ttk.Frame(ffmpeg_frame)
        ffmpeg_args_frame.pack(side="top", pady=5)
        ttk.Label(ffmpeg_args_frame, text="Audio args").pack(side="left", padx=5)
        self.ffmpeg_args_var = scrolledtext.ScrolledText(
            ffmpeg_args_frame,
            height=2,
            wrap=tk.WORD,
        )
        self.ffmpeg_args_var.pack(side="bottom", padx=5)

        # Runtime settings tab
        runtime_frame = ttk.Frame(notebook)
        runtime_frame.pack(side="top", pady=5)
        notebook.add(runtime_frame, text="Runtime")

        # Parallel processes
        parallel_frame = ttk.Frame(runtime_frame)
        parallel_frame.pack(side="top", pady=5)
        ttk.Label(parallel_frame, text="Parallel Processes:").pack(side="left", padx=5)
        self.parallel_var = tk.IntVar()
        parallel_spin = ttk.Spinbox(
            parallel_frame, from_=0, to=32, textvariable=self.parallel_var
        )
        parallel_spin.pack(side="left", padx=5)

        parallel_info_frame = ttk.Frame(runtime_frame)
        parallel_info_frame.pack(side="top", pady=5)
        ttk.Label(parallel_info_frame, text="(0 = auto-detect CPU cores)").pack(
            side="left", padx=5
        )

        # Prepend directory
        prepend_frame = ttk.Frame(runtime_frame)
        prepend_frame.pack(side="top", pady=5)
        ttk.Label(prepend_frame, text="Prepend directory?").pack(side="left", padx=5)
        self.prepend_var = tk.BooleanVar()
        prepend_box = ttk.Checkbutton(prepend_frame, variable=self.prepend_var)
        prepend_box.pack(side="left", padx=5)

        # Youtubify names
        youtubify_frame = ttk.Frame(runtime_frame)
        youtubify_frame.pack(side="top", pady=5)
        ttk.Label(youtubify_frame, text="Youtubify names?").pack(side="left", padx=5)
        self.youtubify_var = tk.BooleanVar()
        youtubify_box = ttk.Checkbutton(youtubify_frame, variable=self.youtubify_var)
        youtubify_box.pack(side="left", padx=5)

        youtubify_info_frame = ttk.Frame(runtime_frame)
        youtubify_info_frame.pack(side="top", pady=5)
        ttk.Label(
            youtubify_info_frame,
            text="Replace some characters in file names for YouTube uploads",
        ).pack(side="left", padx=5)

        # Scoreboard settings tab
        scoreboard_frame = ttk.Frame(notebook)
        scoreboard_frame.pack(side="top", pady=5)
        notebook.add(scoreboard_frame, text="Scoreboard")

        # Scoreboard type
        ttk.Label(scoreboard_frame, text="Scoreboard:").grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )
        self.scoreboard_type_var = tk.StringVar()
        scoreboard_type_combo = ttk.Combobox(
            scoreboard_frame,
            textvariable=self.scoreboard_type_var,
            values=list(scoreboards.SCOREBOARDS.keys()),
            state="readonly",
        )
        scoreboard_type_combo.grid(row=0, column=1, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(self)
        button_frame.pack(side="bottom", pady=10)

        ttk.Button(button_frame, text="Save", command=self.save_config).pack(
            side="left", padx=5
        )
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(
            side="left", padx=5
        )

    def browse_file(self, var, title, filetypes):
        filename = filedialog.askopenfilename(
            title=f"Select {title}", filetypes=filetypes
        )
        if filename:
            var.set(filename)

    def load_config(self):
        """Load current configuration into dialog fields"""

        self.ffmpeg_var.set(str(self.config["paths"]["ffmpeg"]))
        self.slippi_var.set(str(self.config["paths"]["slippi_playback"]))
        self.iso_var.set(str(self.config["paths"]["ssbm_iso"]))
        self.backend_var.set(self.config["dolphin"]["backend"])
        self.resolution_var.set(self.config["dolphin"]["resolution"])
        self.bitrate_var.set(int(self.config["dolphin"]["bitrate"]))
        self.volume_var.set(int(self.config["ffmpeg"]["volume"]))
        self.ffmpeg_args_var.delete("1.0", tk.END)
        self.ffmpeg_args_var.insert(tk.END, str(self.config["ffmpeg"]["audio_args"]))
        self.parallel_var.set(int(self.config["runtime"]["parallel"]))
        self.prepend_var.set(bool(self.config["runtime"]["prepend_directory"]))
        self.youtubify_var.set(bool(self.config["runtime"]["youtubify_names"]))
        self.scoreboard_type_var.set(self.config["scoreboard"]["type"])

    def save_config(self):
        """Save configuration and close dialog"""
        audio_args = self.ffmpeg_args_var.get("1.0", tk.END).replace("\n", "")
        self.result = {
            "paths": {
                "ffmpeg": self.ffmpeg_var.get(),
                "slippi_playback": self.slippi_var.get(),
                "ssbm_iso": self.iso_var.get(),
            },
            "dolphin": {
                "backend": self.backend_var.get(),
                "resolution": self.resolution_var.get(),
                "bitrate": self.bitrate_var.get(),
            },
            "ffmpeg": {
                "volume": self.volume_var.get(),
                "audio_args": audio_args,
            },
            "runtime": {
                "parallel": self.parallel_var.get(),
                "prepend_directory": self.prepend_var.get(),
                "youtubify_names": self.youtubify_var.get(),
            },
            "scoreboard": {
                "type": self.scoreboard_type_var.get(),
            },
        }
        self.destroy()


class AboutDialog(tk.Toplevel):
    """Show about / version information"""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("About")

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

        self.create_widgets()

        # Center the dialog
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def create_widgets(self):
        info_frame = ttk.LabelFrame(self, text="Info", padding=10)
        info_frame.pack(fill="x", padx=10, pady=10)
        info_text = scrolledtext.ScrolledText(
            info_frame,
            height=5,
            wrap=tk.WORD,
        )
        info_text.insert(tk.END, self._get_info())
        info_text["state"] = "disabled"
        info_text.pack(side="left", padx=5)

        version_frame = ttk.LabelFrame(self, text="Version", padding=10)
        version_frame.pack(fill="x", padx=10, pady=10)
        version_text = scrolledtext.ScrolledText(
            version_frame,
            height=1,
            wrap=tk.WORD,
        )
        version_text.insert(tk.END, self._get_version())
        version_text["state"] = "disabled"
        version_text.pack(side="left", padx=5)

        button_frame = ttk.Frame(self, padding=10)
        button_frame.pack(side="bottom", pady=10)
        ttk.Button(button_frame, text="Copy Version", command=self.copy_version).pack(
            side="left", padx=5
        )
        ttk.Button(button_frame, text="Quit", command=self.destroy).pack(
            side="left", padx=5
        )

    def _get_version(self):
        return version.version

    def _get_info(self):
        return (
            "slp2mp4 GUI\n\n"
            "A graphical interface for converting Slippi replay files to MP4 videos."
        )

    def copy_version(self):
        self.clipboard_clear()
        self.clipboard_append(self._get_version())


class Slp2Mp4GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("slp2mp4 GUI")

        # Queue for thread communication
        self.queue = queue.Queue()

        # Load configuration
        self.config = self.load_configuration()

        # Create menu
        self.create_menu()

        # Create main interface
        self.create_widgets()

        # Start queue processing
        self.root.after(100, self.process_queue)

    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Exit", command=self.root.quit)

        # Settings menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Configure...", command=self.show_config_dialog)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

    def create_widgets(self):
        # Mode selection frame
        mode_frame = ttk.LabelFrame(self.root, text="Conversion Mode", padding=10)
        mode_frame.pack(fill="x", padx=10, pady=5)

        default_mode_index = -1
        mode_snakes = list(modes.MODES.keys())
        mode_titles = [_snake_to_title(mode_name) for mode_name in modes.MODES]
        self.mode_var = tk.StringVar(value=mode_snakes[-1])
        for snake, title in zip(mode_snakes, mode_titles):
            ttk.Radiobutton(
                mode_frame,
                text=title,
                variable=self.mode_var,
                value=snake,
                command=self.update_input_section,
            ).pack(side="left", padx=5)

        # Input selection frame
        self.input_frame = ttk.LabelFrame(self.root, text="Input", padding=10)
        self.input_frame.pack(fill="x", padx=10, pady=5)
        self.update_input_section()  # Update title to default

        self.input_var = tk.StringVar()
        self.input_entry = ttk.Entry(
            self.input_frame, textvariable=self.input_var, width=60
        )
        self.input_entry.pack(side="left", padx=5, fill="x", expand=True)

        self.browse_button = ttk.Button(
            self.input_frame, text="Browse", command=self.browse_input
        )
        self.browse_button.pack(side="left", padx=5)

        # Output selection frame
        output_frame = ttk.LabelFrame(self.root, text="Output Directory", padding=10)
        output_frame.pack(fill="x", padx=10, pady=5)

        self.output_var = tk.StringVar(value=".")
        output_entry = ttk.Entry(output_frame, textvariable=self.output_var, width=60)
        output_entry.pack(side="left", padx=5, fill="x", expand=True)

        ttk.Button(output_frame, text="Browse", command=self.browse_output).pack(
            side="left", padx=5
        )

        # Options frame
        options_frame = ttk.LabelFrame(self.root, text="Options", padding=10)
        options_frame.pack(fill="x", padx=10, pady=5)

        self.dry_run_var = tk.BooleanVar()
        ttk.Checkbutton(
            options_frame, text="Dry Run (preview only)", variable=self.dry_run_var
        ).pack(anchor="w")

        # Control buttons frame
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill="x", padx=10, pady=10)

        self.start_button = ttk.Button(
            control_frame,
            text="Start Conversion",
            command=self.start_conversion,
            style="Accent.TButton",
        )
        self.start_button.pack(side="left", padx=5)

        self.stop_button = ttk.Button(
            control_frame, text="Stop", command=self.stop_conversion, state="disabled"
        )
        self.stop_button.pack(side="left", padx=5)

        # Progress frame
        progress_frame = ttk.LabelFrame(self.root, text="Progress", padding=10)
        progress_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame, variable=self.progress_var, mode="indeterminate"
        )
        self.progress_bar.pack(fill="x", pady=5)

        self.status_label = ttk.Label(progress_frame, text="Ready")
        self.status_label.pack(anchor="w", pady=5)

        # Output log
        self.log_text = scrolledtext.ScrolledText(
            progress_frame, height=10, wrap=tk.WORD
        )
        self.log_text.pack(fill="both", expand=True)

    def update_input_section(self):
        """Update input section based on selected mode"""
        mode = self.mode_var.get()
        words = modes.MODES[mode].description.split(" ")
        words = (" ").join([words[0].title()] + words[1:])
        self.input_frame.config(text=words)

    def browse_input(self):
        # TODO: Multi-select? (Not sure what that'd look like for dir mode)
        mode = self.mode_var.get()
        if mode == "single":
            filename = filedialog.askopenfilename(
                title="Select SLP file",
                filetypes=[("Slippi files", "*.slp"), ("All files", "*.*")],
            )
            if filename:
                self.input_var.set(filename)
        else:
            dirname = filedialog.askdirectory(title="Select Directory")
            if dirname:
                self.input_var.set(dirname)

    def browse_output(self):
        dirname = filedialog.askdirectory(title="Select Output Directory")
        if dirname:
            self.output_var.set(dirname)

    def show_config_dialog(self):
        dialog = ConfigDialog(self.root, self.config)
        self.root.wait_window(dialog)
        if dialog.result:
            self.config = dialog.result
            self.save_configuration()

    def show_about(self):
        dialog = AboutDialog(self.root)
        self.root.wait_window(dialog)

    def load_configuration(self):
        """Load configuration from file or use defaults"""
        return config.get_config()

    def save_configuration(self):
        """Save configuration to user config file"""
        config_path = pathlib.Path(config.USER_CONFIG_FILE).expanduser()
        try:
            with open(config_path, "wb") as f:
                tomli_w.dump(self.config, f)
            self.log("Configuration saved successfully")
        except Exception as e:
            self.log(f"Error saving configuration: {e}")

    def validate_inputs(self):
        """Validate user inputs before starting conversion"""
        if not self.input_var.get():
            messagebox.showerror("Error", "Please select an input file or directory")
            return False

        if not self.output_var.get():
            messagebox.showerror("Error", "Please select an output directory")
            return False

        # Check if paths exist in config
        if not self.config["paths"]["slippi_playback"]:
            messagebox.showerror(
                "Error",
                "Slippi Playback path not configured. Please configure in Settings.",
            )
            return False

        if not self.config["paths"]["ssbm_iso"]:
            messagebox.showerror(
                "Error", "SSBM ISO path not configured. Please configure in Settings."
            )
            return False

        return True

    def start_conversion(self):
        if not self.validate_inputs():
            return

        # Disable controls
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.progress_bar.start()

        # Clear log
        self.log_text.delete(1.0, tk.END)

        # Start conversion in thread
        self.conversion_thread = threading.Thread(target=self.run_conversion)
        self.conversion_thread.start()

    def stop_conversion(self):
        # TODO: Implement proper cancellation
        self.log("Stopping conversion...")
        self.stop_button.config(state="disabled")

    def run_conversion(self):
        """Run the actual conversion process"""
        try:
            paths = [pathlib.Path(self.input_var.get())]
            output_directory = pathlib.Path(self.output_var.get())
            dry_run = self.dry_run_var.get()
            mode = modes.MODES[self.mode_var.get()].mode(paths, output_directory)
            self.queue.put(("log", "Starting conversion..."))
            output = mode.run(dry_run)
            if output:
                self.queue.put(("log", "Dry run results:"))
                self.queue.put(("log", output.rstrip()))
            self.queue.put(("log", "\nConversion completed successfully!"))
        except Exception as e:
            import traceback

            self.queue.put(("error", str(e)))
            self.queue.put(("log", f"Full traceback:\n{traceback.format_exc()}"))
        finally:
            self.queue.put(("done", None))

    def process_queue(self):
        """Process messages from worker thread"""
        try:
            while True:
                msg_type, msg_data = self.queue.get_nowait()

                if msg_type == "log":
                    self.log(msg_data)
                elif msg_type == "error":
                    self.log(f"ERROR: {msg_data}")
                    messagebox.showerror("Conversion Error", msg_data)
                elif msg_type == "done":
                    self.progress_bar.stop()
                    self.start_button.config(state="normal")
                    self.stop_button.config(state="disabled")
                    self.status_label.config(text="Ready")

        except queue.Empty:
            pass

        # Schedule next check
        self.root.after(100, self.process_queue)

    def log(self, message):
        """Add message to log output"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.status_label.config(
            text=message[:80] + "..." if len(message) > 80 else message
        )


def main():
    # CRITICAL: Add multiprocessing freeze support for Windows executables
    if getattr(sys, "frozen", False):
        multiprocessing.freeze_support()

    # Set up dark theme if available
    root = tk.Tk()
    try:
        root.tk.call("source", "azure.tcl")
        root.tk.call("set_theme", "dark")
    except:
        # Fall back to default theme
        pass

    app = Slp2Mp4GUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
