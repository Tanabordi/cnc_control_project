import re
import time
from pathlib import Path

from PySide6.QtWidgets import QPushButton
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt


def clamp(n, lo, hi):
    return max(lo, min(hi, n))


def _btn(text, min_h=28, enabled=False):
    b = QPushButton(text)
    b.setEnabled(enabled)
    b.setMinimumHeight(min_h)
    return b


def _set_enabled(btns, ok: bool):
    for b in btns:
        b.setEnabled(ok)


def _read_text(path: str) -> list[str]:
    return Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()


def _ts():
    return time.strftime("%H:%M:%S")


def _strip_gcode_line(line: str) -> str:
    if ";" in line:
        line = line.split(";", 1)[0]
    line = re.sub(r"\(.*?\)", "", line)
    return line.strip()


def _parse_words(line: str) -> dict:
    out = {}
    for tok in line.split():
        if len(tok) < 2:
            continue
        k, v = tok[0].upper(), tok[1:]
        try:
            out[k] = int(float(v)) if k in ("G", "M") else float(v)
        except ValueError:
            pass
    return out


def parse_xyz(csv_str: str):
    parts = csv_str.split(",")
    if len(parts) < 3:
        return None
    try:
        return float(parts[0]), float(parts[1]), float(parts[2])
    except ValueError:
        return None


def extract_field(line: str, key: str):
    token = f"{key}:"
    if token not in line:
        return None
    try:
        return line.split(token, 1)[1].split("|", 1)[0].strip()
    except Exception:
        return None


def extract_state(line: str):
    if not (line.startswith("<") and line.endswith(">")):
        return None
    try:
        return line[1:-1].split("|", 1)[0].strip()
    except Exception:
        return None


def apply_theme(theme: str):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if not app:
        return

    if theme == "light":
        app.setStyle("Fusion")
        p = QPalette()
        p.setColor(QPalette.Window,          QColor(240, 240, 240))
        p.setColor(QPalette.WindowText,      QColor(0, 0, 0))
        p.setColor(QPalette.Base,            QColor(255, 255, 255))
        p.setColor(QPalette.AlternateBase,   QColor(233, 233, 233))
        p.setColor(QPalette.Text,            QColor(0, 0, 0))
        p.setColor(QPalette.Button,          QColor(240, 240, 240))
        p.setColor(QPalette.ButtonText,      QColor(0, 0, 0))
        p.setColor(QPalette.Highlight,       QColor(0, 120, 215))
        p.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        app.setPalette(p)

    else:  # dark
        app.setStyle("Fusion")
        p = QPalette()
        p.setColor(QPalette.Window,          QColor(53, 53, 53))
        p.setColor(QPalette.WindowText,      Qt.white)
        p.setColor(QPalette.Base,            QColor(35, 35, 35))
        p.setColor(QPalette.AlternateBase,   QColor(53, 53, 53))
        p.setColor(QPalette.ToolTipBase,     QColor(25, 25, 25))
        p.setColor(QPalette.ToolTipText,     Qt.white)
        p.setColor(QPalette.Text,            Qt.white)
        p.setColor(QPalette.Button,          QColor(53, 53, 53))
        p.setColor(QPalette.ButtonText,      Qt.white)
        p.setColor(QPalette.BrightText,      Qt.red)
        p.setColor(QPalette.Link,            QColor(42, 130, 218))
        p.setColor(QPalette.Highlight,       QColor(42, 130, 218))
        p.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
        p.setColor(QPalette.Disabled, QPalette.Text,       QColor(127, 127, 127))
        p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(127, 127, 127))
        app.setPalette(p)
