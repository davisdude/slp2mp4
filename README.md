# slp2mp4

Convert Slippi replay files (.slp) to video files (.mp4) with ease. This tool automates the process of rendering Super Smash Bros. Melee replays using Slippi Dolphin and encoding them to MP4 format.

## Features

- **Multiple conversion modes**:
  - Single file conversion
  - Directory batch conversion (recursive)
  - Replay Manager zip file support
- **Parallel processing** for faster batch conversions
- **GUI interface** for easy configuration and operation
- **Customizable output** resolution and bitrate
- **Cross-platform support**  Windows, Linux

## Requirements

- Python 3.11 or higher
- [FFmpeg](https://ffmpeg.org/) installed and accessible
- [Slippi Dolphin](https://slippi.gg/downloads) installed
- Super Smash Bros. Melee ISO file

## Installation

### From Source

```bash
git clone https://github.com/davisdude/slp2mp4.git
cd slp2mp4
pip install -e .
```

### For GUI Support

```bash
pip install -e ".[gui]"
```

## Usage

### Command Line Interface

#### Single File Conversion
```bash
slp2mp4 -o output_directory/ single path/to/replay.slp
```

#### Directory Conversion
Convert all .slp files in a directory (recursively):
```bash
slp2mp4 -o output_directory/ directory path/to/replays/
```

#### Replay Manager Conversion
Convert replay manager exports (zip files or directories):
```bash
slp2mp4 -o output_directory/ replay_manager path/to/replays/
```

#### Options
- `-o, --output-directory`: Specify output directory (default: current directory)
- `-n, --dry-run`: Preview what files will be processed without converting

### Graphical User Interface

The GUI has all the features that the CLI has. Change your settings in the menu, select your conversion type, set your directories, then click start.

## Configuration

### Default Configuration

slp2mp4 uses a configuration file system with sensible defaults. User configuration is stored in `~/.slp2mp4.toml`.

### Configuration Options

#### Paths
- `ffmpeg`: Path to FFmpeg executable
- `slippi_playback`: Path to playback Slippi Dolphin executable
- `ssbm_ini`: Path to your Melee ISO file

#### Dolphin Settings
- `backend`: Video backend (`OGL`, `D3D`, `D3D12`, `Vulkan`, `Software`)
- `resolution`: Output resolution (`480p`, `720p`, `1080p`, `1440p`, `2160p`)
- `bitrate`: Video bitrate in kbps (default: 16000)

#### Runtime Settings
- `parallel`: Number of parallel processes (0 = auto-detect CPU cores)

### Example Configuration

```toml
[paths]
ffmpeg = "ffmpeg"
slippi_playback = "~/AppData/Roaming/Slippi Launcher/playback/Slippi Dolphin.exe"
ssbm_ini = "~/Games/Melee.iso"

[dolphin]
backend = "OGL"
resolution = "1080p"
bitrate = 16000

[runtime]
parallel = 0
```

or on Windows:

```toml
[paths]
ffmpeg = "C:\Users\user\Downloads\ffmpeg-2025-01-27-git-959b799c8d-essentials_build\bin\ffmpeg.exe"
slippi_playback = "C:\Users\user\AppData\Roaming\Slippi Launcher\playback\Slippi Dolphin.exe"
ssbm_ini = "C:\Users\user\Documents\iso\ssbm.iso"

[dolphin]
backend = "D3D"
resolution = "1080p"
bitrate = 16000

[runtime]
parallel = 0
```

## Building Standalone Executable (Windows)

To create a standalone GUI executable:

```bash
pip install pyinstaller
pip install .
pyinstaller slp2mp4-gui.spec
```

The executable will be created in the `dist/` directory.

## Notes

* If you get weird looking video (where half the width is cropped), try
  changing the video backend. [Here][dolphin-video-backends] is a list of the
  different video backends; you can find the names used
  [here][dolphin-video-backends-src] for what name to use in the config.

* Does not play nicely with WSL. Slippi playback expects all paths to be
  relative to Windows. Because `slp2mp4` parses the replay file to determine
  match length, both the WSL-relative and Windows-relative paths for each
  replay file would have to be determined. I could try to determine if the user
  is running under WSL and convert the path if possible.

    * Note to future self: `paths.ssbm_ini` must be the Windows file path (use
      `/` instead of `\`)

* Currently using [`py-slippi`][py-slippi] instead of [`peppi-py`][peppi-py]
  because of numerous issues related to `pyarrow` and `maturin` on Windows /
  Mac.

    * When the switch is made, the API is largely the same, but peppi's frame
      count starts *once players are actionable* (after ready/go), while
      py-slippi's frame count includes these frames.


[dolphin-video-backends-src]: https://github.com/dolphin-emu/dolphin/tree/master/Source/Core/VideoBackends
[dolphin-video-backends]: https://wiki.dolphin-emu.org/index.php?title=Configuration_Guide#Video_Backend
[peppi-py]: https://github.com/hohav/peppi-py
[py-slippi]: https://github.com/hohav/py-slippi

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
