# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Compatibility alias for :mod:`hb_engine.documents`."""
import sys
from hb_engine import documents as _impl
sys.modules[__name__] = _impl
