# Version History

## In-progress

- Add build that bundles ffmpeg with the install (thanks to @ianwal for contributing!)
- Simplified `runtime.name_replacements` implementation
- The "Stop" button in the GUI now actually works :)
- Simplified multiprocessing logic - videos are now rendered "by set" instead of simultaneously
    - This simplifies the implementation significantly, and also is necessary for the future
      scoreboard functionality to work.
    - The downside is that rendering will now take slightly longer.
- Added quotes / apostrophes to the default replacement list
- Allow changing gecko codes via the config

## 3.0.7

- Various improvements around output name handling:
    - Added `runtime.name_replacements` to allow users to have arbitrary
      replacements for title names.
    - Fixed handling of titles with periods before the file extension.
    - Use ` ` instead of `_` for path joining.
    - In single mode, only consider files ending with `.slp`.
    - In zip mode, handle nested zip files better.
- Fixed bug preventing usage of directory mode
- Ensure that config paths that are expected to be files are actually files
- Added `runtime.preserve_directory_structure`

## 3.0.6

- Fixed directory and zip names getting messed up in GUI mode

## 3.0.5

- Fixed dolphin not respecting resolution settings on Windows
- Fixed `double` and `zip` modes improperly truncating paths with `.` in their
  names
- Renamed `replay_manager` mode to `zip` mode
- Improved display of mode names / descriptions in GUI
- Fixed config parsing edge cases

## 3.0.4

- Fixed `~` not being validated properly in config paths
- Use proper dolphin backend names
- Handle invalid TOML files more gracefully
- Fixed `resolution` dropdown in GUI

## 3.0.3

- Fixed a bug where `replay_manager` sometimes wouldn't work properly on
  Windows due to very long path names
- Improved output file name handling
- Changed `volume` to be an ffmpeg setting, since Dolphin framedump ignores
  volume settings apparently
- Only sanitize output filename, not whole directory
- Allow using more than 1 process per CPU

## 3.0.2

- Works on Windows again (how silly of me to assume `os.sched_getaffinity` would
  be multiplatform).

## 3.0.1

- Allow `replay_manager` to accept directories or `.zip` files.

## 3.0.0

- Totally reworked. Run modes:
    - `single`
    - `directory`
    - `replay_manager`
- Added a GUI
- Settings for volume, file output configuration, and more

## Prior

Ancient history.
