"""Compatibility shim for ``setuptools`` legacy ``setup.py``.

The canonical project metadata now lives in ``pyproject.toml`` (PEP 621).
This file is kept so that ``pip install -e .`` and tooling that still
invokes ``setup.py`` keep working.
"""

from setuptools import setup

setup()
