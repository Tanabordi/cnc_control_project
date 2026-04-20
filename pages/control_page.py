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
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # --- Quick Start Guide ---
        guide_box = QGroupBox("🎓 Quick Start Guide")
        guide_layout = QVBoxLayout(guide_box)
        guide_layout.setContentsMargins(6, 6, 6, 6)
        guide_layout.setSpacing(2)
        
        guide_text = QLabel(
            "<b>1. Connect:</b> Select COM port and click Connect<br>"
            "<b>2. Home:</b> Click Home button (required first time)<br>"
            "<b>3. Jog:</b> Use arrow buttons or keyboard to move<br>"
            "<b>4. Capture:</b> Click Capture Waypoint to record positions<br>"
            "<b>5. Export:</b> Click Export G-code when done<br>"
            "<i>💡 Hover over any button to see what it does</i>"
        )
        guide_text.setWordWrap(True)
        guide_text.setStyleSheet("font-size: 10px; padding: 4px;")
        guide_layout.addWidget(guide_text)
        root.addWidget(guide_box)

        # --- Connection bar ---
        conn_bar = QGroupBox("Connection")
        c = QHBoxLayout()
        c.setContentsMargins(6, 6, 6, 6)
        c.setSpacing(6)
        self.port_box = QComboBox()
        self.refresh_btn = _btn("🔄 Refresh Ports", enabled=True)
        self.connect_btn = _btn("🔌 Connect", enabled=True)
        self.disconnect_btn = _btn("❌ Disconnect", enabled=False)
        
        self.refresh_btn.setToolTip("Scan for available COM ports")
        self.connect_btn.setToolTip("Connect to the selected GRBL device")
        self.disconnect_btn.setToolTip("Disconnect from GRBL device")
        self.port_box.setToolTip("Select COM port for GRBL connection")
        
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
        L.setSpacing(6)

        teach = QHBoxLayout()
        teach.setSpacing(4)
        teach.addWidget(QLabel("Feed to NEXT:"))
        self.wp_feed = QSpinBox()
        self.wp_feed.setRange(1, 20000)
        self.wp_feed.setValue(1200)
        self.wp_feed.setToolTip("Speed (mm/min) to move to next waypoint (Feed rate)")
        teach.addWidget(self.wp_feed)

        teach.addWidget(QLabel("Time (s):"))
        self.wp_laser_time = QDoubleSpinBox()
        self.wp_laser_time.setRange(0.0, 9999.0)
        self.wp_laser_time.setDecimals(2)
        self.wp_laser_time.setValue(0.50)
        self.wp_laser_time.setToolTip("Laser on time at this waypoint (seconds)")
        teach.addWidget(self.wp_laser_time)

        teach.addWidget(QLabel("Z safe:"))
        self.wp_z_safe = QDoubleSpinBox()
        self.wp_z_safe.setRange(-99999.0, 0.0)
        self.wp_z_safe.setDecimals(3)
        self.wp_z_safe.setValue(-2.0)
        self.wp_z_safe.setToolTip("Safe Z height to retract between waypoints")
        teach.addWidget(self.wp_z_safe)

        teach.addWidget(QLabel("Power (S):"))
        self.wp_power = QSpinBox()
        self.wp_power.setRange(0, 255)
        self.wp_power.setValue(255)
        self.wp_power.setToolTip("Laser power (0-255) at this waypoint")
        teach.addWidget(self.wp_power)
        teach.addStretch(1)
        L.addLayout(teach)

        self.load_points_gcode_btn = _btn("📂 Load Points (.gcode)")
        self.load_csv_pcb_btn = _btn("📊 Import PCB CSV")
        self.save_waypoints_btn = _btn("💾 Save Waypoints (.json)")
        self.load_waypoints_btn = _btn("📥 Load Waypoints (.json)", enabled=True)
        self.capture_btn = _btn("📍 Capture Waypoint")
        self.update_btn = _btn("✏️ Update Selected")
        self.delete_btn = _btn("🗑️ Delete Selected")
        self.clear_btn = _btn("🚨 Clear Points")
        self.preview3d_btn = _btn("👁️ Preview 3D")
        self.export_gcode_btn = _btn("📤 Export G-code (.gcode)")
        self.export_panel_btn = _btn("📋 Export Panel (.gcode)")
        
        self.load_points_gcode_btn.setToolTip("Load movement path from G-code file")
        self.load_csv_pcb_btn.setToolTip("Import PCB component positions from CSV file")
        self.save_waypoints_btn.setToolTip("Save current waypoints to JSON file")
        self.load_waypoints_btn.setToolTip("Load waypoints from previously saved JSON file")
        self.capture_btn.setToolTip("Capture current machine position as new waypoint")
        self.update_btn.setToolTip("Update selected waypoint with current position")
        self.delete_btn.setToolTip("Delete the selected waypoint from the list")
        self.clear_btn.setToolTip("Remove all waypoints (cannot undo!)")
        self.preview3d_btn.setToolTip("Visualize the tool path in 3D")
        self.export_gcode_btn.setToolTip("Generate and export G-code for single PCB")
        self.export_panel_btn.setToolTip("Generate and export G-code for panel (multiple PCBs)")

        btn_row1 = QHBoxLayout()
        btn_row1.setSpacing(4)
        for b in [self.load_points_gcode_btn, self.load_csv_pcb_btn,
                  self.save_waypoints_btn, self.load_waypoints_btn,
                  self.export_gcode_btn, self.export_panel_btn]:
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn_row1.addWidget(b)

        btn_row2 = QHBoxLayout()
        btn_row2.setSpacing(4)
        for b in [self.capture_btn, self.update_btn, self.delete_btn,
                  self.clear_btn, self.preview3d_btn]:
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn_row2.addWidget(b)

        L.addLayout(btn_row1)
        L.addLayout(btn_row2)

        # Waypoint table with helpful label
        wp_box = QGroupBox("Waypoints (Saved Positions)")
        wp_layout = QVBoxLayout(wp_box)
        wp_layout.setContentsMargins(4, 4, 4, 4)
        wp_layout.setSpacing(3)
        
        wp_info = QLabel("Click on a row to select it, then use Update to modify or Delete to remove")
        wp_info.setStyleSheet("color: #666; font-size: 9px;")
        wp_layout.addWidget(wp_info)
        
        self.wp_table = WaypointTable(self)
        self.wp_table.setColumnCount(7)
        self.wp_table.setHorizontalHeaderLabels(["Number", "Position (X,Y)", "Z work", "Z safe", "Speed(F)", "Time (s)", "Power"])
        self.wp_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.wp_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.wp_table.setSelectionMode(QTableWidget.SingleSelection)
        self.wp_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        wp_layout.addWidget(self.wp_table, 1)
        L.addWidget(wp_box, 1)

        self.wp_table.cellClicked.connect(self.app.on_waypoint_clicked)

        # --- Log (inside left panel) ---
        log_box = QGroupBox("📋 System Log")
        lv = QVBoxLayout(log_box)
        lv.setContentsMargins(6, 6, 6, 6)
        lv.setSpacing(4)
        
        log_info = QLabel("Shows connection status, movements, and error messages")
        log_info.setStyleSheet("color: #666; font-size: 9px;")
        lv.addWidget(log_info)
        
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(100)
        self.log_view.setMaximumHeight(180)
        self.log_view.setLineWrapMode(QTextEdit.NoWrap)
        lv.addWidget(self.log_view)
        clear_row = QHBoxLayout()
        clear_row.setSpacing(4)
        self.clear_log_btn = _btn("Clear Log", enabled=True)
        self.copy_log_btn = _btn("Copy Log", enabled=True)
        self.save_log_btn = _btn("Save Log", enabled=True)
        
        self.clear_log_btn.setToolTip("Clear all log messages")
        self.copy_log_btn.setToolTip("Copy all log messages to clipboard")
        self.save_log_btn.setToolTip("Save log to text file")
        
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
        console_box = QGroupBox("Console (Advanced)")
        cv = QVBoxLayout(console_box)
        cv.setContentsMargins(6, 6, 6, 6)
        cv.setSpacing(4)
        
        # Console help text
        console_help = QLabel("Send direct GRBL commands. Common: $I (info), $$ (settings), G28 (home), M5 (stop)")
        console_help.setStyleSheet("color: #666; font-size: 9px;")
        cv.addWidget(console_help)
        
        console_row = QHBoxLayout()
        console_row.setSpacing(4)
        self.console_input = QLineEdit()
        self.console_input.setPlaceholderText("Send GRBL command (e.g. $I, ?, $$, G28, M5 ...)")
        self.console_input.setToolTip("Enter GRBL commands directly. Press Enter or click Send button.")
        self.console_send_btn = _btn("Send", enabled=False)
        self.console_send_btn.setToolTip("Send the command to GRBL device")
        console_row.addWidget(self.console_input, 1)
        console_row.addWidget(self.console_send_btn)
        cv.addLayout(console_row)
        L.addWidget(console_box)

        # ===== Right panel =====
        right = QWidget()
        R = QVBoxLayout(right)
        R.setContentsMargins(0, 0, 0, 0)
        R.setSpacing(6)

        status_box = QGroupBox("📍 Current Status")
        sg = QVBoxLayout(status_box)
        sg.setContentsMargins(6, 6, 6, 6)
        sg.setSpacing(3)

        def _coord_field():
            f = QLineEdit()
            f.setReadOnly(True)
            f.setAlignment(Qt.AlignRight)
            f.setMinimumWidth(60)
            f.setMaximumWidth(100)
            f.setText("0.000")
            f.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            return f

        sg.addWidget(QLabel("📏 Work Coordinates (G54):"))
        wrow = QHBoxLayout()
        self.wpos_x = _coord_field()
        self.wpos_y = _coord_field()
        self.wpos_z = _coord_field()
        self.wpos_x.setToolTip("Current X work position")
        self.wpos_y.setToolTip("Current Y work position")
        self.wpos_z.setToolTip("Current Z work position")
        wrow.addWidget(QLabel("X:"))
        wrow.addWidget(self.wpos_x)
        wrow.addWidget(QLabel("Y:"))
        wrow.addWidget(self.wpos_y)
        wrow.addWidget(QLabel("Z:"))
        wrow.addWidget(self.wpos_z)
        sg.addLayout(wrow)

        sg.addWidget(QLabel("📍 Machine Coordinates (absolute):"))
        mrow = QHBoxLayout()
        self.mpos_x = _coord_field()
        self.mpos_y = _coord_field()
        self.mpos_z = _coord_field()
        self.mpos_x.setToolTip("Current X machine position (before work offset)")
        self.mpos_y.setToolTip("Current Y machine position (before work offset)")
        self.mpos_z.setToolTip("Current Z machine position (before work offset)")
        mrow.addWidget(QLabel("X:"))
        mrow.addWidget(self.mpos_x)
        mrow.addWidget(QLabel("Y:"))
        mrow.addWidget(self.mpos_y)
        mrow.addWidget(QLabel("Z:"))
        mrow.addWidget(self.mpos_z)
        sg.addLayout(mrow)

        sstat = QHBoxLayout()
        sstat.addWidget(QLabel("Machine Status:"))
        self.state_lbl = QLabel("-")
        self.state_lbl.setToolTip("Current machine state (Idle, Run, Hold, Alarm, etc)")
        sstat.addWidget(self.state_lbl, 1)
        sg.addLayout(sstat)

        pnrow = QHBoxLayout()
        pnrow.addWidget(QLabel("Pin State (Pn):"))
        self.pn_lbl = QLabel("-")
        self.pn_lbl.setToolTip("Active pins/inputs on the machine")
        pnrow.addWidget(self.pn_lbl, 1)
        sg.addLayout(pnrow)

        R.addWidget(status_box)

        jog_box = QGroupBox("Jog (Manual Movement)")
        jog_root = QVBoxLayout(jog_box)
        jog_root.setContentsMargins(6, 6, 6, 6)
        jog_root.setSpacing(4)
        
        # Jog help text
        help_lbl = QLabel("Click buttons or use arrow keys to move (when keyboard control is on)")
        help_lbl.setStyleSheet("color: #666; font-size: 9px;")
        jog_root.addWidget(help_lbl)
        
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        self.btn_up = _btn("▲ Y+", min_h=48)
        self.btn_down = _btn("▼ Y-", min_h=48)
        self.btn_left = _btn("◀ X-", min_h=48)
        self.btn_right = _btn("▶ X+", min_h=48)
        self.btn_stop = _btn("⦸ CANCEL", min_h=48)
        self.btn_z_up = _btn("▲ Z+", min_h=48)
        self.btn_z_down = _btn("▼ Z-", min_h=48)
        
        self.btn_up.setToolTip("Move Y axis positive")
        self.btn_down.setToolTip("Move Y axis negative")
        self.btn_left.setToolTip("Move X axis negative")
        self.btn_right.setToolTip("Move X axis positive")
        self.btn_stop.setToolTip("Cancel current jog movement")
        self.btn_z_up.setToolTip("Move Z axis positive (up)")
        self.btn_z_down.setToolTip("Move Z axis negative (down)")

        self.jog_buttons = [self.btn_up, self.btn_down, self.btn_left,
                            self.btn_right, self.btn_stop, self.btn_z_up, self.btn_z_down]
        for b in self.jog_buttons:
            b.setMinimumSize(QSize(42, 42))
            b.setMaximumSize(QSize(80, 80))
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        grid.addWidget(self.btn_up, 0, 1)
        grid.addWidget(self.btn_left, 1, 0)
        grid.addWidget(self.btn_stop, 1, 1)
        grid.addWidget(self.btn_right, 1, 2)
        grid.addWidget(self.btn_down, 2, 1)
        grid.addWidget(self.btn_z_up, 0, 4)
        grid.addWidget(self.btn_z_down, 2, 4)
        jog_root.addLayout(grid)

        row1 = QHBoxLayout()
        row1.setSpacing(4)
        row1.addWidget(QLabel("Step Size:"))
        self.step_mode = QComboBox()
        self.step_mode.addItems(["0.1 mm", "1 mm", "10 mm", "Custom"])
        self.step_mode.setToolTip("Distance to move each step (0.1mm = fine, 10mm = coarse)")
        self.step_mm = QDoubleSpinBox()
        self.step_mm.setRange(0.01, 1000)
        self.step_mm.setValue(100.0)
        self.step_mm.setEnabled(False)
        self.step_mm.setToolTip("Custom step distance when 'Custom' is selected")
        row1.addWidget(self.step_mode, 1)
        row1.addWidget(self.step_mm, 1)
        jog_root.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(4)
        row2.addWidget(QLabel("Feed Rate (mm/min):"))
        self.feed = QSpinBox()
        self.feed.setRange(1, 20000)
        self.feed.setValue(2000)
        self.feed.setToolTip("Jog speed (higher = faster movement)")
        row2.addWidget(self.feed, 1)
        jog_root.addLayout(row2)

        self.keyboard_cb = QCheckBox("Enable Keyboard Control (arrow keys)")
        self.keyboard_cb.setChecked(True)
        self.keyboard_cb.setToolTip("Use arrow keys and Page Up/Down to jog when this is enabled")
        jog_root.addWidget(self.keyboard_cb)

        R.addWidget(jog_box)

        move_group = QGroupBox("Move to Target (Absolute Position)")
        mv = QFormLayout(move_group)
        mv.setContentsMargins(6, 6, 6, 6)
        mv.setSpacing(4)
        
        # Move help text
        move_help = QLabel("Enter target coordinates and press Move button")
        move_help.setStyleSheet("color: #666; font-size: 9px;")
        mv.addRow(move_help)
        
        self.tx = QDoubleSpinBox()
        self.tx.setRange(-99999, 99999)
        self.tx.setValue(0)
        self.tx.setToolTip("Target X coordinate (mm)")
        self.ty = QDoubleSpinBox()
        self.ty.setRange(-99999, 99999)
        self.ty.setValue(0)
        self.ty.setToolTip("Target Y coordinate (mm)")
        self.tz = QDoubleSpinBox()
        self.tz.setRange(-99999, 99999)
        self.tz.setValue(0)
        self.tz.setToolTip("Target Z coordinate (mm)")
        self.move_btn = _btn("🎯 Move to Target (G1)")
        self.move_btn.setToolTip("Move to the specified XYZ coordinates")
        
        mv.addRow("X (mm):", self.tx)
        mv.addRow("Y (mm):", self.ty)
        mv.addRow("Z (mm):", self.tz)
        mv.addRow(self.move_btn)
        R.addWidget(move_group)

        self.home_btn = _btn("🏠 Home ($H)")
        self.unlock_btn = _btn("🔓 Unlock ($X)")
        self.zero_btn = _btn("0️⃣ Set Work Zero (G54)")
        self.go_zero_btn = _btn("➡️ Go to Machine Zero")
        self.reset_btn = _btn("⟲ Reset (Ctrl+X)")
        self.estop_btn = _btn("🛑 E-STOP")
        self.auto_unlock_cb = QCheckBox("Auto Unlock after Reset")
        
        self.home_btn.setToolTip("Home all axes (homing cycle)")
        self.unlock_btn.setToolTip("Unlock axes after alarm (soft reset)")
        self.zero_btn.setToolTip("Set current position as work zero (origin)")
        self.go_zero_btn.setToolTip("Move to machine zero position (0,0,0)")
        self.reset_btn.setToolTip("Emergency reset (stops all movement)")
        self.estop_btn.setToolTip("EMERGENCY STOP - stops immediately")
        self.auto_unlock_cb.setToolTip("Automatically unlock axes when reset is pressed")
        
        # Style E-STOP button to stand out
        self.estop_btn.setStyleSheet("background-color: #ff4444; color: white; font-weight: bold;")

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
        R.addStretch(1)  # Push everything above to top

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
        self.save_waypoints_btn.clicked.connect(self.app.save_waypoints_json)
        self.load_waypoints_btn.clicked.connect(self.app.load_waypoints_json)
        self.capture_btn.clicked.connect(self.app.capture_point)
        self.update_btn.clicked.connect(self.app.update_selected_point)
        self.delete_btn.clicked.connect(self.app.delete_selected_point)
        self.clear_btn.clicked.connect(self.app.clear_points)
        self.preview3d_btn.clicked.connect(self.app.preview_3d)
        self.export_gcode_btn.clicked.connect(self.app.export_gcode)
        self.export_panel_btn.clicked.connect(self.app.export_panel_gcode)

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
