import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import pathlib
import json
import os
import sys
import subprocess
from typing import Dict, List, Optional
import configparser
import multiprocessing

# Add the src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import slp2mp4.config as config
import slp2mp4.modes.single as single_mode
import slp2mp4.modes.directory as directory_mode
import slp2mp4.modes.replay_manager as replay_manager_mode
import slp2mp4.orchestrator as orchestrator


class ConfigDialog(tk.Toplevel):
    """Configuration dialog for slp2mp4 settings"""

    def __init__(self, parent, current_config):
        super().__init__(parent)
        self.title("slp2mp4 Configuration")
        self.geometry("600x500")
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
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Paths tab
        paths_frame = ttk.Frame(notebook)
        notebook.add(paths_frame, text="Paths")

        # FFmpeg path
        ttk.Label(paths_frame, text="FFmpeg Path:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.ffmpeg_var = tk.StringVar()
        ffmpeg_entry = ttk.Entry(paths_frame, textvariable=self.ffmpeg_var, width=40)
        ffmpeg_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(paths_frame, text="Browse", command=lambda: self.browse_file(self.ffmpeg_var, "FFmpeg", [("Executable", "*.exe"), ("All files", "*.*")])).grid(row=0, column=2, padx=5, pady=5)

        # Slippi Playback path
        ttk.Label(paths_frame, text="Slippi Playback Path:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.slippi_var = tk.StringVar()
        slippi_entry = ttk.Entry(paths_frame, textvariable=self.slippi_var, width=40)
        slippi_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(paths_frame, text="Browse", command=lambda: self.browse_file(self.slippi_var, "Slippi Dolphin", [("Executable", "*.exe"), ("All files", "*.*")])).grid(row=1, column=2, padx=5, pady=5)

        # SSBM ISO path
        ttk.Label(paths_frame, text="SSBM ISO Path:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.iso_var = tk.StringVar()
        iso_entry = ttk.Entry(paths_frame, textvariable=self.iso_var, width=40)
        iso_entry.grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(paths_frame, text="Browse", command=lambda: self.browse_file(self.iso_var, "SSBM ISO", [("ISO files", "*.iso"), ("All files", "*.*")])).grid(row=2, column=2, padx=5, pady=5)

        # Dolphin settings tab
        dolphin_frame = ttk.Frame(notebook)
        notebook.add(dolphin_frame, text="Dolphin")

        # Video backend
        ttk.Label(dolphin_frame, text="Video Backend:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.backend_var = tk.StringVar()
        backend_combo = ttk.Combobox(dolphin_frame, textvariable=self.backend_var, values=["OGL", "D3D", "D3D12", "Vulkan", "Software"], state='readonly')
        backend_combo.grid(row=0, column=1, padx=5, pady=5)

        # Resolution
        ttk.Label(dolphin_frame, text="Resolution:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.resolution_var = tk.StringVar()
        resolution_combo = ttk.Combobox(dolphin_frame, textvariable=self.resolution_var, values=["480p", "720p", "1080p", "1440p", "2160p"], state='readonly')
        resolution_combo.grid(row=1, column=1, padx=5, pady=5)

        # Bitrate
        ttk.Label(dolphin_frame, text="Bitrate (kbps):").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.bitrate_var = tk.IntVar()
        bitrate_spin = ttk.Spinbox(dolphin_frame, from_=1000, to=50000, textvariable=self.bitrate_var, increment=1000)
        bitrate_spin.grid(row=2, column=1, padx=5, pady=5)

        # Runtime settings tab
        runtime_frame = ttk.Frame(notebook)
        notebook.add(runtime_frame, text="Runtime")

        # Parallel processes
        ttk.Label(runtime_frame, text="Parallel Processes:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.parallel_var = tk.IntVar()
        ttk.Label(runtime_frame, text="(0 = auto-detect CPU cores)").grid(row=0, column=2, sticky='w', padx=5, pady=5)
        parallel_spin = ttk.Spinbox(runtime_frame, from_=0, to=32, textvariable=self.parallel_var)
        parallel_spin.grid(row=0, column=1, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(self)
        button_frame.pack(side='bottom', pady=10)

        ttk.Button(button_frame, text="Save", command=self.save_config).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side='left', padx=5)

    def browse_file(self, var, title, filetypes):
        filename = filedialog.askopenfilename(title=f"Select {title}", filetypes=filetypes)
        if filename:
            var.set(filename)

    def load_config(self):
        """Load current configuration into dialog fields"""
        # Reverse map resolution from internal format to display format
        resolution_reverse_map = {"2": "480p", "3": "720p", "5": "1080p", "6": "1440p", "8": "2160p"}

        self.ffmpeg_var.set(str(self.config.get('paths', {}).get('ffmpeg', 'ffmpeg')))
        self.slippi_var.set(str(self.config.get('paths', {}).get('slippi_playback', '')))
        self.iso_var.set(str(self.config.get('paths', {}).get('ssbm_ini', '')))
        self.backend_var.set(self.config.get('dolphin', {}).get('backend', 'OGL'))

        # Handle resolution conversion
        res_value = str(self.config.get('dolphin', {}).get('resolution', '5'))
        display_resolution = resolution_reverse_map.get(res_value, res_value)
        # If it's already in display format (e.g. "1080p"), use it as is
        if display_resolution in ["480p", "720p", "1080p", "1440p", "2160p"]:
            self.resolution_var.set(display_resolution)
        else:
            self.resolution_var.set("1080p")  # Default

        self.bitrate_var.set(int(self.config.get('dolphin', {}).get('bitrate', 16000)))
        self.parallel_var.set(self.config.get('runtime', {}).get('parallel', 0))

    def save_config(self):
        """Save configuration and close dialog"""
        # Get the resolution value and convert it to the internal format
        resolution_map = {"480p": "2", "720p": "3", "1080p": "5", "1440p": "6", "2160p": "8"}
        resolution = self.resolution_var.get()

        # Convert paths to pathlib.Path objects
        import pathlib

        self.result = {
            'paths': {
                'ffmpeg': pathlib.Path(self.ffmpeg_var.get()).expanduser(),
                'slippi_playback': pathlib.Path(self.slippi_var.get()).expanduser(),
                'ssbm_ini': pathlib.Path(self.iso_var.get()).expanduser()
            },
            'dolphin': {
                'backend': self.backend_var.get(),
                'resolution': resolution_map.get(resolution, "5"),  # Default to 1080p
                'bitrate': str(self.bitrate_var.get())  # Convert to string
            },
            'runtime': {
                'parallel': self.parallel_var.get() if self.parallel_var.get() != 0 else os.cpu_count()
            },
            'ffmpeg': {
                'audio_args': '-ar 48000 -c:a libopus -f opus -ac 2 -b:a 128k'
            }
        }
        self.destroy()


class Slp2Mp4GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("slp2mp4 GUI")
        self.root.geometry("800x600")

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
        mode_frame.pack(fill='x', padx=10, pady=5)

        self.mode_var = tk.StringVar(value="single")
        ttk.Radiobutton(mode_frame, text="Single File", variable=self.mode_var, value="single", command=self.update_input_section).pack(side='left', padx=5)
        ttk.Radiobutton(mode_frame, text="Directory", variable=self.mode_var, value="directory", command=self.update_input_section).pack(side='left', padx=5)
        ttk.Radiobutton(mode_frame, text="Replay Manager", variable=self.mode_var, value="replay_manager", command=self.update_input_section).pack(side='left', padx=5)

        # Input selection frame
        self.input_frame = ttk.LabelFrame(self.root, text="Input", padding=10)
        self.input_frame.pack(fill='x', padx=10, pady=5)

        self.input_var = tk.StringVar()
        self.input_entry = ttk.Entry(self.input_frame, textvariable=self.input_var, width=60)
        self.input_entry.pack(side='left', padx=5, fill='x', expand=True)

        self.browse_button = ttk.Button(self.input_frame, text="Browse", command=self.browse_input)
        self.browse_button.pack(side='left', padx=5)

        # Output selection frame
        output_frame = ttk.LabelFrame(self.root, text="Output Directory", padding=10)
        output_frame.pack(fill='x', padx=10, pady=5)

        self.output_var = tk.StringVar(value=".")
        output_entry = ttk.Entry(output_frame, textvariable=self.output_var, width=60)
        output_entry.pack(side='left', padx=5, fill='x', expand=True)

        ttk.Button(output_frame, text="Browse", command=self.browse_output).pack(side='left', padx=5)

        # Options frame
        options_frame = ttk.LabelFrame(self.root, text="Options", padding=10)
        options_frame.pack(fill='x', padx=10, pady=5)

        self.dry_run_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Dry Run (preview only)", variable=self.dry_run_var).pack(anchor='w')
        
        self.no_prepend_folder_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Don't prepend folder names to output filenames", variable=self.no_prepend_folder_var).pack(anchor='w')

        self.youtube_mode = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="YouTube Mode", variable=self.youtube_mode).pack(anchor='w')

        # Control buttons frame
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill='x', padx=10, pady=10)

        self.start_button = ttk.Button(control_frame, text="Start Conversion", command=self.start_conversion, style='Accent.TButton')
        self.start_button.pack(side='left', padx=5)

        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.stop_conversion, state='disabled')
        self.stop_button.pack(side='left', padx=5)

        # Progress frame
        progress_frame = ttk.LabelFrame(self.root, text="Progress", padding=10)
        progress_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, mode='indeterminate')
        self.progress_bar.pack(fill='x', pady=5)

        self.status_label = ttk.Label(progress_frame, text="Ready")
        self.status_label.pack(anchor='w', pady=5)

        # Output log
        self.log_text = scrolledtext.ScrolledText(progress_frame, height=10, wrap=tk.WORD)
        self.log_text.pack(fill='both', expand=True)

    def update_input_section(self):
        """Update input section based on selected mode"""
        mode = self.mode_var.get()
        if mode == "single":
            self.input_frame.config(text="Input File")
        elif mode == "directory":
            self.input_frame.config(text="Input Directory")
        elif mode == "replay_manager":
            self.input_frame.config(text="Replay Manager Zip/Directory")

    def browse_input(self):
        mode = self.mode_var.get()
        if mode == "single":
            filename = filedialog.askopenfilename(
                title="Select SLP file",
                filetypes=[("Slippi files", "*.slp"), ("All files", "*.*")]
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
        messagebox.showinfo("About", "slp2mp4 GUI\n\nA graphical interface for converting Slippi replay files to MP4 videos.")

    def load_configuration(self):
        """Load configuration from file or use defaults"""
        try:
            # Try to load from slp2mp4's config loader
            conf = config.get_config()
            # Ensure bitrate is a string for INI file compatibility
            if 'dolphin' in conf and 'bitrate' in conf['dolphin']:
                conf['dolphin']['bitrate'] = str(conf['dolphin']['bitrate'])
            return conf
        except:
            # Return default configuration
            return {
                'paths': {
                    'ffmpeg': pathlib.Path('ffmpeg'),
                    'slippi_playback': pathlib.Path(os.path.expanduser('~/AppData/Roaming/Slippi Launcher/playback/Slippi Dolphin.exe')),
                    'ssbm_ini': pathlib.Path('')
                },
                'dolphin': {
                    'backend': 'OGL',
                    'resolution': '5',  # Internal format for 1080p
                    'bitrate': '16000'  # Must be string
                },
                'runtime': {
                    'parallel': os.cpu_count()
                },
                'ffmpeg': {
                    'audio_args': '-ar 48000 -c:a libopus -f opus -ac 2 -b:a 128k'
                }
            }

    def save_configuration(self):
        """Save configuration to user config file"""
        config_path = pathlib.Path("~/.slp2mp4.toml").expanduser()
        try:
            import tomli_w
            # Convert configuration to TOML-friendly format
            toml_config = {
                'paths': {
                    'ffmpeg': str(self.config['paths']['ffmpeg']),
                    'slippi_playback': str(self.config['paths']['slippi_playback']),
                    'ssbm_ini': str(self.config['paths']['ssbm_ini'])
                },
                'dolphin': {
                    'backend': self.config['dolphin']['backend'],
                    'resolution': '1080p' if self.config['dolphin']['resolution'] == '5' else '720p',  # Convert back to friendly format
                    'bitrate': int(self.config['dolphin']['bitrate'])  # Save as int in TOML
                },
                'runtime': {
                    'parallel': 0 if self.config['runtime']['parallel'] == os.cpu_count() else self.config['runtime']['parallel']
                },
                'ffmpeg': {
                    'audio_args': self.config['ffmpeg']['audio_args']
                }
            }
            with open(config_path, 'wb') as f:
                tomli_w.dump(toml_config, f)
            self.log("Configuration saved successfully")
        except ImportError:
            self.log("Warning: tomli_w not installed, configuration not saved to file")
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
        if not self.config.get('paths', {}).get('slippi_playback'):
            messagebox.showerror("Error", "Slippi Playback path not configured. Please configure in Settings.")
            return False

        if not self.config.get('paths', {}).get('ssbm_ini'):
            messagebox.showerror("Error", "SSBM ISO path not configured. Please configure in Settings.")
            return False

        return True

    def start_conversion(self):
        if not self.validate_inputs():
            return

        # Disable controls
        self.start_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.progress_bar.start()

        # Clear log
        self.log_text.delete(1.0, tk.END)

        # Start conversion in thread
        self.conversion_thread = threading.Thread(target=self.run_conversion)
        self.conversion_thread.start()

    def stop_conversion(self):
        # TODO: Implement proper cancellation
        self.log("Stopping conversion...")
        self.stop_button.config(state='disabled')

    def run_conversion(self):
        """Run the actual conversion process"""
        try:
            # Create args namespace to mimic command line args
            class Args:
                pass

            args = Args()
            args.path = pathlib.Path(self.input_var.get())
            args.output_directory = pathlib.Path(self.output_var.get())
            args.dry_run = self.dry_run_var.get()
            args.no_prepend_folder = self.no_prepend_folder_var.get()
            args.youtube_mode = self.youtube_mode.get()

            mode = self.mode_var.get()

            # Use the config directly - it's already been processed
            conf = self.config

            # Get inputs and outputs based on mode
            if mode == "single":
                products = single_mode.run(conf, args)
            elif mode == "directory":
                products = directory_mode.run(conf, args)
            elif mode == "replay_manager":
                products = replay_manager_mode.run(conf, args)

            if args.dry_run:
                # Show dry run results
                self.queue.put(('log', "Dry run results:"))
                for out_file, input_files in products.items():
                    self.queue.put(('log', f"\n{out_file}:"))
                    for i in input_files:
                        self.queue.put(('log', f"  - {i}"))
            else:
                # Create output directory
                os.makedirs(args.output_directory, exist_ok=True)

                # Run orchestrator
                self.queue.put(('log', "Starting conversion..."))
                orchestrator.run(conf, products)
                self.queue.put(('log', "\nConversion completed successfully!"))

        except Exception as e:
            import traceback
            self.queue.put(('error', str(e)))
            self.queue.put(('log', f"Full traceback:\n{traceback.format_exc()}"))
        finally:
            self.queue.put(('done', None))

    def process_queue(self):
        """Process messages from worker thread"""
        try:
            while True:
                msg_type, msg_data = self.queue.get_nowait()

                if msg_type == 'log':
                    self.log(msg_data)
                elif msg_type == 'error':
                    self.log(f"ERROR: {msg_data}")
                    messagebox.showerror("Conversion Error", msg_data)
                elif msg_type == 'done':
                    self.progress_bar.stop()
                    self.start_button.config(state='normal')
                    self.stop_button.config(state='disabled')
                    self.status_label.config(text="Ready")

        except queue.Empty:
            pass

        # Schedule next check
        self.root.after(100, self.process_queue)

    def log(self, message):
        """Add message to log output"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.status_label.config(text=message[:80] + "..." if len(message) > 80 else message)


def main():
    # CRITICAL: Add multiprocessing freeze support for Windows executables
    if getattr(sys, 'frozen', False):
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
