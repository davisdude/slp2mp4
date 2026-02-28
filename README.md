# `slp2mp4`

Convert Slippi replay files (`.slp`) to video files (`.mp4`) with ease.

## Features

- Multiple conversion modes:
    - Single file(s)
    - Directory (recursive)
    - [Replay Manager][replay-manager] zip(s)
- Parallel processing for faster conversions
- GUI for easy configuration and operation
- Customizable output resolution and bitrate
- Cross-platform support for Windows, Linux
    - Dolphin on Mac does not support framedumping

## Requirements

- Python 3.11 or higher
- [FFmpeg](https://ffmpeg.org/) installed and accessible
- [Slippi Dolphin](https://slippi.gg/downloads) installed
- Super Smash Bros. Melee ISO file

## Installation

### From a Build

Select the latest release from the [releases][releases] page.

### From Source

```bash
pip install "slp2mp4[gui] @ git+https://github.com/davisdude/slp2mp4.git"
```

or

```bash
git clone https://github.com/davisdude/slp2mp4.git
pip install .[gui]
```

Both methods require having `git` and `pip` installed

## Usage

### Command Line Interface

```text
usage: slp2mp4 [-h] [-o OUTPUT_DIRECTORY] [-n] [-v] {single,directory,replay_manager} ...

options:
  -h, --help            show this help message and exit
  -o, --output-directory OUTPUT_DIRECTORY
                        set path to output videos
  -n, --dry-run         show inputs and outputs and exit
  -v, --version         show program's version number and exit

mode:
  {single,directory,replay_manager}
    single              convert single replay files to videos
    directory           recursively convert all replay files in a directory to videos
    replay_manager      recursively convert all replay files in a zip to videos
```

Each mode can accept several inputs simultaneously:

```text
usage: slp2mp4 single [-h] paths [paths ...]

positional arguments:
  paths       input file(s)

options:
  -h, --help  show this help message and exit
```

```
usage: slp2mp4 directory [-h] paths [paths ...]

positional arguments:
  paths       input directory/directories

options:
  -h, --help  show this help message and exit
```

```
usage: slp2mp4 zip [-h] paths [paths ...]

positional arguments:
  paths       replay manager zip/directory

options:
  -h, --help  show this help message and exit
```

### Graphical User Interface

The GUI has all the features that the CLI has. Change your settings in the
menu, select your conversion type, set your directories, then click start.

To launch the GUI, run `slp2mp4_gui`.

## Configuration

`slp2mp4` uses hierarchical settings that come from [TOML][toml] files.
Settings not found in the user configuration (`~/.slp2mp4.toml`) fall back to
the [default settings](#default-settings).

### Default Settings

The default settings can be found [here][default-settings].

### Configuration Options

#### Paths

- `ffmpeg`: Path to FFmpeg executable
- `slippi_playback`: Path to playback Slippi Dolphin executable
- `ssbm_iso`: Path to your Melee ISO file

#### Dolphin Settings

- `backend`: Video backend (`D3D12`, `DX11`, `DX9`, `OGL`, `Software Renderer`,
  `Vulkan`)
- `resolution`: Output resolution (`480p`, `720p`, `1080p`, `1440p`, `2160p`)
- `bitrate`: Video bitrate in kbps

##### Gecko Codes

- `"$Optional: Show Player Names"`
- `"$Optional: Game Music OFF"`
- `"$Optional: Widescreen 16:9"`
- `"$Optional: Disable Screen Shake"`
- `"$Optional: Hide HUD"`
- `"$Optional: Hide Waiting For Game"`
- `"$Optional: Enable Develop Mode"`
- `"$Optional: Lagless FoD"`

#### FFmpeg Settings

- `audio_args`: FFmpeg audio processing settings
- `volume`: Volume of dolphin (0-100)

#### Runtime Settings

- `parallel`: Number of parallel processes (0 = auto-detect CPU cores)
- `prepend_directory`: Prepend the parent directory info
- `preserve_directory_structure`: Make video outputs match the input structure
  instead of being "flat"
- `youtubify_names`: Enable `name_replacements` (below)
- `name_replacements`: A mapping of characters to replace in titles; intended for
  uploads to websites (e.g. YouTube) that remove or prohibit certain characters
  in titles

    - To disable entirely, set `youtubify_names` to `false`
    - To disable for specific characters, have its assignment be to itself, e.g.

      ```toml
      [runtime.name_replacements]
      "-" = "-"
      ```

    - Replacements are only per-character. Replacing a single character with multiple characters or
      vice-versa may result in unexpected behavior.

### Example Configuration

Windows:

```toml
[paths]
ffmpeg = "~/Downloads/ffmpeg-2025-01-27-git-959b799c8d-essentials_build/bin/ffmpeg.exe"
slippi_playback = "~/AppData/Roaming/Slippi Launcher/playback/Slippi Dolphin.exe"
ssbm_iso = "~/Documents/iso/ssbm.iso"

[dolphin]
backend = "D3D12"
resolution = "1080p"
bitrate = 16000

[ffmpeg]
volume = 25

[runtime]
parallel = 0
```

Linux:

```toml
[paths]
ffmpeg = "ffmpeg"
slippi_playback = "~/.config/Slippi Launcher/playback/Slippi_Playback-x86_64.AppImage"
ssbm_iso = "~/Games/Melee.iso"

[dolphin]
backend = "OGL"
resolution = "1080p"
bitrate = 16000

[ffmpeg]
volume = 25

[runtime]
parallel = 0
```

## Notes

* If you get weird looking video (where half the width is cropped), try
  changing the video backend (see `backend` in [dolphin
  settings](#dolphin-settings) for possible options).

* Does not play nicely with WSL, since dolphin expects all paths to be relative
  to Windows.

## License

This project is licensed under the MIT License - see the [license](LICENSE.md)
file for details.


[default-settings]: ./src/slp2mp4/defaults.toml
[dolphin-video-backends-src]: https://github.com/dolphin-emu/dolphin/tree/master/Source/Core/VideoBackends
[dolphin-video-backends]: https://wiki.dolphin-emu.org/index.php?title=Configuration_Guide#Video_Backend
[releases]: ../../releases
[replay-manager]: https://github.com/jmlee337/replay-manager-for-slippi
[toml]: https://toml.io/en/
