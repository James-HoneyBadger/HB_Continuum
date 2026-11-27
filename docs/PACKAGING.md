# Packaging the desktop application

The Tauri shell is only a UI: all archive work happens in the Python engine.
A packaged app therefore ships two pieces — the shell and a standalone engine
binary — and must not depend on a system `python3` or a repository checkout.

## Engine package layout

The implementation is the `hb_engine` package. `dispatch.py` is the stable CLI
and PyInstaller entry point; it loads `hb_engine.dispatch` and calls `main()`.
Every engine module uses package-relative imports. Top-level names such as
`catalog.py`, `ipc.py` and `schedule.py` are compatibility aliases that point
at the package module, preserving existing imports and test patch targets.

## Building the engine

`scripts/build_engine.py` builds `dispatch.py` with PyInstaller and places the
result where Tauri expects a sidecar:

```sh
python3 -m pip install pyinstaller
python3 scripts/build_engine.py
```

It produces:

- `dist/hb-engine` (`hb-engine.exe` on Windows) — a one-file executable;
- `src-tauri/binaries/hb-engine-<host-triple>` — the copy named for Tauri's
  `externalBin` entry. The sidecar is declared in
  `src-tauri/tauri.bundle.conf.json`, not in the base config: `tauri dev`
  and `cargo build` must work on a checkout that has not built the engine
  yet, while a release build requires it.

The build passes `--collect-submodules hb_engine`, so adding an engine module
cannot leave it out of the sidecar. `--no-copy` builds without copying,
`--print-command` shows the PyInstaller invocation, and `--smoke` runs the
built binary against a temporary archive
(`--version`, `import`, `search`, `health`). CI runs `--no-copy --smoke` on
Ubuntu, macOS and Windows.

The binary is **host-specific**: build it on each target platform, and per
architecture for macOS universal builds. Cross-compiling is not supported by
this script.

## How the shell finds the engine

At startup the shell resolves, in order:

1. `HB_ENGINE` — an explicit path to a standalone engine binary;
2. `hb-engine` (or `hb-engine.exe`) next to the application executable, which
   is where Tauri installs the sidecar;
3. `HB_ENGINE_SCRIPT` — an explicit path to `dispatch.py`;
4. `dispatch.py` next to the executable, three directories up (a
   `src-tauri/target/<profile>` build), or in the repository recorded at
   compile time (development only).

If none exists, startup fails with a message naming the missing sidecar
rather than a bare spawn error. Steps 3–4 are a development convenience;
a released app should rely on steps 1–2.

## Packaging

With the engine built for the current host:

```sh
cd frontend && npm install
npm run tauri -- build --config src-tauri/tauri.bundle.conf.json
```

The npm script runs Tauri from the repository root, so the overlay path is
relative to it. Tauri merges the overlay into `tauri.conf.json`, bundles
`binaries/hb-engine-<host-triple>` as an external binary and places it beside
the app executable. A debug build with the overlay
(`tauri build --debug --no-bundle --config ...`) is enough to verify the
layout: it copies `hb-engine` next to the app, which is where the shell looks
first after `HB_ENGINE`.

`cargo test` in `src-tauri` covers the resolution order (bundled binary
preferred, script fallback, explicit overrides).

## Optional dependencies

The engine imports `keyring` and `cryptography` lazily for credential storage
and encryption fallbacks, and `tkinter` for the legacy Tkinter workstation.
PyInstaller includes whichever of these are installed in the build
environment; otherwise those features fail with their normal "not installed"
errors. The Tauri shell never needs Tkinter, so a build machine without it
still produces a fully functional shell engine.

## Limitations

- No signing, notarization or auto-update is implemented; those are release
  decisions for the repository owner.
- The engine binary embeds the Python runtime, so it is roughly 30 MB.
- The PyInstaller build is validated on the three CI platforms, but not yet
  reproduced on a machine without network access to PyPI.
