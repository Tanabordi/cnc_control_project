import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QGroupBox, QTextEdit, QFileDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QSplitter, QProgressBar
)

from ops.gcode import FigureCanvas, Figure, parse_gcode_to_segments, estimate_run_time
from core.utils import _btn, _set_enabled, _read_text, _ts


class RunPage(QWidget):
    def __init__(self, app_ref):
        super().__init__()
        self.app = app_ref
        self._gcode_path = ""
        self._autoscroll = True
        self._estimated_total_s = 0.0
        self._stream_start_time = 0.0

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
        self._tool_dot = None
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

        # Action buttons
        self.home_btn     = _btn("Home ($H)")
        self.unlock_btn   = _btn("Unlock ($X)")
        self.zero_btn     = _btn("Set Work Zero (G54)")
        self.go_zero_btn  = _btn("Go Machine Zero (G53)")
        self.reset_btn2   = _btn("Reset (Ctrl+X)")
        self.auto_unlock_cb = QCheckBox("Auto $X after Reset")
        self.estop_btn    = _btn("E-STOP")

        act1 = QHBoxLayout()
        act1.addWidget(self.home_btn, 1)
        act1.addWidget(self.unlock_btn, 1)
        act2 = QHBoxLayout()
        act2.addWidget(self.zero_btn, 1)
        act2.addWidget(self.go_zero_btn, 1)
        act3 = QHBoxLayout()
        act3.addWidget(self.reset_btn2, 2)
        act3.addWidget(self.auto_unlock_cb, 2)
        act3.addWidget(self.estop_btn, 1)
        R.addLayout(act1)
        R.addLayout(act2)
        R.addLayout(act3)

        # Log
        log_box = QGroupBox("Log")
        log_v = QVBoxLayout(log_box)
        log_v.setContentsMargins(8, 8, 8, 8)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QTextEdit.NoWrap)
        log_v.addWidget(self.log_view, 1)
        R.addWidget(log_box, 1)

        # Console input
        console_box = QGroupBox("Console")
        cns_v = QVBoxLayout(console_box)
        cns_v.setContentsMargins(8, 8, 8, 8)
        console_row = QHBoxLayout()
        self.console_input = QLineEdit()
        self.console_input.setPlaceholderText("Send GRBL command (e.g. $I, ?, $$, G28 ...)")
        self.console_send_btn = _btn("Send", enabled=False)
        console_row.addWidget(self.console_input, 1)
        console_row.addWidget(self.console_send_btn)
        cns_v.addLayout(console_row)
        R.addWidget(console_box)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        # --- Progress row ---
        prog_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(14)
        self.progress_lbl = QLabel("—")
        self.progress_lbl.setStyleSheet("font-family: monospace; font-size: 11px;")
        self.eta_lbl = QLabel("")
        self.eta_lbl.setStyleSheet("font-family: monospace; font-size: 11px; color: gray;")
        prog_row.addWidget(self.progress_bar, 1)
        prog_row.addWidget(self.progress_lbl)
        prog_row.addWidget(self.eta_lbl)
        root.addLayout(prog_row)

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
        self.home_btn.clicked.connect(self.app.do_home)
        self.unlock_btn.clicked.connect(lambda: self.app.worker.send_line("$X"))
        self.zero_btn.clicked.connect(self.app.set_work_zero)
        self.go_zero_btn.clicked.connect(self.app.go_machine_zero)
        self.reset_btn2.clicked.connect(self.app.do_reset)
        self.estop_btn.clicked.connect(self.app.do_estop)
        self.console_input.returnPressed.connect(self.app.send_run_console_command)
        self.console_send_btn.clicked.connect(self.app.send_run_console_command)

        self.set_connected(False)
        self.set_stream_state("idle")

    # ---- Tool position ----
    def update_tool_position(self, x: float, y: float):
        if self._tool_dot is None or self.canvas is None:
            return
        self._tool_dot.set_offsets([[x, y]])
        self.canvas.draw_idle()

    # ---- Log ----
    def append_log(self, line: str):
        self.log_view.append(f"[{_ts()}] {line}")

    # ---- Connection state ----
    def set_connected(self, ok: bool):
        _set_enabled([self.run_btn, self.reset_btn, self.stop_btn], ok)
        _set_enabled([self.home_btn, self.unlock_btn, self.zero_btn,
                      self.go_zero_btn, self.reset_btn2, self.estop_btn,
                      self.console_send_btn], ok)
        if not ok:
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(False)
        self.state_lbl.setText("Port opened" if ok else "Disconnected")

    # ---- Progress ----
    def set_estimated_time(self, seconds: float):
        self._estimated_total_s = seconds

    def update_progress(self, done: int, total: int):
        self.progress_bar.setMaximum(max(total, 1))
        self.progress_bar.setValue(done)
        pct = int(done * 100 / total) if total > 0 else 0
        self.progress_lbl.setText(f"{done} / {total}  ({pct}%)")

        eta_str = ""
        if done > 0 and self._stream_start_time > 0:
            elapsed = time.time() - self._stream_start_time
            remaining_s = elapsed * (total - done) / done
            if remaining_s < 60:
                eta_str = f"ETA: {int(remaining_s)}s"
            else:
                m, s = divmod(int(remaining_s), 60)
                eta_str = f"ETA: {m}m {s}s"
        elif self._estimated_total_s > 0 and total > 0:
            eta_str = f"Est: {_fmt_duration(self._estimated_total_s)}"
        self.eta_lbl.setText(eta_str)

    def reset_progress(self):
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(1)
        self.progress_lbl.setText("—")
        self.eta_lbl.setText(
            f"Est: {_fmt_duration(self._estimated_total_s)}" if self._estimated_total_s > 0 else ""
        )
        self._stream_start_time = 0.0

    # ---- Stream state ----
    def set_stream_state(self, st: str):
        if st == "running":
            if self._stream_start_time == 0.0:
                self._stream_start_time = time.time()
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
            if self.app.controller.is_connected():
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
        try:
            est_s = estimate_run_time(_read_text(path))
            self.set_estimated_time(est_s)
            self.reset_progress()
            self.app.on_log(f"Estimated run time: {_fmt_duration(est_s)}")
        except Exception:
            pass

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
        self._tool_dot = self.ax.scatter([sx], [sy], marker="o", color="#00aaff", zorder=10, s=80)
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
        self.reset_progress()

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


def _fmt_duration(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m"
