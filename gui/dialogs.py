"""Dialog classes for CNC Control."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QGroupBox,
    QCheckBox, QSpinBox, QLabel, QDialogButtonBox
)


class PanelConfigDialog(QDialog):
    """Dialog for configuring panel export settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export G-code")
        self.setModal(True)
        self.setMinimumWidth(260)

        layout = QVBoxLayout(self)

        self.panel_cb = QCheckBox("Export as Panel (replicate waypoints)")
        layout.addWidget(self.panel_cb)

        self.panel_group = QGroupBox("Panel Settings")
        self.panel_group.setEnabled(False)
        pg = QFormLayout(self.panel_group)

        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 50)
        self.rows_spin.setValue(1)

        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 50)
        self.cols_spin.setValue(1)

        self.total_lbl = QLabel("Total: 1 PCB")

        pg.addRow("Rows:", self.rows_spin)
        pg.addRow("Columns:", self.cols_spin)
        pg.addRow(self.total_lbl)
        layout.addWidget(self.panel_group)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self.panel_cb.toggled.connect(self.panel_group.setEnabled)
        self.rows_spin.valueChanged.connect(self._update_total)
        self.cols_spin.valueChanged.connect(self._update_total)

    def _update_total(self):
        n = self.rows_spin.value() * self.cols_spin.value()
        self.total_lbl.setText(f"Total: {n} PCBs")

    def is_panel(self):
        return self.panel_cb.isChecked()

    def get_layout(self):
        return self.rows_spin.value(), self.cols_spin.value()
