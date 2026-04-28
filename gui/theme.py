"""Application theme (dark/light palette) for CNC Control.

Extracted from core/utils.py so theme logic lives in the GUI layer.
"""

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt


def apply_theme(theme: str):
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
