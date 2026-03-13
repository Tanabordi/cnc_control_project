from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QToolButton, QMenu, QStackedWidget,
    QMessageBox, QFileDialog
)

from models import Point
from settings import load_settings, save_settings
from utils import clamp, _set_enabled, _read_text, apply_theme
from worker import GrblWorker
from preview import Preview3DWindow
from pages import ControlPage, RunPage, SettingsPage


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CNC Control (GRBL-ESP32 / MKS DLC32)")
        self.setFocusPolicy(Qt.StrongFocus)

        self.settings = load_settings()
        self.worker = GrblWorker()
        self.worker.status.connect(self.on_status)
        self.worker.log.connect(self.on_log)
        self.worker.connected.connect(self.on_connected)
        self.worker.stream_state.connect(self.on_stream_state)
        self.worker.line_sent.connect(self._on_line_sent)
        self.worker.line_ack.connect(self._on_line_ack)
        self.worker.line_error_at.connect(self._on_line_error_at)

        self.worker.alarm.connect(self.on_alarm)
        self.worker.grbl_reset.connect(self.on_grbl_reset)

        self.points: list[Point] = []
        self._connected = False
        self._streaming_now = False
        self._alarm_active = False
        self._last_auto_x_time = 0.0  # cooldown: prevent $X spam
        self._home_state = ""  # "after_H" | "after_HZ"

        # --- Top bar ---
        top = QHBoxLayout()
        self.menu_btn = QToolButton()
        self.menu_btn.setText("☰")
        self.menu_btn.setPopupMode(QToolButton.InstantPopup)

        menu = QMenu(self)
        self.act_control = menu.addAction("Control")
        self.act_run = menu.addAction("G-code program")
        self.act_settings = menu.addAction("Settings")
        menu.addSeparator()
        self.act_exit = menu.addAction("Exit")
        self.menu_btn.setMenu(menu)

        top.addWidget(self.menu_btn)
        top.addWidget(QLabel(""), 1)
        self.page_title = QLabel("Control")
        top.addWidget(self.page_title)
        top.addStretch(1)

        # --- Pages ---
        self.stack = QStackedWidget()
        self.control_page = ControlPage(self)
        self.run_page = RunPage(self)
        self.settings_page = SettingsPage(self)
        self.stack.addWidget(self.control_page)
        self.stack.addWidget(self.run_page)
        self.stack.addWidget(self.settings_page)

        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self.stack, 1)
        self.resize(1400, 900)

        self.act_control.triggered.connect(lambda: self.show_page("control"))
        self.act_run.triggered.connect(lambda: self.show_page("run"))
        self.act_settings.triggered.connect(lambda: self.show_page("settings"))
        self.act_exit.triggered.connect(self.close)

        self.refresh_ports()
        self.on_step_mode(self.control_page.step_mode.currentText())
        self.settings_page.load_into_ui(self.settings)
        self.apply_settings_to_runtime()

        if self.settings.last_port:
            idx = self.control_page.port_box.findText(self.settings.last_port)
            if idx >= 0:
                self.control_page.port_box.setCurrentIndex(idx)

    def show_page(self, name: str):
        mp = {"control": (0, "Control"), "run": (1, "G-code program"), "settings": (2, "Settings")}
        i, title = mp.get(name, (0, "Control"))
        self.stack.setCurrentIndex(i)
        self.page_title.setText(title)

    def apply_settings_to_runtime(self):
        self.worker.set_poll_interval_ms(self.settings.status_poll_ms)
        self.control_page.auto_unlock_cb.setChecked(bool(self.settings.auto_unlock_after_reset))
        apply_theme(self.settings.theme)

    # -------- Keyboard jog --------
    def keyPressEvent(self, event):
        if not self._connected or self._streaming_now:
            return super().keyPressEvent(event)

        # Determine active page and its keyboard_cb/step/feed
        cur = self.stack.currentIndex()
        if cur == 0:
            page, jog_fn = self.control_page, self.jog
            if not page.keyboard_cb.isChecked():
                return super().keyPressEvent(event)
            step = self.get_step()
        else:
            return super().keyPressEvent(event)

        if event.isAutoRepeat():
            event.accept()
            return

        keymap = {
            Qt.Key_Left:     ("X", -step),
            Qt.Key_Right:    ("X", +step),
            Qt.Key_Up:       ("Y", +step),
            Qt.Key_Down:     ("Y", -step),
            Qt.Key_PageUp:   ("Z", +step),
            Qt.Key_PageDown: ("Z", -step),
        }
        if event.key() in keymap:
            axis, delta = keymap[event.key()]
            jog_fn(axis, delta)
            event.accept()
            return
        return super().keyPressEvent(event)

    # -------- Ports / Connect --------
    def refresh_ports(self):
        import serial.tools.list_ports
        self.control_page.port_box.clear()
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.control_page.port_box.addItems(ports)
        self.on_log(f"Found ports: {', '.join(ports) if ports else '(none)'}")

    def do_connect(self):
        port = self.control_page.port_box.currentText().strip()
        if not port:
            QMessageBox.warning(self, "No Port", "Please select a COM port.")
            return
        self.settings.last_port = port
        save_settings(self.settings)
        ok = self.worker.connect_serial(port, int(self.settings.baud))
        if ok and not self.worker.isRunning():
            self.worker.start()

    def do_disconnect(self):
        self.worker.disconnect_serial()

    def on_connected(self, ok: bool):
        self._connected = ok
        cp = self.control_page

        cp.connect_btn.setEnabled(not ok)
        cp.disconnect_btn.setEnabled(ok)

        _set_enabled([cp.home_btn, cp.unlock_btn, cp.zero_btn, cp.go_zero_btn, cp.reset_btn, cp.estop_btn], ok)
        _set_enabled(cp.jog_buttons, ok)
        _set_enabled([cp.load_points_gcode_btn, cp.load_csv_pcb_btn, cp.capture_btn,
                      cp.update_btn, cp.delete_btn, cp.clear_btn,
                      cp.preview3d_btn, cp.move_btn, cp.export_gcode_btn], ok)

        cp.update_btn.setEnabled(False)
        cp.console_send_btn.setEnabled(ok)
        cp.state_lbl.setText("Port opened" if ok else "Disconnected")
        self.run_page.set_connected(ok)
        self.run_page.reset_btn.setEnabled(ok)
        self.settings_page.set_connected(ok)

        if ok:
            self._alarm_active = False
        if ok and self.settings.auto_unlock_after_connect:
            import time as _time
            self._last_auto_x_time = _time.time()
            self.worker.send_line("$X")
            self.on_log("Auto unlock after connect ($X).")

    def on_stream_state(self, st: str):
        self._streaming_now = (st in ("running", "paused"))
        locked = self._streaming_now
        cp = self.control_page
        _set_enabled(cp.jog_buttons, self._connected and (not locked))
        _set_enabled([cp.move_btn, cp.load_points_gcode_btn, cp.load_csv_pcb_btn, cp.capture_btn,
                      cp.update_btn, cp.delete_btn, cp.clear_btn,
                      cp.export_gcode_btn, cp.preview3d_btn], self._connected and (not locked))
        if locked:
            cp.update_btn.setEnabled(False)
        self.run_page.set_stream_state(st)

    # -------- UI updates --------
    def on_status(self, payload: dict):
        state = payload.get("state") or "-"

        wx, wy, wz = payload["wpos"]
        mpos = payload.get("mpos")
        mx, my, mz = mpos if mpos else (wx, wy, wz)

        for page in (self.control_page, self.run_page):
            page.wpos_x.setText(f"{wx:.3f}")
            page.wpos_y.setText(f"{wy:.3f}")
            page.wpos_z.setText(f"{wz:.3f}")
            page.mpos_x.setText(f"{mx:.3f}")
            page.mpos_y.setText(f"{my:.3f}")
            page.mpos_z.setText(f"{mz:.3f}")
            page.state_lbl.setText(state)

        self.run_page.update_tool_position(wx, wy)

        if state.lower().startswith("alarm") and not self._alarm_active:
            self.on_alarm(state)
        elif self._alarm_active and not state.lower().startswith("alarm"):
            self._alarm_active = False
            self._last_alarm_was_hard_limit = False
            cp = self.control_page
            _set_enabled(cp.jog_buttons, True)
            cp.home_btn.setEnabled(True)

    # -------- Stream line tracking --------
    def _on_line_sent(self, idx: int, cmd: str):
        self.run_page.update_cmd_row_sent(idx)

    def _on_line_ack(self, idx: int):
        self.run_page.update_cmd_row_ack(idx)

    def _on_line_error_at(self, idx: int, msg: str):
        self.run_page.update_cmd_row_error(idx, msg)

    def on_log(self, msg: str):
        self.control_page.append_log(msg)
        self.run_page.append_log(msg)
        self.settings_page.append_log(msg)
        if self._home_state and msg.strip().lower() == "ok":
            if self._home_state == "after_H":
                self._home_state = "after_HZ"
                self.worker.send_line("$HZ")
                self.on_log("Homing Z...")
            elif self._home_state == "after_HZ":
                self._home_state = ""
                self.on_log("Homing done.")

    # -------- Console --------
    def send_console_command(self):
        cp = self.control_page
        cmd = cp.console_input.text().strip()
        if not cmd:
            return
        self.worker.send_line(cmd)
        cp.console_input.clear()

    def send_run_console_command(self):
        rp = self.run_page
        cmd = rp.console_input.text().strip()
        if not cmd:
            return
        self.worker.send_line(cmd)
        rp.console_input.clear()

    # -------- Soft limits --------
    def soft_limits(self):
        s = self.settings
        return (s.xmin, s.xmax, s.ymin, s.ymax, s.zmin, s.zmax)

    def within_limits(self, x, y, z):
        xmin, xmax, ymin, ymax, zmin, zmax = self.soft_limits()
        return (xmin <= x <= xmax) and (ymin <= y <= ymax) and (zmin <= z <= zmax)

    # -------- Step/Jog/Move --------
    def get_step(self):
        cp = self.control_page
        mode = cp.step_mode.currentText()
        return float(mode) if mode in ("0.1", "1", "10") else float(cp.step_mm.value())

    def on_step_mode(self, txt: str):
        self.control_page.step_mm.setEnabled(txt == "Custom")

    def jog(self, axis: str, delta: float):
        wpos = self.worker.last_wpos()
        if not wpos:
            self.on_log("No position received yet.")
            return
        x, y, z = wpos
        nx, ny, nz = x, y, z
        if axis == "X":
            nx = x + delta
        elif axis == "Y":
            ny = y + delta
        elif axis == "Z":
            nz = z + delta
        if not self.within_limits(nx, ny, nz):
            self.on_log(f"Soft limit blocked. Target: X{nx:.3f} Y{ny:.3f} Z{nz:.3f}")
            return
        f = self.control_page.feed.value()
        self.worker.send_line(f"$J=G91 {axis}{delta:.3f} F{f}")

    def move_to_target(self):
        cp = self.control_page
        x, y, z = cp.tx.value(), cp.ty.value(), cp.tz.value()
        if not self.within_limits(x, y, z):
            self.on_log(f"Soft limit blocked. Target: X{x:.3f} Y{y:.3f} Z{z:.3f}")
            return
        f = cp.feed.value()
        self.worker.send_line("G90")
        self.worker.send_line(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{f}")

    # -------- Waypoints actions --------
    def on_waypoint_clicked(self, row: int, col: int):
        if not self._connected:
            return
        if self._streaming_now:
            self.on_log("กำลัง Run/Stream อยู่: ไม่อนุญาตให้วิ่งไป Waypoint จากตาราง")
            return
        if row < 0 or row >= len(self.points):
            return

        cp = self.control_page
        p = self.points[row]
        cp.wp_feed.setValue(int(p.feed_to_next))
        cp.wp_laser_time.setValue(float(p.laser_time_s))
        cp.wp_z_safe.setValue(float(p.z_safe))
        cp.tx.setValue(float(p.x))
        cp.ty.setValue(float(p.y))
        cp.tz.setValue(float(p.z))
        cp.update_btn.setEnabled(True)

        if not self.within_limits(p.x, p.y, p.z):
            self.on_log(f"Soft limit blocked. Target: X{p.x:.3f} Y{p.y:.3f} Z{p.z:.3f}")
            return
        f = int(p.feed_to_next) if p.feed_to_next else int(cp.feed.value())
        self.worker.send_line("G90")
        self.worker.send_line(f"G1 X{p.x:.3f} Y{p.y:.3f} Z{p.z:.3f} F{f}")
        self.on_log(f"Go to waypoint #{row+1}: X{p.x:.3f} Y{p.y:.3f} Z{p.z:.3f} F{f}")

    def update_selected_point(self):
        if not self._connected:
            return
        if self._streaming_now:
            self.on_log("กำลัง Run/Stream อยู่: ไม่อนุญาตให้ Update ระหว่าง Stream")
            return
        cp = self.control_page
        row = cp.wp_table.currentRow()
        if row is None or row < 0 or row >= len(self.points):
            self.on_log("เลือกแถวที่ต้องการ Update ก่อน")
            return
        wpos = self.worker.last_wpos()
        if not wpos:
            self.on_log("No position received yet.")
            return
        x, y, z = wpos
        if not self.within_limits(x, y, z):
            self.on_log(f"Soft limit blocked. Current: X{x:.3f} Y{y:.3f} Z{z:.3f}")
            return
        f = int(cp.wp_feed.value())
        t = float(cp.wp_laser_time.value())
        zs = float(cp.wp_z_safe.value())
        p = self.points[row]
        p.x, p.y, p.z = float(x), float(y), float(z)
        p.feed_to_next = int(f)
        p.laser_time_s = float(t)
        p.z_safe = zs
        self._refresh_table_from_points()
        cp.wp_table.selectRow(row)
        self.on_log(f"Updated waypoint #{row+1} -> X{x:.3f} Y{y:.3f} Z{z:.3f} Zsafe{zs:.3f} F{f} T{t:.2f}")

    def _refresh_table_from_points(self):
        from PySide6.QtWidgets import QTableWidgetItem
        cp = self.control_page
        cp.wp_table.setRowCount(0)
        for i, p in enumerate(self.points, start=1):
            r = cp.wp_table.rowCount()
            cp.wp_table.insertRow(r)
            cp.wp_table.setItem(r, 0, QTableWidgetItem(str(i)))
            cp.wp_table.setItem(r, 1, QTableWidgetItem(f"X{p.x:.3f} Y{p.y:.3f}"))
            cp.wp_table.setItem(r, 2, QTableWidgetItem(f"{p.z:.3f}"))
            cp.wp_table.setItem(r, 3, QTableWidgetItem(f"{p.z_safe:.3f}"))
            cp.wp_table.setItem(r, 4, QTableWidgetItem(str(int(p.feed_to_next))))
            cp.wp_table.setItem(r, 5, QTableWidgetItem(f"{float(p.laser_time_s):.2f}"))

        cp.preview3d_btn.setEnabled(len(self.points) >= 2 and self._connected)
        cp.export_gcode_btn.setEnabled(len(self.points) >= 1 and self._connected)
        cp.delete_btn.setEnabled(len(self.points) >= 1 and self._connected)
        cp.update_btn.setEnabled(
            self._connected and (cp.wp_table.currentRow() >= 0) and (not self._streaming_now)
        )

    def capture_point(self):
        cp = self.control_page
        wpos = self.worker.last_wpos()
        if not wpos:
            self.on_log("No position received yet.")
            return
        x, y, z = wpos
        f = int(cp.wp_feed.value())
        t = float(cp.wp_laser_time.value())
        zs = float(cp.wp_z_safe.value())
        idx = len(self.points) + 1
        self.points.append(Point(name=f"P{idx}", x=x, y=y, z=z, feed_to_next=f, laser_time_s=t, z_safe=zs))
        self._refresh_table_from_points()

    def delete_selected_point(self):
        cp = self.control_page
        row = cp.wp_table.currentRow()
        if row is None or row < 0 or row >= len(self.points):
            return
        self.points.pop(row)
        self._refresh_table_from_points()

    def clear_points(self):
        self.points.clear()
        self._refresh_table_from_points()

    def preview_3d(self):
        if not self.points or len(self.points) < 2:
            QMessageBox.warning(self, "Preview 3D", "ต้องมีอย่างน้อย 2 points")
            return
        safe_z = clamp(self.settings.safe_z, self.settings.zmin, self.settings.zmax)
        Preview3DWindow(self.points, safe_z=safe_z, parent=self).exec()

    def load_points_gcode(self):
        from utils import _strip_gcode_line, _parse_words
        path, _ = QFileDialog.getOpenFileName(self, "Load Points from G-code", "", "G-code (*.gcode *.nc *.ngc *.txt)")
        if not path:
            return

        points: list[Point] = []
        last_x = last_y = last_z = 0.0
        last_f = int(self.control_page.wp_feed.value())

        for raw in _read_text(path):
            line = _strip_gcode_line(raw)
            if not line:
                continue
            w = _parse_words(line)
            if not w:
                continue
            g = w.get("G", None)
            if g in (0, 1):
                x = w.get("X", last_x)
                y = w.get("Y", last_y)
                z = w.get("Z", last_z)
                if "F" in w and w["F"] is not None:
                    last_f = int(w["F"])
                if ("X" in w) or ("Y" in w) or ("Z" in w):
                    idx = len(points) + 1
                    points.append(Point(name=f"P{idx}", x=float(x), y=float(y), z=float(z),
                                        feed_to_next=int(last_f), laser_time_s=0.0))
                last_x, last_y, last_z = x, y, z

        self.points = points
        self._refresh_table_from_points()
        self.on_log(f"Loaded points from G-code: {path} ({len(self.points)} points)")

    def load_pcb_csv(self):
        from pcb_import import parse_pcb_csv, PcbCalibDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Import PCB CSV", "", "CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return

        try:
            components, has_side = parse_pcb_csv(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"ไม่สามารถอ่านไฟล์ CSV ได้:\n{e}")
            return

        if not components:
            QMessageBox.warning(self, "Empty", "ไม่พบ component ในไฟล์ CSV")
            return

        self.on_log(f"PCB CSV: {len(components)} components จาก {path}")

        dlg = PcbCalibDialog(components, has_side, self.worker, self)
        if dlg.exec() != PcbCalibDialog.Accepted:
            return

        wp = dlg.get_waypoints(
            default_feed=int(self.control_page.wp_feed.value()),
            default_time=float(self.control_page.wp_laser_time.value()),
        )
        if not wp:
            QMessageBox.warning(self, "Error", "ไม่สามารถคำนวณ waypoints ได้ (ตรวจสอบ calibration points)")
            return

        self.points = wp
        self._refresh_table_from_points()
        self.on_log(f"Imported {len(self.points)} waypoints from PCB CSV")

    def export_gcode(self):
        if not self.points:
            QMessageBox.warning(self, "No Points", "Capture points first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export G-code", "points.gcode", "G-code (*.gcode *.nc *.ngc)")
        if not path:
            return

        lines = ["G90", "G21", "G54"]
        for p in self.points:
            f = int(p.feed_to_next)
            lines += [
                f"; {p.name}",
                f"G0 X{p.x:.3f} Y{p.y:.3f} Z{p.z_safe:.3f}",
                f"G1 Z{p.z:.3f} F{f}",
                f"G4 P{p.laser_time_s:.3f}",
                f"G0 Z{p.z_safe:.3f}",
            ]
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.on_log(f"Exported: {path}")

    # -------- GRBL actions --------
    def set_work_zero(self):
        self.worker.send_line("G10 L20 P1 X0 Y0 Z0")
        self.on_log("Set G54 work zero at current position")

    def go_machine_zero(self):
        self.worker.send_line("G90")
        self.worker.send_line("G53 G0 X0 Y0 Z0")
        self.on_log("Go to Machine Zero (G53)")

    def do_home(self):
        if not self._connected:
            return
        self._home_state = "after_H"
        self.worker.send_line("$H")
        self.on_log("Homing started...")

    def do_reset(self):
        if not self._connected:
            return
        self.worker.send_reset()
        if self.control_page.auto_unlock_cb.isChecked():
            self.worker.send_line("$X")

    def do_estop(self):
        if not self._connected:
            return
        ret = QMessageBox.question(
            self, "Confirm E-STOP",
            "ต้องการสั่ง E-STOP ใช่ไหม?\n(จะส่ง HOLD ! + CTRL+X และไม่ Auto Unlock)",
            QMessageBox.Yes | QMessageBox.No
        )
        if ret != QMessageBox.Yes:
            return
        self.worker.estop()

    def on_alarm(self, msg: str):
        self._alarm_active = True
        self._last_alarm_was_hard_limit = "1" in msg  # ALARM:1 = hard limit
        for page in (self.control_page, self.run_page):
            page.state_lbl.setText(msg)
        _set_enabled(self.control_page.jog_buttons, False)
        self.control_page.home_btn.setEnabled(False)
        if self._last_alarm_was_hard_limit:
            self.on_log("Hard limit! ขยับแกนออกจาก endstop ด้วยมือก่อน แล้วกด Unlock ($X)")
        else:
            self.on_log(f"{msg} — กด Unlock ($X) เพื่อ clear")

    def on_grbl_reset(self):
        was_hard_limit = getattr(self, '_last_alarm_was_hard_limit', False)
        was_alarm = self._alarm_active
        self._alarm_active = False
        self._last_alarm_was_hard_limit = False
        if was_alarm:
            cp = self.control_page
            _set_enabled(cp.jog_buttons, True)
            cp.home_btn.setEnabled(True)
            if not self._streaming_now:
                self.on_stream_state("idle")
        import time as _time
        now = _time.time()
        if was_hard_limit:
            return
        if self._connected and self.settings.auto_unlock_after_connect:
            if now - self._last_auto_x_time > 2.0:
                self._last_auto_x_time = now
                self.worker.send_line("$X")
                self.on_log("Auto unlock ($X) after GRBL reset.")

    def closeEvent(self, event):
        try:
            self.worker.disconnect_serial()
        except Exception:
            pass
        event.accept()
