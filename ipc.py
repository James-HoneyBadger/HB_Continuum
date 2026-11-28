# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Compatibility alias for :mod:`hb_engine.ipc`."""
import sys
from hb_engine import ipc as _impl
sys.modules[__name__] = _impl
