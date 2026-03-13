from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QFormLayout, QTextEdit, QLineEdit,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QGridLayout, QSizePolicy, QSplitter, QApplication, QFileDialog
)

from utils import _btn, _ts


class WaypointTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)


class ControlPage(QWidget):
    def __init__(self, app_ref):
        super().__init__()
        self.app = app_ref

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # --- Connection bar ---
        conn_bar = QGroupBox()
        c = QHBoxLayout()
        c.setContentsMargins(8, 8, 8, 8)
        self.port_box = QComboBox()
        self.refresh_btn = _btn("Refresh Ports", enabled=True)
        self.connect_btn = _btn("Connect", enabled=True)
        self.disconnect_btn = _btn("Disconnect", enabled=False)
        c.addWidget(QLabel("Port:"))
        c.addWidget(self.port_box, 1)
        c.addWidget(self.refresh_btn)
        c.addWidget(self.connect_btn)
        c.addWidget(self.disconnect_btn)
        conn_bar.setLayout(c)
        root.addWidget(conn_bar)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ===== Left panel =====
        left = QWidget()
        L = QVBoxLayout(left)
        L.setContentsMargins(0, 0, 0, 0)
        L.setSpacing(8)

        teach = QHBoxLayout()
        teach.addWidget(QLabel("Feed to NEXT:"))
        self.wp_feed = QSpinBox()
        self.wp_feed.setRange(1, 20000)
        self.wp_feed.setValue(1200)
        teach.addWidget(self.wp_feed)

        teach.addWidget(QLabel("Time (s):"))
        self.wp_laser_time = QDoubleSpinBox()
        self.wp_laser_time.setRange(0.0, 9999.0)
        self.wp_laser_time.setDecimals(2)
        self.wp_laser_time.setValue(0.50)
        teach.addWidget(self.wp_laser_time)

        teach.addWidget(QLabel("Z safe:"))
        self.wp_z_safe = QDoubleSpinBox()
        self.wp_z_safe.setRange(-99999.0, 0.0)
        self.wp_z_safe.setDecimals(3)
        self.wp_z_safe.setValue(-2.0)
        teach.addWidget(self.wp_z_safe)
        teach.addStretch(1)
        L.addLayout(teach)

        self.load_points_gcode_btn = _btn("Load Points (.gcode)")
        self.load_csv_pcb_btn = _btn("Import PCB CSV")
        self.capture_btn = _btn("Capture Waypoint")
        self.update_btn = _btn("Update Selected")
        self.delete_btn = _btn("Delete Selected")
        self.clear_btn = _btn("Clear Points")
        self.preview3d_btn = _btn("Preview 3D")
        self.export_gcode_btn = _btn("Export G-code (.gcode)")

        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(6)
        for b in [self.load_points_gcode_btn, self.load_csv_pcb_btn, self.capture_btn,
                  self.update_btn, self.delete_btn, self.clear_btn,
                  self.preview3d_btn, self.export_gcode_btn]:
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn_bar.addWidget(b)
        L.addLayout(btn_bar)

        self.wp_table = WaypointTable(self)
        self.wp_table.setColumnCount(6)
        self.wp_table.setHorizontalHeaderLabels(["Number", "Position (X,Y)", "Z work", "Z safe", "Speed(F)", "Time (s)"])
        self.wp_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.wp_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.wp_table.setSelectionMode(QTableWidget.SingleSelection)
        self.wp_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        L.addWidget(self.wp_table, 1)

        self.wp_table.cellClicked.connect(self.app.on_waypoint_clicked)

        # --- Log (inside left panel) ---
        log_box = QGroupBox("Log")
        lv = QVBoxLayout(log_box)
        lv.setContentsMargins(8, 8, 8, 8)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(120)
        self.log_view.setMaximumHeight(220)
        self.log_view.setLineWrapMode(QTextEdit.NoWrap)
        lv.addWidget(self.log_view)
        clear_row = QHBoxLayout()
        self.clear_log_btn = _btn("Clear Log", enabled=True)
        self.copy_log_btn = _btn("Copy Log", enabled=True)
        self.save_log_btn = _btn("Save Log", enabled=True)
        self.clear_log_btn.clicked.connect(self.log_view.clear)
        self.copy_log_btn.clicked.connect(
            lambda: QApplication.clipboard().setText(self.log_view.toPlainText())
        )
        self.save_log_btn.clicked.connect(self._save_log)
        clear_row.addWidget(self.clear_log_btn)
        clear_row.addWidget(self.copy_log_btn)
        clear_row.addWidget(self.save_log_btn)
        clear_row.addStretch(1)
        lv.addLayout(clear_row)
        L.addWidget(log_box)

        # --- Console (inside left panel) ---
        console_box = QGroupBox("Console")
        cv = QVBoxLayout(console_box)
        cv.setContentsMargins(8, 8, 8, 8)
        console_row = QHBoxLayout()
        self.console_input = QLineEdit()
        self.console_input.setPlaceholderText("Send GRBL command (e.g. $I, ?, $$, G28, M5 ...)")
        self.console_send_btn = _btn("Send", enabled=False)
        console_row.addWidget(self.console_input, 1)
        console_row.addWidget(self.console_send_btn)
        cv.addLayout(console_row)
        L.addWidget(console_box)

        # ===== Right panel =====
        right = QWidget()
        R = QVBoxLayout(right)
        R.setContentsMargins(0, 0, 0, 0)
        R.setSpacing(8)

        status_box = QGroupBox("State")
        sg = QVBoxLayout(status_box)
        sg.setContentsMargins(8, 8, 8, 8)
        sg.setSpacing(4)

        def _coord_field():
            f = QLineEdit()
            f.setReadOnly(True)
            f.setAlignment(Qt.AlignRight)
            f.setFixedWidth(80)
            f.setText("0.000")
            return f

        sg.addWidget(QLabel("Work coordinates:"))
        wrow = QHBoxLayout()
        self.wpos_x = _coord_field()
        self.wpos_y = _coord_field()
        self.wpos_z = _coord_field()
        wrow.addWidget(self.wpos_x)
        wrow.addWidget(self.wpos_y)
        wrow.addWidget(self.wpos_z)
        sg.addLayout(wrow)

        sg.addWidget(QLabel("Machine coordinates:"))
        mrow = QHBoxLayout()
        self.mpos_x = _coord_field()
        self.mpos_y = _coord_field()
        self.mpos_z = _coord_field()
        mrow.addWidget(self.mpos_x)
        mrow.addWidget(self.mpos_y)
        mrow.addWidget(self.mpos_z)
        sg.addLayout(mrow)

        sstat = QHBoxLayout()
        sstat.addWidget(QLabel("Status:"))
        self.state_lbl = QLabel("-")
        sstat.addWidget(self.state_lbl, 1)
        sg.addLayout(sstat)

        pnrow = QHBoxLayout()
        pnrow.addWidget(QLabel("Pins (Pn):"))
        self.pn_lbl = QLabel("-")
        pnrow.addWidget(self.pn_lbl, 1)
        sg.addLayout(pnrow)

        R.addWidget(status_box)

        jog_box = QGroupBox("Jog")
        jog_root = QVBoxLayout(jog_box)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        self.btn_up = _btn("▲", min_h=48)
        self.btn_down = _btn("▼", min_h=48)
        self.btn_left = _btn("◀", min_h=48)
        self.btn_right = _btn("▶", min_h=48)
        self.btn_stop = _btn("⦸", min_h=48)
        self.btn_z_up = _btn("▲", min_h=48)
        self.btn_z_down = _btn("▼", min_h=48)

        self.jog_buttons = [self.btn_up, self.btn_down, self.btn_left,
                            self.btn_right, self.btn_stop, self.btn_z_up, self.btn_z_down]
        for b in self.jog_buttons:
            b.setMinimumSize(QSize(48, 48))
            b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        grid.addWidget(self.btn_up, 0, 1)
        grid.addWidget(self.btn_left, 1, 0)
        grid.addWidget(self.btn_stop, 1, 1)
        grid.addWidget(self.btn_right, 1, 2)
        grid.addWidget(self.btn_down, 2, 1)
        grid.addWidget(self.btn_z_up, 0, 4)
        grid.addWidget(self.btn_z_down, 2, 4)
        jog_root.addLayout(grid)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Step:"))
        self.step_mode = QComboBox()
        self.step_mode.addItems(["0.1", "1", "10", "Custom"])
        self.step_mm = QDoubleSpinBox()
        self.step_mm.setRange(0.01, 1000)
        self.step_mm.setValue(100.0)
        self.step_mm.setEnabled(False)
        row1.addWidget(self.step_mode, 1)
        row1.addWidget(self.step_mm, 1)
        jog_root.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Feed:"))
        self.feed = QSpinBox()
        self.feed.setRange(1, 20000)
        self.feed.setValue(2000)
        row2.addWidget(self.feed, 1)
        jog_root.addLayout(row2)

        self.keyboard_cb = QCheckBox("Keyboard control")
        self.keyboard_cb.setChecked(True)
        jog_root.addWidget(self.keyboard_cb)

        R.addWidget(jog_box)

        move_group = QGroupBox("Move to Target (Absolute, mm)")
        mv = QFormLayout(move_group)
        self.tx = QDoubleSpinBox()
        self.tx.setRange(-99999, 99999)
        self.tx.setValue(0)
        self.ty = QDoubleSpinBox()
        self.ty.setRange(-99999, 99999)
        self.ty.setValue(0)
        self.tz = QDoubleSpinBox()
        self.tz.setRange(-99999, 99999)
        self.tz.setValue(0)
        self.move_btn = _btn("Move (G1)")
        mv.addRow("X", self.tx)
        mv.addRow("Y", self.ty)
        mv.addRow("Z", self.tz)
        mv.addRow(self.move_btn)
        R.addWidget(move_group)

        self.home_btn = _btn("Home ($H)")
        self.unlock_btn = _btn("Unlock ($X)")
        self.zero_btn = _btn("Set Work Zero (G54)")
        self.go_zero_btn = _btn("Go Machine Zero (G53)")
        self.reset_btn = _btn("Reset (Ctrl+X)")
        self.estop_btn = _btn("E-STOP")
        self.auto_unlock_cb = QCheckBox("Auto $X after Reset")

        act1 = QHBoxLayout()
        act1.addWidget(self.home_btn, 1)
        act1.addWidget(self.unlock_btn, 1)
        act2 = QHBoxLayout()
        act2.addWidget(self.zero_btn, 1)
        act2.addWidget(self.go_zero_btn, 1)
        act3 = QHBoxLayout()
        act3.addWidget(self.reset_btn, 2)
        act3.addWidget(self.auto_unlock_cb, 2)
        act3.addWidget(self.estop_btn, 1)
        R.addLayout(act1)
        R.addLayout(act2)
        R.addLayout(act3)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        self.console_input.returnPressed.connect(self.app.send_console_command)
        self.console_send_btn.clicked.connect(self.app.send_console_command)

        self.max_log_lines = 400

        # ---- signals ----
        self.refresh_btn.clicked.connect(self.app.refresh_ports)
        self.connect_btn.clicked.connect(self.app.do_connect)
        self.disconnect_btn.clicked.connect(self.app.do_disconnect)

        self.step_mode.currentTextChanged.connect(self.app.on_step_mode)

        self.btn_left.clicked.connect(lambda: self.app.jog("X", -self.app.get_step()))
        self.btn_right.clicked.connect(lambda: self.app.jog("X", +self.app.get_step()))
        self.btn_up.clicked.connect(lambda: self.app.jog("Y", +self.app.get_step()))
        self.btn_down.clicked.connect(lambda: self.app.jog("Y", -self.app.get_step()))
        self.btn_z_up.clicked.connect(lambda: self.app.jog("Z", +self.app.get_step()))
        self.btn_z_down.clicked.connect(lambda: self.app.jog("Z", -self.app.get_step()))
        self.btn_stop.clicked.connect(self.app.worker.jog_cancel)

        self.home_btn.clicked.connect(self.app.do_home)
        self.unlock_btn.clicked.connect(lambda: self.app.worker.send_line("$X"))
        self.zero_btn.clicked.connect(self.app.set_work_zero)
        self.go_zero_btn.clicked.connect(self.app.go_machine_zero)
        self.reset_btn.clicked.connect(self.app.do_reset)
        self.estop_btn.clicked.connect(self.app.do_estop)
        self.move_btn.clicked.connect(self.app.move_to_target)

        self.load_points_gcode_btn.clicked.connect(self.app.load_points_gcode)
        self.load_csv_pcb_btn.clicked.connect(self.app.load_pcb_csv)
        self.capture_btn.clicked.connect(self.app.capture_point)
        self.update_btn.clicked.connect(self.app.update_selected_point)
        self.delete_btn.clicked.connect(self.app.delete_selected_point)
        self.clear_btn.clicked.connect(self.app.clear_points)
        self.preview3d_btn.clicked.connect(self.app.preview_3d)
        self.export_gcode_btn.clicked.connect(self.app.export_gcode)

    def append_log(self, line: str):
        import html
        text = f"[{_ts()}] {line}"
        low = line.lower()
        if "error" in low:
            color = "#ff6b6b"
        elif "alarm" in low:
            color = "#ffa500"
        elif low.strip() == "ok":
            color = "#69db7c"
        else:
            color = ""
        if color:
            self.log_view.append(f'<span style="color:{color}">{html.escape(text)}</span>')
        else:
            self.log_view.append(html.escape(text))
        doc = self.log_view.document()
        while doc.blockCount() > self.max_log_lines:
            cursor = self.log_view.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.select(cursor.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def _save_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Log", "cnc_log.txt", "Text Files (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.log_view.toPlainText())
