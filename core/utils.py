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
        p.setColor(QPalette.Disabled, QPalette.Text,       QColor(160, 160, 160))
        p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(160, 160, 160))
        p.setColor(QPalette.PlaceholderText, QColor(140, 140, 140))
        app.setPalette(p)
        
        app.setStyleSheet("""
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                margin-top: 1.2em;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 4px;
                color: #0066cc;
                font-weight: bold;
            }
            QPushButton {
                background-color: #f5f5f5;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                padding: 5px 10px;
                color: #000000;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
                border-color: #999999;
            }
            QPushButton:pressed {
                background-color: #d8d8d8;
            }
            QPushButton:disabled {
                background-color: #f0f0f0;
                color: #a0a0a0;
                border: 1px solid #e0e0e0;
            }
            QLineEdit, QTextEdit {
                border: 1px solid #cccccc;
                border-radius: 3px;
                background-color: #fafafa;
                color: #000000;
                padding: 4px;
            }
            QTableWidget {
                border: 1px solid #cccccc;
                border-radius: 3px;
                background-color: #ffffff;
                color: #000000;
                alternate-background-color: #f9f9f9;
            }
            QTableWidget::item:selected {
                background-color: #0066cc;
                color: white;
            }
            QHeaderView::section {
                background-color: #e0e0e0;
                color: #000000;
                padding: 4px;
                border: 1px solid #d0d0d0;
            }
        """)

    else:  # dark
        app.setStyle("Fusion")
        p = QPalette()
        p.setColor(QPalette.Window,          QColor(45, 45, 45))
        p.setColor(QPalette.WindowText,      Qt.white)
        p.setColor(QPalette.Base,            QColor(30, 30, 30))
        p.setColor(QPalette.AlternateBase,   QColor(40, 40, 40))
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
        p.setColor(QPalette.PlaceholderText, QColor(160, 160, 160))
        app.setPalette(p)
        
        app.setStyleSheet("""
            QGroupBox {
                background-color: #2b2b2b;
                border: 1px solid #444444;
                border-radius: 6px;
                margin-top: 1.2em;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 4px;
                color: #4da6ff;
                font-weight: bold;
            }
            QPushButton {
                background-color: #404040;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 5px 10px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #505050;
                border-color: #777777;
            }
            QPushButton:pressed {
                background-color: #303030;
            }
            QPushButton:disabled {
                background-color: #353535;
                color: #777777;
                border: 1px solid #444444;
            }
            QLineEdit, QTextEdit {
                border: 1px solid #555555;
                border-radius: 3px;
                background-color: #1e1e1e;
                color: #ffffff;
                padding: 4px;
            }
            QTableWidget {
                border: 1px solid #555555;
                border-radius: 3px;
                background-color: #1e1e1e;
                color: #ffffff;
                alternate-background-color: #2a2a2a;
            }
            QTableWidget::item:selected {
                background-color: #2980b9;
                color: white;
            }
            QHeaderView::section {
                background-color: #333333;
                color: white;
                padding: 4px;
                border: 1px solid #444444;
            }
        """)
