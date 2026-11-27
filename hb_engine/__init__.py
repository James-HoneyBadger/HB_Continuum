# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""HB Continuum engine package.

The CLI entry point remains the top-level ``dispatch.py`` wrapper. Engine
modules live here so the desktop IPC server, packaging scripts and tests use
one implementation, while the historical top-level import paths keep working
through thin compatibility modules.
"""
