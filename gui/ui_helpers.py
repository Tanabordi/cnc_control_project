"""UI helper functions for CNC Control widgets.

Extracted from core/utils.py so widget-related helpers live in the GUI layer.
"""

from PySide6.QtWidgets import QPushButton


def _btn(text, min_h=28, enabled=False):
    b = QPushButton(text)
    b.setEnabled(enabled)
    b.setMinimumHeight(min_h)
    return b


def _set_enabled(btns, ok: bool):
    for b in btns:
        b.setEnabled(ok)
