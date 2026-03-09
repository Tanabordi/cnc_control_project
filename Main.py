import sys
import locale

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication

from app import App


if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, "C")
    QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedStates))
    app = QApplication(sys.argv)
    w = App()
    w.show()
    sys.exit(app.exec())
