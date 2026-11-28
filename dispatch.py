# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""HB Continuum CLI entry point.

The implementation lives in :mod:`hb_engine.dispatch`. This wrapper keeps
`python3 dispatch.py ...` and the PyInstaller entry contract unchanged.
"""
import sys
from hb_engine import dispatch as _impl

if __name__ == '__main__':
    raise SystemExit(_impl.main(sys.argv[1:]))
sys.modules[__name__] = _impl
