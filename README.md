# ETS2 Triple Monitor Configurator

A small cross-platform desktop app (Windows, Linux, macOS) that generates a
`multimon_config.sii` file for **Euro Truck Simulator 2** triple-monitor setups.
You enter your monitor size, bezel, viewing distance and side-monitor angle; the app
computes the FOV and per-monitor heading offsets (including the bezel correction)
and writes the file.

## Download

Grab the build for your system from the
[Releases](../../releases/latest) page. No Python or Qt installation needed.

| System  | File                                          | How to run |
|---------|-----------------------------------------------|------------|
| Windows | `ETS2-Triple-Monitor-windows-x64.exe`         | Double-click |
| Linux   | `ETS2-Triple-Monitor-linux-x64.tar.gz`        | `tar xzf ...` then `./ETS2-Triple-Monitor` |
| macOS   | `ETS2-Triple-Monitor-macos-arm64.zip` (Apple Silicon) | Unzip, open the `.app` |

### First-run security warnings (the builds are unsigned)

- **Windows:** SmartScreen may say "Windows protected your PC". Click
  *More info* → *Run anyway*.
- **macOS:** Gatekeeper blocks unsigned apps. Right-click the app → *Open* → *Open*.
  If it still refuses, run
  `xattr -dr com.apple.quarantine /path/to/ETS2-Triple-Monitor.app`.
- **Linux:** make sure the file is executable (`chmod +x ETS2-Triple-Monitor`).
  Qt needs the `libxcb-cursor0` system package on most distros
  (`sudo apt install libxcb-cursor0` on Debian/Ubuntu).

## Usage

1. **Screens** – visible panel width/height, total bezel between monitors,
   eye-to-screen distance, and the physical angle of the side monitors.
2. **Camera** – camera space offset, pitch and roll.
3. **FOV** – automatic (computed from size and distance) or manual, plus optional
   per-monitor relative offsets.
4. **Advanced** – interior/exterior rendering and the frustum subrect
   (leave at `0, 0, 1, 1` for a normal triple setup).
5. Click **Preview calculations** to check the numbers, then
   **Generate multimon_config.sii** and save the file. The save dialog opens in the
   ETS2 user-data folder when it can find it.

Place the generated file where your ETS2 setup expects `multimon_config.sii`
(typically the game's user-data folder; check your game/mod documentation).

## How the numbers are computed

- FOV = `2 · atan((size / 2) / distance)`, for width and height.
- Bezel correction = `atan((width + bezel) / 2 / distance) − atan(width / 2 / distance)`.
- Left heading = `side angle + bezel correction`; right heading is its negative;
  the center monitor is `0`.

## Run from source

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m ets2_triple_monitor    # start the app
pytest                           # run the tests
```

## Build a standalone executable locally

```bash
pip install -e ".[build]"
pyinstaller --onefile --windowed --noconfirm --clean \
  --name ETS2-Triple-Monitor --paths src packaging/run.py
```

(On macOS drop `--onefile`; PyInstaller then produces a `.app` bundle in `dist/`.)
PyInstaller cannot cross-compile, so each OS must be built on that OS — that is
what the GitHub Actions workflow does.

## Publishing a release

```bash
# bump __version__ in src/ets2_triple_monitor/__init__.py, commit, then:
git tag v1.0.1
git push origin v1.0.1
```

The `Build & Release` workflow runs the tests, builds Windows / Linux / macOS
binaries, and attaches them to a new GitHub Release with auto-generated notes.
You can also run it manually from the *Actions* tab (it will build artifacts
without publishing a release when run on a branch; choose an existing tag to
attach the artifacts to its release.

## Project layout

```
src/ets2_triple_monitor/
    core.py      # maths + .sii generation (no Qt, unit-tested)
    gui.py       # PySide6 interface
packaging/run.py # PyInstaller entry point
tests/           # pytest tests for core.py
.github/workflows/
    ci.yml       # tests on Windows/Linux/macOS
    release.yml  # build + publish binaries on version tags
```

## License

MIT — see [LICENSE](LICENSE). The app uses PySide6 (LGPL).
