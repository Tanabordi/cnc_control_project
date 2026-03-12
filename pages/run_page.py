from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QGroupBox, QTextEdit, QFileDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QSplitter, QComboBox, QSpinBox,
    QDoubleSpinBox, QGridLayout, QSizePolicy
)

from gcode import FigureCanvas, Figure, parse_gcode_to_segments
from utils import _btn, _set_enabled, _read_text, _ts


class RunPage(QWidget):
    def __init__(self, app_ref):
        super().__init__()
        self.app = app_ref
        self._gcode_path = ""
        self._autoscroll = True

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ===== Left panel =====
        left = QWidget()
        L = QVBoxLayout(left)
        L.setContentsMargins(0, 0, 0, 0)
        L.setSpacing(4)

        # Canvas
        canvas_box = QGroupBox("G-code program")
        cv = QVBoxLayout(canvas_box)
        cv.setContentsMargins(4, 4, 4, 4)
        cv.setSpacing(4)
        if FigureCanvas is None or Figure is None:
            cv.addWidget(QLabel("matplotlib not available. Install: pip install matplotlib"))
            self.fig = self.ax = self.canvas = None
        else:
            self.fig = Figure()
            self.canvas = FigureCanvas(self.fig)
            self.ax = self.fig.add_subplot(111)
            cv.addWidget(self.canvas, 1)
        self.info_lbl = QLabel("X: -    Y: -    Z: -")
        self.info_lbl.setStyleSheet("font-family: monospace; font-size: 10px; padding: 2px;")
        cv.addWidget(self.info_lbl)
        L.addWidget(canvas_box, 1)

        # Command table
        self.cmd_table = QTableWidget()
        self.cmd_table.setColumnCount(4)
        self.cmd_table.setHorizontalHeaderLabels(["#", "Command", "State", "Response"])
        self.cmd_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cmd_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cmd_table.setAlternatingRowColors(True)
        self.cmd_table.verticalHeader().setVisible(False)
        self.cmd_table.verticalHeader().setDefaultSectionSize(20)
        hh = self.cmd_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        L.addWidget(self.cmd_table, 1)

        # ===== Right panel =====
        right = QWidget()
        R = QVBoxLayout(right)
        R.setContentsMargins(0, 0, 0, 0)
        R.setSpacing(8)

        # State box
        state_box = QGroupBox("State")
        sg = QVBoxLayout(state_box)
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

        R.addWidget(state_box)

        # Jog section
        jog_box = QGroupBox("Jog")
        jog_root = QVBoxLayout(jog_box)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        self.btn_up    = _btn("▲", min_h=40)
        self.btn_down  = _btn("▼", min_h=40)
        self.btn_left  = _btn("◀", min_h=40)
        self.btn_right = _btn("▶", min_h=40)
        self.btn_stop  = _btn("⦸", min_h=40)
        self.btn_z_up  = _btn("▲", min_h=40)
        self.btn_z_down= _btn("▼", min_h=40)

        self.jog_buttons = [self.btn_up, self.btn_down, self.btn_left,
                            self.btn_right, self.btn_stop, self.btn_z_up, self.btn_z_down]
        for b in self.jog_buttons:
            b.setMinimumSize(QSize(40, 40))
            b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        grid.addWidget(self.btn_up,    0, 1)
        grid.addWidget(self.btn_left,  1, 0)
        grid.addWidget(self.btn_stop,  1, 1)
        grid.addWidget(self.btn_right, 1, 2)
        grid.addWidget(self.btn_down,  2, 1)
        grid.addWidget(self.btn_z_up,  0, 4)
        grid.addWidget(self.btn_z_down,2, 4)
        jog_root.addLayout(grid)

        step_row = QHBoxLayout()
        step_row.addWidget(QLabel("Step:"))
        self.step_mode = QComboBox()
        self.step_mode.addItems(["0.1", "1", "10", "Custom"])
        self.step_mm = QDoubleSpinBox()
        self.step_mm.setRange(0.01, 1000)
        self.step_mm.setValue(1.0)
        self.step_mm.setEnabled(False)
        step_row.addWidget(self.step_mode, 1)
        step_row.addWidget(self.step_mm, 1)
        jog_root.addLayout(step_row)

        feed_row = QHBoxLayout()
        feed_row.addWidget(QLabel("Feed:"))
        self.feed = QSpinBox()
        self.feed.setRange(1, 20000)
        self.feed.setValue(2000)
        feed_row.addWidget(self.feed, 1)
        jog_root.addLayout(feed_row)

        self.keyboard_cb = QCheckBox("Keyboard control")
        self.keyboard_cb.setChecked(False)
        jog_root.addWidget(self.keyboard_cb)
        R.addWidget(jog_box)

        # Move to Target
        move_group = QGroupBox("Move to Target (Absolute, mm)")
        from PySide6.QtWidgets import QFormLayout
        mv = QFormLayout(move_group)
        self.tx = QDoubleSpinBox(); self.tx.setRange(-99999, 99999); self.tx.setValue(0)
        self.ty = QDoubleSpinBox(); self.ty.setRange(-99999, 99999); self.ty.setValue(0)
        self.tz = QDoubleSpinBox(); self.tz.setRange(-99999, 99999); self.tz.setValue(0)
        self.move_btn = _btn("Move (G1)")
        mv.addRow("X", self.tx); mv.addRow("Y", self.ty)
        mv.addRow("Z", self.tz); mv.addRow(self.move_btn)
        R.addWidget(move_group)

        # Console (log output)
        console_box = QGroupBox("Log")
        cns = QVBoxLayout(console_box)
        cns.setContentsMargins(8, 8, 8, 8)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QTextEdit.NoWrap)
        cns.addWidget(self.log_view, 1)
        R.addWidget(console_box, 1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        # --- Bottom toolbar ---
        bot = QHBoxLayout()
        self.check_mode_cb = QCheckBox("Check mode")
        self.autoscroll_cb = QCheckBox("Autoscroll")
        self.autoscroll_cb.setChecked(True)
        bot.addWidget(self.check_mode_cb)
        bot.addWidget(self.autoscroll_cb)
        bot.addStretch(1)

        self.load_btn = _btn("Open", enabled=True)
        self.reset_btn = _btn("Reset", enabled=False)
        self.run_btn = _btn("Send")
        self.pause_btn = _btn("Pause")
        self.resume_btn = _btn("Resume")
        self.stop_btn = _btn("Abort")
        for b in [self.load_btn, self.reset_btn, self.run_btn,
                  self.pause_btn, self.resume_btn, self.stop_btn]:
            bot.addWidget(b)
        root.addLayout(bot)

        # ---- signals ----
        self.load_btn.clicked.connect(self.on_load)
        self.reset_btn.clicked.connect(self.app.worker.send_reset)
        self.run_btn.clicked.connect(self.on_run_confirm)
        self.pause_btn.clicked.connect(self.app.worker.pause_stream)
        self.resume_btn.clicked.connect(self.app.worker.resume_stream)
        self.stop_btn.clicked.connect(self.app.worker.stop_run_estop)
        self.check_mode_cb.toggled.connect(
            lambda _: self.app.worker.send_line("$C")
        )
        self.autoscroll_cb.toggled.connect(
            lambda v: setattr(self, "_autoscroll", v)
        )
        self.step_mode.currentTextChanged.connect(self._on_step_mode)
        self.btn_left.clicked.connect(lambda: self.app.run_jog("X", -self.get_step()))
        self.btn_right.clicked.connect(lambda: self.app.run_jog("X", +self.get_step()))
        self.btn_up.clicked.connect(lambda: self.app.run_jog("Y", +self.get_step()))
        self.btn_down.clicked.connect(lambda: self.app.run_jog("Y", -self.get_step()))
        self.btn_z_up.clicked.connect(lambda: self.app.run_jog("Z", +self.get_step()))
        self.btn_z_down.clicked.connect(lambda: self.app.run_jog("Z", -self.get_step()))
        self.btn_stop.clicked.connect(self.app.worker.jog_cancel)
        self.move_btn.clicked.connect(self.app.run_move_to_target)

        self.set_connected(False)
        self.set_stream_state("idle")

    # ---- Log ----
    def append_log(self, line: str):
        self.log_view.append(f"[{_ts()}] {line}")

    # ---- Step/Jog helpers ----
    def get_step(self) -> float:
        mode = self.step_mode.currentText()
        return float(mode) if mode in ("0.1", "1", "10") else float(self.step_mm.value())

    def _on_step_mode(self, txt: str):
        self.step_mm.setEnabled(txt == "Custom")

    # ---- Connection state ----
    def set_connected(self, ok: bool):
        _set_enabled([self.run_btn, self.reset_btn, self.stop_btn], ok)
        _set_enabled(self.jog_buttons + [self.move_btn], ok)
        if not ok:
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(False)
        self.state_lbl.setText("Port opened" if ok else "Disconnected")

    # ---- Stream state ----
    def set_stream_state(self, st: str):
        locked = st in ("running", "paused")
        _set_enabled(self.jog_buttons + [self.move_btn], self.app._connected and not locked)
        if st == "running":
            self.pause_btn.setEnabled(True)
            self.resume_btn.setEnabled(False)
            self.run_btn.setEnabled(False)
        elif st == "paused":
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(True)
            self.run_btn.setEnabled(False)
        else:
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(False)
            if self.app._connected:
                self.run_btn.setEnabled(True)

    # ---- Path ----
    def set_path(self, path: str):
        self._gcode_path = path

    def get_path(self) -> str:
        return self._gcode_path

    # ---- File load ----
    def on_load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open G-code", "", "G-code (*.gcode *.nc *.ngc *.txt)"
        )
        if not path:
            return
        self.set_path(path)
        self.app.on_log(f"Loaded G-code: {path}")
        self.draw_preview_from_file(path)
        self.populate_cmd_table(path)

    # ---- Run ----
    def on_run_confirm(self):
        path = self.get_path()
        if not path:
            QMessageBox.warning(self, "No G-code", "Load a G-code file first.")
            return
        ret = QMessageBox.question(
            self, "Confirm Run",
            "ต้องการ Run G-code ใช่ไหม?\n(ระหว่าง Run จะล็อก Jog/Points เพื่อความปลอดภัย)",
            QMessageBox.Yes | QMessageBox.No
        )
        if ret != QMessageBox.Yes:
            return
        self.reset_cmd_table_states()
        self.app.worker.start_stream(_read_text(path))

    # ---- Canvas preview ----
    def draw_preview_from_file(self, path: str):
        if self.ax is None or self.canvas is None:
            return
        try:
            segs, start_xyz, end_xyz = parse_gcode_to_segments(_read_text(path))
        except Exception as e:
            self.app.on_log(f"Preview error: {e}")
            return

        self.ax.clear()
        for s in segs:
            self.ax.plot(
                [s.x0, s.x1], [s.y0, s.y1],
                linestyle="-" if s.kind == "G1" else "--",
                color="black" if s.kind == "G1" else "#888888",
                linewidth=0.8
            )

        sx, sy, _ = start_xyz
        ex, ey, _ = end_xyz
        self.ax.scatter([sx], [sy], marker="s", color="green", zorder=5, s=30)
        self.ax.scatter([ex], [ey], marker="s", color="red", zorder=5, s=30)
        self.ax.set_aspect("equal", adjustable="box")
        self.ax.set_xlabel("X (mm)")
        self.ax.set_ylabel("Y (mm)")
        self.ax.grid(True, alpha=0.3)

        all_x = [s.x0 for s in segs] + [s.x1 for s in segs]
        all_y = [s.y0 for s in segs] + [s.y1 for s in segs]
        all_z = [s.z0 for s in segs] + [s.z1 for s in segs]
        if all_x:
            self.info_lbl.setText(
                f"X: {min(all_x):.3f} ... {max(all_x):.3f}    "
                f"Y: {min(all_y):.3f} ... {max(all_y):.3f}    "
                f"Z: {min(all_z):.3f} ... {max(all_z):.3f}    "
                f"Vertices: {len(segs)}"
            )
        self.canvas.draw_idle()

    # ---- Command table ----
    def populate_cmd_table(self, path: str):
        self.cmd_table.setRowCount(0)
        idx = 0
        for ln in _read_text(path):
            stripped = ln.strip()
            if not stripped or stripped.startswith(";") or stripped.startswith("("):
                continue
            self.cmd_table.insertRow(idx)
            self.cmd_table.setItem(idx, 0, QTableWidgetItem(str(idx + 1)))
            self.cmd_table.setItem(idx, 1, QTableWidgetItem(stripped))
            item_state = QTableWidgetItem("In queue")
            item_state.setForeground(Qt.gray)
            self.cmd_table.setItem(idx, 2, item_state)
            self.cmd_table.setItem(idx, 3, QTableWidgetItem(""))
            idx += 1

    def reset_cmd_table_states(self):
        for r in range(self.cmd_table.rowCount()):
            item = self.cmd_table.item(r, 2)
            if item:
                item.setText("In queue")
                item.setForeground(Qt.gray)
            resp = self.cmd_table.item(r, 3)
            if resp:
                resp.setText("")

    def update_cmd_row_sent(self, idx: int):
        if idx < 0 or idx >= self.cmd_table.rowCount():
            return
        item = self.cmd_table.item(idx, 2)
        if item:
            item.setText("Running")
            item.setForeground(Qt.blue)
        if self._autoscroll:
            self.cmd_table.scrollToItem(self.cmd_table.item(idx, 0))

    def update_cmd_row_ack(self, idx: int):
        if idx < 0 or idx >= self.cmd_table.rowCount():
            return
        item = self.cmd_table.item(idx, 2)
        if item:
            item.setText("Done")
            item.setForeground(Qt.darkGreen)

    def update_cmd_row_error(self, idx: int, msg: str):
        if idx < 0 or idx >= self.cmd_table.rowCount():
            return
        item = self.cmd_table.item(idx, 2)
        if item:
            item.setText("Error")
            item.setForeground(Qt.red)
        resp = self.cmd_table.item(idx, 3)
        if resp:
            resp.setText(msg)
        self.cmd_table.scrollToItem(self.cmd_table.item(idx, 0))
