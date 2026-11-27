# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Compatibility alias for :mod:`hb_engine.sync_lock`."""
import sys
from hb_engine import sync_lock as _impl
sys.modules[__name__] = _impl
