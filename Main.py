import sys
import locale

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication

from gui.app import MainWindow


if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, "C")
    QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedStates))
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


