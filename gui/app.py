"""Main application window for CNC Control."""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QToolButton, QMenu, QStackedWidget,
    QMessageBox, QFileDialog,
)

from core.models import Point
from core.settings import load_settings, save_settings
from core.utils import clamp, _set_enabled, apply_theme
from core.worker import GrblWorker
from gui.preview import Preview3DWindow
from gui.pages import ControlPage, RunPage, SettingsPage
from core.controller import CNCController

# Import operation modules
from ops import signal_handlers
from ops import waypoint_ops
from ops import gcode_export
from ops import grbl_commands
from ops import movement


class MainWindow(QWidget):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CNC Control (GRBL-ESP32 / MKS DLC32)")
        self.setFocusPolicy(Qt.StrongFocus)

        self.settings = load_settings()
        self.worker = GrblWorker()
        self.controller = CNCController(self.worker, self.settings)
        self._last_alarm_was_hard_limit = False

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
        self.setMinimumSize(900, 550) # ยังคงเก็บขั้นต่ำไว้ เผื่อผู้ใช้กดปุ่มย่อหน้าต่าง (Restore Down) มันจะได้ไม่พัง
        self.showMaximized()          # <--- เพิ่มคำสั่งนี้เพื่อบังคับขยายเต็มจอตั้งแต่เริ่มรันโปรแกรม
        
        # --- Setup connections ---
        self.act_control.triggered.connect(lambda: self.show_page("control"))
        self.act_run.triggered.connect(lambda: self.show_page("run"))
        self.act_settings.triggered.connect(lambda: self.show_page("settings"))
        self.act_exit.triggered.connect(self.close)

        signal_handlers.setup_signal_handlers(self)

        # Connect page signal routing
        # Most signals are connected directly in control_page.__init__
        # We only setup the non-connected ones here:
        self.control_page.capture_btn.clicked.connect(self.capture_point)
        self.control_page.update_btn.clicked.connect(self.update_selected_point)
        self.control_page.delete_btn.clicked.connect(self.delete_selected_point)
        self.control_page.clear_btn.clicked.connect(self.clear_points)
        self.control_page.preview3d_btn.clicked.connect(self.preview_3d)
        self.control_page.move_btn.clicked.connect(self.move_to_target)
        self.control_page.load_points_gcode_btn.clicked.connect(self.load_points_gcode)
        self.control_page.load_csv_pcb_btn.clicked.connect(self.load_pcb_csv)
        self.control_page.save_waypoints_btn.clicked.connect(self.save_waypoints_json)
        self.control_page.load_waypoints_btn.clicked.connect(self.load_waypoints_json)
        self.control_page.export_gcode_btn.clicked.connect(self.export_gcode)
        self.control_page.export_panel_btn.clicked.connect(self.export_panel_gcode)
        self.control_page.import_vector_btn.clicked.connect(self.import_vector_file)
        self.control_page.import_image_btn.clicked.connect(self.import_image_file)
        self.control_page.wp_table.cellClicked.connect(self.on_waypoint_clicked)
        self.control_page.console_send_btn.clicked.connect(self.send_console_command)

        self.control_page.home_btn.clicked.connect(self.do_home)
        self.control_page.reset_btn.clicked.connect(self.do_reset)
        self.control_page.estop_btn.clicked.connect(self.do_estop)
        self.control_page.zero_btn.clicked.connect(self.set_work_zero)
        self.control_page.go_zero_btn.clicked.connect(self.go_machine_zero)

        self.run_page.console_send_btn.clicked.connect(self.send_run_console_command)
        self.run_page.reset_btn.clicked.connect(self.do_reset)

        # ---------------------------------------------------------
        # เสียบสายไฟให้ปุ่ม Connection
        self.control_page.refresh_btn.clicked.connect(self.refresh_ports)
        self.control_page.connect_btn.clicked.connect(self.do_connect)
        self.control_page.disconnect_btn.clicked.connect(self.do_disconnect)

        # เสียบสายไฟให้ปุ่ม Jog (ขยับแกน)
        self.control_page.step_mode.currentTextChanged.connect(self.on_step_mode)
        self.control_page.btn_x_plus.clicked.connect(lambda: self.jog("X", self.get_step()))
        self.control_page.btn_x_minus.clicked.connect(lambda: self.jog("X", -self.get_step()))
        self.control_page.btn_y_plus.clicked.connect(lambda: self.jog("Y", self.get_step()))
        self.control_page.btn_y_minus.clicked.connect(lambda: self.jog("Y", -self.get_step()))
        self.control_page.btn_z_plus.clicked.connect(lambda: self.jog("Z", self.get_step()))
        self.control_page.btn_z_minus.clicked.connect(lambda: self.jog("Z", -self.get_step()))
        # ---------------------------------------------------------

        self.refresh_ports()
        self.on_step_mode(self.control_page.step_mode.currentText())
        self.settings_page.load_into_ui(self.settings)
        self.apply_settings_to_runtime()

        if self.settings.last_port:
            idx = self.control_page.port_box.findText(self.settings.last_port)
            if idx >= 0:
                self.control_page.port_box.setCurrentIndex(idx)

    def show_page(self, name: str):
        """Show specified page."""
        mp = {"control": (0, "Control"), "run": (1, "G-code program"), "settings": (2, "Settings")}
        i, title = mp.get(name, (0, "Control"))
        self.stack.setCurrentIndex(i)
        self.page_title.setText(title)

    def apply_settings_to_runtime(self):
        """Apply settings to runtime."""
        self.worker.set_poll_interval_ms(self.settings.status_poll_ms)
        self.control_page.auto_unlock_cb.setChecked(bool(self.settings.auto_unlock_after_reset))
        apply_theme(self.settings.theme)

    def keyPressEvent(self, event):
        """Handle keyboard events for jogging."""
        if not self.controller.is_connected() or self.controller.is_streaming():
            return super().keyPressEvent(event)

        cur = self.stack.currentIndex()
        if cur == 0:
            page = self.control_page
            if not page.keyboard_cb.isChecked():
                return super().keyPressEvent(event)
            step = movement.get_step(self)
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
            self.jog(axis, delta)
            event.accept()
            return
        return super().keyPressEvent(event)

    # -------- Connection --------
    def refresh_ports(self):
        """Refresh list of available serial ports."""
        import serial.tools.list_ports
        self.control_page.port_box.clear()
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.control_page.port_box.addItems(ports)
        self.on_log(f"Found ports: {', '.join(ports) if ports else '(none)'}")

    def do_connect(self):
        """Connect to serial port."""
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
        """Disconnect from serial port."""
        self.worker.disconnect_serial()

    # -------- Signal handlers (delegate to signal_handlers module) --------
    def on_connected(self, ok: bool):
        signal_handlers.on_connected(self, ok)

    def on_stream_state(self, st: str):
        signal_handlers.on_stream_state(self, st)

    def on_status(self, payload: dict):
        signal_handlers.on_status(self, payload)

    def on_log(self, msg: str):
        signal_handlers.on_log(self, msg)

    def clear_all_logs(self):
        self.control_page.log_view.clear()
        self.run_page.log_view.clear()
        if hasattr(self.settings_page, 'log_view'):
            self.settings_page.log_view.clear()

    def _on_line_sent(self, idx: int, cmd: str):
        signal_handlers._on_line_sent(self, idx, cmd)

    def _on_line_ack(self, idx: int):
        signal_handlers._on_line_ack(self, idx)

    def _on_line_error_at(self, idx: int, msg: str):
        signal_handlers._on_line_error_at(self, idx, msg)

    def _on_stream_progress(self, done: int, total: int):
        signal_handlers._on_stream_progress(self, done, total)

    def on_alarm(self, msg: str):
        signal_handlers.on_alarm(self, msg)

    def on_grbl_reset(self):
        signal_handlers.on_grbl_reset(self)

    # -------- Waypoint operations (delegate to waypoint_ops module) --------
    def on_waypoint_clicked(self, row: int, col: int):
        waypoint_ops.on_waypoint_clicked(self, row, col)

    def update_selected_point(self):
        waypoint_ops.update_selected_point(self)

    def _refresh_table_from_points(self):
        waypoint_ops._refresh_table_from_points(self)

    def capture_point(self):
        waypoint_ops.capture_point(self)

    def delete_selected_point(self):
        waypoint_ops.delete_selected_point(self)

    def clear_points(self):
        waypoint_ops.clear_points(self)

    def preview_3d(self):
        waypoint_ops.preview_3d(self)

    def load_points_gcode(self):
        waypoint_ops.load_points_gcode(self)

    def load_pcb_csv(self):
        waypoint_ops.load_pcb_csv(self)

    def save_waypoints_json(self):
        waypoint_ops.save_waypoints_json(self)

    def load_waypoints_json(self):
        waypoint_ops.load_waypoints_json(self)

    def import_vector_file(self):
        """Import SVG or DXF file for processing."""
        from ops.vector_import import VectorImportDialog

        dlg = VectorImportDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return

        new_points = dlg.get_waypoints()
        if not new_points:
            QMessageBox.information(self, "No Data", "No waypoints were generated from the file.")
            return

        self.controller.points.extend(new_points)
        self._refresh_table_from_points()
        self.on_log(f"Imported {len(new_points)} waypoints from vector file.")

    def import_image_file(self):
        """Import PNG or JPG file for edge tracing."""
        pass

    # -------- G-code export (delegate to gcode_export module) --------
    def export_gcode(self):
        gcode_export.export_gcode(self)

    def export_panel_gcode(self):
        gcode_export.export_panel_gcode(self)

    # -------- GRBL commands (delegate to grbl_commands module) --------
    def set_work_zero(self):
        grbl_commands.set_work_zero(self)

    def go_machine_zero(self):
        grbl_commands.go_machine_zero(self)

    def do_home(self):
        grbl_commands.do_home(self)

    def do_reset(self):
        grbl_commands.do_reset(self)

    def do_estop(self):
        grbl_commands.do_estop(self)

    def send_console_command(self):
        grbl_commands.send_console_command(self)

    def send_run_console_command(self):
        grbl_commands.send_run_console_command(self)

    # -------- Movement (delegate to movement module) --------
    def get_step(self):
        """Get current step size (called by control_page for jog buttons)."""
        return movement.get_step(self)

    def on_step_mode(self, txt: str):
        movement.on_step_mode(self, txt)

    def jog(self, axis: str, delta: float):
        movement.jog(self, axis, delta)

    def move_to_target(self):
        movement.move_to_target(self)

    # -------- UI lifecycle --------
    def closeEvent(self, event):
        """Handle window close event."""
        try:
            self.worker.disconnect_serial()
        except Exception:
            pass
        event.accept()
