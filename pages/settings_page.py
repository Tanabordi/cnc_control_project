import re

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QFormLayout, QTextEdit,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox
)

from settings import AppSettings, save_settings, load_settings, SETTINGS_PATH
from utils import _btn, _ts, apply_theme


GRBL_DESC = {
    0: "Step pulse time (us)", 1: "Step idle delay (ms)",
    2: "Step pulse invert mask", 3: "Step direction invert mask",
    4: "Invert step enable pin", 5: "Invert limit pins",
    6: "Invert probe pin", 10: "Status report options",
    11: "Junction deviation (mm)", 12: "Arc tolerance (mm)",
    13: "Report in inches", 20: "Soft limits enable",
    21: "Hard limits enable", 22: "Homing cycle enable",
    23: "Homing direction invert", 24: "Homing feed (mm/min)",
    25: "Homing seek (mm/min)", 26: "Homing debounce (ms)",
    27: "Homing pull-off (mm)", 30: "Max spindle speed (RPM)",
    31: "Min spindle speed (RPM)", 32: "Laser mode enable",
    100: "X steps/mm", 101: "Y steps/mm", 102: "Z steps/mm",
    110: "X max rate (mm/min)", 111: "Y max rate (mm/min)", 112: "Z max rate (mm/min)",
    120: "X acceleration (mm/s2)", 121: "Y acceleration (mm/s2)", 122: "Z acceleration (mm/s2)",
    130: "X max travel (mm)", 131: "Y max travel (mm)", 132: "Z max travel (mm)",
}


