# ADR-001: Desktop application framework

- **Status:** Accepted (PoC in progress)
- **Date:** 2026-11-26

## Context

The Tkinter workstation serves as the current desktop interface. The
directive calls for a modern, cross-platform research workstation and
proposes Tauri 2 (Rust shell, Vue 3 frontend) while requiring an honest
evaluation of alternatives.

## Decision

Adopt **Tauri 2 with a Vue 3 + TypeScript + Vite frontend**, retaining the
Python engine as a managed subprocess driven by the versioned IPC protocol
(ADR-003).

The Tkinter interface remains the functional fallback until desktop parity
is established.

## Alternatives considered

- **PySide6/QML:** strong Python fit, but a heavier runtime footprint and a
  less mature cross-platform packaging story than Tauri's system webview.
- **Keep Tkinter only:** lowest risk, but limited as the product grows into
  a data-dense research workstation.
- **Bundled Chromium (Electron):** rejected — large footprint for no
  demonstrated benefit over the native system webview.

## Consequences

- Two toolchains (Python + Rust/Node) to maintain; the Rust shell is a thin
  layer that owns only subprocess lifecycle and IPC marshalling.
- Small distributable size via the OS webview, but platform-specific
  webview dependencies (webkit2gtk on Linux, WKWebView on macOS, WebView2
  on Windows) are required.
- Packaging the Python engine as a bundled sidecar remains open; the PoC
  resolves `dispatch.py` relative to the source tree and documents this as
  a limitation.