class SettingsPage(QWidget):
    def __init__(self, app_ref):
        super().__init__()
        self.app = app_ref
        self._param_buffer: list[str] = []
        self._collecting_params = False
        self._collect_timer = QTimer(self)
        self._collect_timer.setSingleShot(True)
        self._collect_timer.timeout.connect(self._finish_collect_params)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_grbl_tab(), "GRBL Parameters")
        root.addWidget(tabs, 1)

        root.addWidget(QLabel("Log:"))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(120)
        self.log_view.setMaximumHeight(200)
        self.log_view.setLineWrapMode(QTextEdit.NoWrap)
        root.addWidget(self.log_view)

        self.app.worker.grbl_param_line.connect(self._on_grbl_param_line)

    # ---- Tab: General -------------------------------------------------------
    def _build_general_tab(self) -> QWidget:
        tab = QWidget()
        v = QVBoxLayout(tab)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(8)

        grp = QGroupBox("Settings")
        form = QFormLayout()

        self.baud_box = QComboBox()
        self.baud_box.addItems(["9600", "19200", "38400", "57600", "115200",
                                 "230400", "250000", "460800", "921600"])
        self.poll_ms = QSpinBox()
        self.poll_ms.setRange(30, 2000)
        self.poll_ms.setValue(150)
        self.auto_unlock_connect = QCheckBox("Auto $X after Connect")
        self.auto_unlock_reset   = QCheckBox("Auto $X after Reset")

        def _dbl():
            d = QDoubleSpinBox()
            d.setRange(-99999, 99999)
            return d

        self.xmin, self.xmax = _dbl(), _dbl()
        self.ymin, self.ymax = _dbl(), _dbl()
        self.zmin, self.zmax = _dbl(), _dbl()

        self.safe_z_spin = QDoubleSpinBox()
        self.safe_z_spin.setRange(-9999, 9999)
        self.safe_z_spin.setDecimals(2)
        self.safe_z_spin.setValue(5.0)

        self.theme_box = QComboBox()
        self.theme_box.addItems(["dark", "light"])

        form.addRow("Baud rate", self.baud_box)
        form.addRow("Status poll interval (ms)", self.poll_ms)
        form.addRow("", self.auto_unlock_connect)
        form.addRow("", self.auto_unlock_reset)
        form.addRow(QLabel("Soft Limits (mm)"), QLabel(""))
        for k, w in [("X min", self.xmin), ("X max", self.xmax),
                     ("Y min", self.ymin), ("Y max", self.ymax),
                     ("Z min", self.zmin), ("Z max", self.zmax)]:
            form.addRow(k, w)
        form.addRow(QLabel(""))
        form.addRow("Safe Z height (mm)", self.safe_z_spin)
        form.addRow("Theme", self.theme_box)
        grp.setLayout(form)
        v.addWidget(grp)

        btns = QHBoxLayout()
        self.apply_btn  = _btn("Apply (No Save)", enabled=True)
        self.save_btn   = _btn("Save to settings.json", enabled=True)
        self.reload_btn = _btn("Reload from settings.json", enabled=True)
        btns.addWidget(self.apply_btn)
        btns.addWidget(self.save_btn)
        btns.addWidget(self.reload_btn)
        btns.addStretch(1)
        v.addLayout(btns)
        v.addStretch(1)

        self.apply_btn.clicked.connect(self.apply_only)
        self.save_btn.clicked.connect(self.save_and_apply)
        self.reload_btn.clicked.connect(self.reload_from_file)
        self.theme_box.currentTextChanged.connect(apply_theme)
        return tab

    # ---- Tab: GRBL Parameters -----------------------------------------------
    def _build_grbl_tab(self) -> QWidget:
        tab = QWidget()
        v = QVBoxLayout(tab)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        btns = QHBoxLayout()
        self.read_grbl_btn  = _btn("Read from GRBL ($$)", enabled=False)
        self.test_conn_btn  = _btn("Test Connection ($I)", enabled=False)
        self.write_grbl_btn = _btn("Write to GRBL", enabled=False)
        btns.addWidget(self.read_grbl_btn)
        btns.addWidget(self.test_conn_btn)
        btns.addWidget(self.write_grbl_btn)
        btns.addStretch(1)
        v.addLayout(btns)

        self.params_table = QTableWidget()
        self.params_table.setColumnCount(3)
        self.params_table.setHorizontalHeaderLabels(["Parameter", "Value", "Description"])
        self.params_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.params_table.setAlternatingRowColors(True)
        self.params_table.verticalHeader().setVisible(False)
        self.params_table.verticalHeader().setDefaultSectionSize(22)
        hh = self.params_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        v.addWidget(self.params_table, 1)

        self.read_grbl_btn.clicked.connect(self._read_grbl_params)
        self.test_conn_btn.clicked.connect(self._test_connection)
        self.write_grbl_btn.clicked.connect(self._write_grbl_params)
        return tab

    # ---- GRBL params collect ------------------------------------------------
    def _read_grbl_params(self):
        self._param_buffer.clear()
        self._collecting_params = True
        self.app.worker.send_line("$$")
        self._collect_timer.start(2000)
        self.append_log("Reading GRBL parameters ($$)...")

    def _on_grbl_param_line(self, line: str):
        if self._collecting_params:
            self._param_buffer.append(line)

    def _finish_collect_params(self):
        self._collecting_params = False
        if not self._param_buffer:
            self.append_log("No parameters received. Check connection.")
            return
        self._populate_params_table(self._param_buffer)
        self.write_grbl_btn.setEnabled(True)
        self.append_log(f"Received {len(self._param_buffer)} parameters.")

    def _populate_params_table(self, lines: list[str]):
        self.params_table.setRowCount(0)
        pat = re.compile(r'^\$(\d+)=([^\s(]+)\s*(?:\((.*)\))?')
        for line in lines:
            m = pat.match(line.strip())
            if not m:
                continue
            num  = int(m.group(1))
            val  = m.group(2)
            desc = m.group(3) or GRBL_DESC.get(num, "")
            r = self.params_table.rowCount()
            self.params_table.insertRow(r)
            self.params_table.setItem(r, 0, QTableWidgetItem(f"${num}"))
            self.params_table.setItem(r, 1, QTableWidgetItem(val))
            self.params_table.setItem(r, 2, QTableWidgetItem(desc))

    def _test_connection(self):
        self.app.worker.send_line("$I")
        self.append_log("Sent $I — check Log for firmware info.")

    def _write_grbl_params(self):
        rows = self.params_table.rowCount()
        if rows == 0:
            return
        ret = QMessageBox.question(
            self, "Write to GRBL",
            f"send {rows} parameters to GRBL?",
            QMessageBox.Yes | QMessageBox.No
        )
        if ret != QMessageBox.Yes:
            return
        for r in range(rows):
            param = self.params_table.item(r, 0)
            val   = self.params_table.item(r, 1)
            if param and val:
                self.app.worker.send_line(f"{param.text()}={val.text()}")
        self.append_log(f"Sent {rows} parameters to GRBL.")

    # ---- Log ----------------------------------------------------------------
    def append_log(self, line: str):
        self.log_view.append(f"[{_ts()}] {line}")

    # ---- Connection state ---------------------------------------------------
    def set_connected(self, ok: bool):
        self.read_grbl_btn.setEnabled(ok)
        self.test_conn_btn.setEnabled(ok)
        if not ok:
            self.write_grbl_btn.setEnabled(False)

    # ---- Load / Read / Apply ------------------------------------------------
    def load_into_ui(self, s: AppSettings):
        idx = self.baud_box.findText(str(int(s.baud)))
        self.baud_box.setCurrentIndex(idx if idx >= 0 else self.baud_box.findText("115200"))
        self.poll_ms.setValue(int(s.status_poll_ms))
        self.auto_unlock_connect.setChecked(bool(s.auto_unlock_after_connect))
        self.auto_unlock_reset.setChecked(bool(s.auto_unlock_after_reset))
        self.xmin.setValue(float(s.xmin)); self.xmax.setValue(float(s.xmax))
        self.ymin.setValue(float(s.ymin)); self.ymax.setValue(float(s.ymax))
        self.zmin.setValue(float(s.zmin)); self.zmax.setValue(float(s.zmax))
        self.safe_z_spin.setValue(float(s.safe_z))
        idx_t = self.theme_box.findText(s.theme)
        self.theme_box.setCurrentIndex(idx_t if idx_t >= 0 else 0)

    def read_from_ui(self) -> AppSettings:
        s = self.app.settings
        s.baud = int(self.baud_box.currentText())
        s.status_poll_ms = int(self.poll_ms.value())
        s.auto_unlock_after_connect = bool(self.auto_unlock_connect.isChecked())
        s.auto_unlock_after_reset = bool(self.auto_unlock_reset.isChecked())
        s.xmin = float(self.xmin.value()); s.xmax = float(self.xmax.value())
        s.ymin = float(self.ymin.value()); s.ymax = float(self.ymax.value())
        s.zmin = float(self.zmin.value()); s.zmax = float(self.zmax.value())
        s.safe_z = float(self.safe_z_spin.value())
        s.theme = self.theme_box.currentText()
        return s

    def _sync_limits_to_grbl(self):
        s = self.app.settings
        w = self.app.worker
        if not w.ser or not w.ser.is_open:
            return
        tx = max(abs(s.xmin), abs(s.xmax))
        ty = max(abs(s.ymin), abs(s.ymax))
        tz = max(abs(s.zmin), abs(s.zmax))
        w.send_line(f"$130={tx:.3f}")
        w.send_line(f"$131={ty:.3f}")
        w.send_line(f"$132={tz:.3f}")
        self.append_log(f"Synced to GRBL: $130={tx:.3f}, $131={ty:.3f}, $132={tz:.3f}")

    def apply_only(self):
        self.read_from_ui()
        self.app.apply_settings_to_runtime()
        self._sync_limits_to_grbl()
        self.app.on_log("Settings applied (not saved).")

    def save_and_apply(self):
        self.read_from_ui()
        ok = save_settings(self.app.settings)
        self.app.apply_settings_to_runtime()
        self._sync_limits_to_grbl()
        self.app.on_log(f"Saved settings: {SETTINGS_PATH}" if ok else "Save settings failed.")

    def reload_from_file(self):
        self.app.settings = load_settings()
        self.load_into_ui(self.app.settings)
        self.app.apply_settings_to_runtime()
        self.app.on_log("Reloaded settings from file.")
