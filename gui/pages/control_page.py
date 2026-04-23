from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QComboBox, QSpinBox, QDoubleSpinBox, QSizePolicy,
    QTableWidget, QHeaderView, QTextEdit, QLineEdit,
    QApplication, QSplitter, QScrollArea, QFrame, QCheckBox, QGridLayout,
    QPushButton, QRadioButton, QStackedWidget
)
from PySide6.QtCore import Qt
from core.utils import _btn
from core.i18n import tr

# จำลองตารางเพื่อให้ไม่ติด Error
WaypointTable = QTableWidget

# ── Jog button CSS styles ──
_JOG_XY_STYLE = """
    QPushButton {
        background-color: #1a3a5c;
        color: #4da6ff;
        border: 2px solid #2a5a8c;
        border-radius: 8px;
        font-size: 18px;
        font-weight: bold;
        min-width: 55px;
        min-height: 55px;
    }
    QPushButton:hover {
        background-color: #1e4a7a;
        border-color: #4da6ff;
    }
    QPushButton:pressed {
        background-color: #0d6efd;
        color: white;
    }
    QPushButton:disabled {
        background-color: #2a2a2a;
        color: #555;
        border-color: #444;
    }
"""

_JOG_Z_STYLE = """
    QPushButton {
        background-color: #3a2a0a;
        color: #ffb347;
        border: 2px solid #8a6a1a;
        border-radius: 8px;
        font-size: 18px;
        font-weight: bold;
        min-width: 55px;
        min-height: 55px;
    }
    QPushButton:hover {
        background-color: #5a4a1a;
        border-color: #ffb347;
    }
    QPushButton:pressed {
        background-color: #fd7e14;
        color: white;
    }
    QPushButton:disabled {
        background-color: #2a2a2a;
        color: #555;
        border-color: #444;
    }
"""

_JOG_CENTER_STYLE = """
    QLabel {
        background-color: #1a1a2e;
        color: #888;
        border: 2px solid #333;
        border-radius: 8px;
        font-size: 12px;
        font-weight: bold;
        min-width: 55px;
        min-height: 55px;
        qproperty-alignment: AlignCenter;
    }
"""

_HOME_BTN_STYLE = """
    QPushButton {
        font-size: 11px;
        padding: 4px 6px;
    }
"""


class ControlPage(QWidget):
    def __init__(self, app_ref):
        super().__init__()
        self.app = app_ref

        # Layout หลักสุดของหน้าจอ
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ==========================================
        # TOP BAR: แถบสถานะและการเชื่อมต่อ (ห้ามโดนบังเด็ดขาด)
        # ==========================================
        top_bar = QHBoxLayout()
        
        # 1. Connection (ซ้ายบน)
        self.conn_box = QGroupBox(tr("grp_connection"))
        c = QVBoxLayout(self.conn_box)
        c.setContentsMargins(6, 6, 6, 6)

        # Radio Row (Serial / TCP)
        radio_row = QHBoxLayout()
        self.radio_serial = QRadioButton("Serial")
        self.radio_tcp = QRadioButton("TCP/IP")
        self.radio_serial.setChecked(True)
        radio_row.addWidget(self.radio_serial)
        radio_row.addWidget(self.radio_tcp)
        radio_row.addStretch(1)
        c.addLayout(radio_row)

        # Inputs Row
        self.conn_inputs = QStackedWidget()
        
        # --- Serial Widget ---
        self.serial_widget = QWidget()
        s_layout = QHBoxLayout(self.serial_widget)
        s_layout.setContentsMargins(0, 0, 0, 0)
        self.port_lbl = QLabel(tr("lbl_port"))
        self.port_box = QComboBox()
        self.refresh_btn = _btn(tr("btn_refresh"), enabled=True)
        s_layout.addWidget(self.port_lbl)
        s_layout.addWidget(self.port_box, 1)
        s_layout.addWidget(self.refresh_btn)
        self.conn_inputs.addWidget(self.serial_widget)

        # --- TCP Widget ---
        self.tcp_widget = QWidget()
        t_layout = QHBoxLayout(self.tcp_widget)
        t_layout.setContentsMargins(0, 0, 0, 0)
        self.ip_lbl = QLabel("IP:")
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("192.168.1.24")
        self.port_tcp_lbl = QLabel("Port:")
        
        self.port_tcp_input = QSpinBox()
        self.port_tcp_input.setRange(1, 65535)
        self.port_tcp_input.setValue(8080)
        self.port_tcp_input.setFixedWidth(65)
        self.port_tcp_input.setToolTip("พอร์ตมาตรฐานสำหรับ MKS คือ 8080, สำหรับ Telnet คือ 23")
        
        self.test_tcp_btn = _btn("Test", enabled=True)
        self.test_tcp_btn.setToolTip("ทดสอบการเชื่อมต่อ (Ping Port)")
        
        t_layout.addWidget(self.ip_lbl)
        t_layout.addWidget(self.ip_input, 1)
        t_layout.addWidget(self.port_tcp_lbl)
        t_layout.addWidget(self.port_tcp_input)
        t_layout.addWidget(self.test_tcp_btn)
        self.conn_inputs.addWidget(self.tcp_widget)

        c.addWidget(self.conn_inputs)

        # Buttons Row
        btn_row = QHBoxLayout()
        self.connect_btn = _btn(tr("btn_connect"), enabled=True)
        self.connect_btn.setObjectName("connect_btn")
        self.disconnect_btn = _btn(tr("btn_disconnect"), enabled=False)
        btn_row.addStretch(1)
        btn_row.addWidget(self.connect_btn)
        btn_row.addWidget(self.disconnect_btn)
        c.addLayout(btn_row)

        # Connect signals for radio toggling
        self.radio_serial.toggled.connect(self._toggle_conn_type)
        self.radio_tcp.toggled.connect(self._toggle_conn_type)

        top_bar.addWidget(self.conn_box, 1)

        # 2. Machine Status (ขวาบน - ข้อมูลที่สำคัญที่สุดสำหรับ PCB)
        self.status_box = QGroupBox(tr("grp_status"))
        sg = QHBoxLayout(self.status_box)
        sg.setContentsMargins(10, 6, 10, 6)
        
        self.state_lbl = QLabel(tr("lbl_disconnected"))
        self.state_lbl.setStyleSheet("font-weight: bold; color: #DC3545; font-size: 16px;")
        sg.addWidget(self.state_lbl)
        
        # WPos (พิกัดชิ้นงาน)
        sg.addWidget(QLabel(" | <b style='color:#0D6EFD;'>WPos:</b> X"))
        self.wpos_x = QLabel("0.000"); self.wpos_y = QLabel("0.000"); self.wpos_z = QLabel("0.000")
        for lbl in [self.wpos_x, QLabel("Y"), self.wpos_y, QLabel("Z"), self.wpos_z]: 
            lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
            sg.addWidget(lbl)
            
        # MPos (พิกัดเครื่อง)
        sg.addWidget(QLabel(" | <b>MPos:</b> X"))
        self.mpos_x = QLabel("0.000"); self.mpos_y = QLabel("0.000"); self.mpos_z = QLabel("0.000")
        for lbl in [self.mpos_x, QLabel("Y"), self.mpos_y, QLabel("Z"), self.mpos_z]: sg.addWidget(lbl)
        
        self.pn_lbl = QLabel("-")
        sg.addWidget(QLabel(" | <b>Pins:</b>")); sg.addWidget(self.pn_lbl)
        top_bar.addWidget(self.status_box, 2)
        
        root.addLayout(top_bar)

        # ==========================================
        # MIDDLE AREA: แยกระหว่างแผงควบคุม (ซ้าย) กับ ตาราง/Log (ขวา)
        # ==========================================
        splitter = QSplitter(Qt.Horizontal)

        # ----- ฝั่งซ้าย: แผงควบคุมทั้งหมด (มี Scroll Bar) -----
        left = QWidget()
        left.setMinimumWidth(320)
        L = QVBoxLayout(left)
        L.setContentsMargins(0, 0, 4, 0)
        
        # A. Quick Commands (โซนอันตราย/ตั้งค่าเครื่อง) — with 4 home buttons
        self.cmd_box = QGroupBox(tr("grp_commands"))
        cmd_grid = QGridLayout(self.cmd_box)
        cmd_grid.setSpacing(4)

        self.home_all_btn = _btn(tr("btn_home_all"))
        self.home_x_btn = _btn(tr("btn_home_x")); self.home_x_btn.setStyleSheet(_HOME_BTN_STYLE)
        self.home_y_btn = _btn(tr("btn_home_y")); self.home_y_btn.setStyleSheet(_HOME_BTN_STYLE)
        self.home_z_btn = _btn(tr("btn_home_z")); self.home_z_btn.setStyleSheet(_HOME_BTN_STYLE)
        self.unlock_btn = _btn(tr("btn_unlock"))
        self.zero_btn = _btn(tr("btn_set_zero"))
        self.go_zero_btn = _btn(tr("btn_go_zero"))
        self.go_work_zero_btn = _btn(tr("btn_go_work_zero"))
        self.reset_btn = _btn(tr("btn_reset"))
        self.estop_btn = _btn(tr("btn_estop"))
        self.estop_btn.setObjectName("estop_btn")

        # Row 0: Home All | Home X | Home Y | Home Z | Unlock
        cmd_grid.addWidget(self.home_all_btn, 0, 0)
        cmd_grid.addWidget(self.home_x_btn, 0, 1)
        cmd_grid.addWidget(self.home_y_btn, 0, 2)
        cmd_grid.addWidget(self.home_z_btn, 0, 3)
        cmd_grid.addWidget(self.unlock_btn, 0, 4)
        # Row 1: Set Zero | Go Machine Zero | Go Work Zero | Reset | E-STOP
        cmd_grid.addWidget(self.zero_btn, 1, 0)
        cmd_grid.addWidget(self.go_zero_btn, 1, 1)
        cmd_grid.addWidget(self.go_work_zero_btn, 1, 2)
        cmd_grid.addWidget(self.reset_btn, 1, 3)
        cmd_grid.addWidget(self.estop_btn, 1, 4)

        L.addWidget(self.cmd_box)

        # B. Jogging Control — Professional CNC Pendant Design
        self.jog_box = QGroupBox(tr("grp_jog"))
        jog_vbox = QVBoxLayout(self.jog_box)
        jl = QHBoxLayout()
        jog_vbox.addLayout(jl)
        jl.setSpacing(12)

        # -- D-Pad for X/Y --
        dpad = QGridLayout()
        dpad.setSpacing(3)

        self.btn_y_plus = QPushButton("▲\nY+"); self.btn_y_plus.setStyleSheet(_JOG_XY_STYLE)
        self.btn_y_minus = QPushButton("▼\nY-"); self.btn_y_minus.setStyleSheet(_JOG_XY_STYLE)
        self.btn_x_plus = QPushButton("▶\nX+"); self.btn_x_plus.setStyleSheet(_JOG_XY_STYLE)
        self.btn_x_minus = QPushButton("◀\nX-"); self.btn_x_minus.setStyleSheet(_JOG_XY_STYLE)

        center_lbl = QLabel("X / Y")
        center_lbl.setStyleSheet(_JOG_CENTER_STYLE)
        center_lbl.setAlignment(Qt.AlignCenter)
        center_lbl.setFixedSize(59, 59)

        #        [  Y+  ]
        # [ X- ] [  ⌂  ] [ X+ ]
        #        [  Y-  ]
        dpad.addWidget(self.btn_y_plus, 0, 1, Qt.AlignCenter)
        dpad.addWidget(self.btn_x_minus, 1, 0, Qt.AlignCenter)
        dpad.addWidget(center_lbl, 1, 1, Qt.AlignCenter)
        dpad.addWidget(self.btn_x_plus, 1, 2, Qt.AlignCenter)
        dpad.addWidget(self.btn_y_minus, 2, 1, Qt.AlignCenter)

        jl.addLayout(dpad)

        # -- Z Column --
        z_col = QVBoxLayout()
        z_col.setSpacing(3)

        z_label = QLabel("Z")
        z_label.setAlignment(Qt.AlignCenter)
        z_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #ffb347;")

        self.btn_z_plus = QPushButton("▲\nZ+"); self.btn_z_plus.setStyleSheet(_JOG_Z_STYLE)
        self.btn_z_minus = QPushButton("▼\nZ-"); self.btn_z_minus.setStyleSheet(_JOG_Z_STYLE)

        z_col.addWidget(z_label)
        z_col.addWidget(self.btn_z_plus)
        z_col.addWidget(self.btn_z_minus)
        z_col.addStretch(1)

        jl.addLayout(z_col)

        self.jog_buttons = [self.btn_x_plus, self.btn_x_minus, self.btn_y_plus,
                            self.btn_y_minus, self.btn_z_plus, self.btn_z_minus]

        # การตั้งค่า Jog (Step / Feed)
        jog_settings = QVBoxLayout()
        self.keyboard_cb = QCheckBox(tr("cb_keyboard_jog")); self.auto_unlock_cb = QCheckBox(tr("cb_auto_unlock"))
        step_row = QHBoxLayout(); self.step_lbl = QLabel(tr("lbl_step")); step_row.addWidget(self.step_lbl)
        self.step_mode = QComboBox(); self.step_mode.addItems(["0.1", "1", "10", "Custom"])
        self.step_mm = QDoubleSpinBox(); self.step_mm.setEnabled(False); self.step_mm.setSuffix(" mm")
        step_row.addWidget(self.step_mode); step_row.addWidget(self.step_mm)
        
        feed_row = QHBoxLayout(); self.feed_lbl = QLabel(tr("lbl_feed")); feed_row.addWidget(self.feed_lbl)
        self.feed = QSpinBox(); self.feed.setRange(1, 20000); self.feed.setValue(1000); self.feed.setSuffix(" mm/min")
        feed_row.addWidget(self.feed)
        
        jog_settings.addWidget(self.keyboard_cb); jog_settings.addWidget(self.auto_unlock_cb)
        jog_settings.addLayout(step_row); jog_settings.addLayout(feed_row)
        jog_settings.addStretch(1)
        jl.addLayout(jog_settings)
        
        # C. Move to Target (พิมพ์พิกัดแล้ววิ่งไป) - Moved inside Jog Control
        tgt_row = QHBoxLayout()
        tgt_row.setContentsMargins(0, 8, 0, 0)
        self.tx = QDoubleSpinBox(); self.tx.setRange(-999, 999); self.tx.setDecimals(3)
        self.ty = QDoubleSpinBox(); self.ty.setRange(-999, 999); self.ty.setDecimals(3)
        self.tz = QDoubleSpinBox(); self.tz.setRange(-999, 999); self.tz.setDecimals(3)
        self.move_btn = _btn(tr("btn_move"))
        for lbl, widget in [("X:", self.tx), ("Y:", self.ty), ("Z:", self.tz)]:
            tgt_row.addWidget(QLabel(lbl)); tgt_row.addWidget(widget)
        tgt_row.addWidget(self.move_btn)
        jog_vbox.addLayout(tgt_row)
        
        L.addWidget(self.jog_box)



        # D. Project & Waypoint Actions (ปุ่มนำเข้า/ส่งออกที่เคยหายไป)
        self.action_box = QGroupBox(tr("grp_project"))
        al = QVBoxLayout(self.action_box)
        
        # แถมบน: การตั้งค่า Waypoint
        teach = QGridLayout()
        self.wp_feed = QSpinBox(); self.wp_feed.setRange(1, 20000); self.wp_feed.setValue(1200); self.wp_feed.setSuffix(" mm/min")
        self.wp_laser_time = QDoubleSpinBox(); self.wp_laser_time.setValue(0.50); self.wp_laser_time.setSuffix(" s")
        self.wp_z_safe = QDoubleSpinBox(); self.wp_z_safe.setRange(-999, 0); self.wp_z_safe.setValue(-2.0)
        self.wp_power = QSpinBox(); self.wp_power.setRange(0, 255); self.wp_power.setValue(255)
        self.teach_labels = []
        for i, (lbl_key, widget) in enumerate([("lbl_wp_feed", self.wp_feed), ("lbl_wp_time", self.wp_laser_time),
                                               ("lbl_wp_zsafe", self.wp_z_safe), ("lbl_wp_power", self.wp_power)]):
            lbl = QLabel(tr(lbl_key))
            lbl._i18n_key = lbl_key
            self.teach_labels.append(lbl)
            teach.addWidget(lbl, i // 2, (i % 2) * 2)
            teach.addWidget(widget, i // 2, (i % 2) * 2 + 1)
        al.addLayout(teach)

        # แถวปุ่มปฏิบัติการ
        self.load_points_gcode_btn = _btn(tr("btn_load_gcode"))
        self.load_csv_pcb_btn = _btn(tr("btn_import_csv"))
        self.save_waypoints_btn = _btn(tr("btn_save_json"))
        self.load_waypoints_btn = _btn(tr("btn_load_json"), enabled=True)
        self.export_gcode_btn = _btn(tr("btn_exp_gcode"))
        self.export_panel_btn = _btn(tr("btn_exp_panel"))
        
        self.import_vector_btn = _btn(tr("btn_import_vector"))
        self.import_image_btn = _btn(tr("btn_import_image"))
        
        self.capture_btn = _btn(tr("btn_capture")); self.capture_btn.setStyleSheet("background-color: #198754; color: white;")
        self.update_btn = _btn(tr("btn_update_wp"))
        self.delete_btn = _btn(tr("btn_delete_wp"))
        self.clear_btn = _btn(tr("btn_clear_all"))
        self.preview3d_btn = _btn(tr("btn_3d_preview"))

        def hline():
            f = QFrame()
            f.setFrameShape(QFrame.HLine)
            f.setFrameShadow(QFrame.Sunken)
            return f

        # 1. File Operations
        file_ops = QGridLayout()
        file_ops.addWidget(self.load_points_gcode_btn, 0, 0)
        file_ops.addWidget(self.load_waypoints_btn, 0, 1)
        file_ops.addWidget(self.save_waypoints_btn, 0, 2)
        file_ops.addWidget(self.load_csv_pcb_btn, 1, 0)
        file_ops.addWidget(self.import_vector_btn, 1, 1)
        file_ops.addWidget(self.import_image_btn, 1, 2)

        # 2. Waypoint Actions
        wp_ops = QHBoxLayout()
        wp_ops.addWidget(self.capture_btn)
        wp_ops.addWidget(self.update_btn)
        wp_ops.addWidget(self.delete_btn)
        wp_ops.addWidget(self.clear_btn)

        # 3. Export Operations
        exp_ops = QHBoxLayout()
        exp_ops.addWidget(self.export_gcode_btn)
        exp_ops.addWidget(self.export_panel_btn)
        exp_ops.addWidget(self.preview3d_btn)
        
        al.addWidget(hline())
        al.addLayout(file_ops)
        al.addWidget(hline())
        al.addLayout(wp_ops)
        al.addWidget(hline())
        al.addLayout(exp_ops)
        L.addWidget(self.action_box)
        
        L.addStretch(1) # ดันไม่ให้ปุ่มแตกกระจาย

        # เอาฝั่งซ้ายใส่ ScrollArea
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setWidget(left)

        # ----- ฝั่งขวา: ตาราง Waypoints, Console, และ Log -----
        right = QWidget()
        R = QVBoxLayout(right)
        R.setContentsMargins(4, 0, 0, 0)

        # Waypoint Table (ตอนนี้ขยายได้เต็มที่โดยไม่บัง Status แล้ว)
        self.wp_box = QGroupBox(tr("grp_waypoints"))
        wp_layout = QVBoxLayout(self.wp_box)
        self.wp_table = QTableWidget()
        self.wp_table.setColumnCount(7)
        self.wp_table.setHorizontalHeaderLabels([
            tr("wp_col_no"), tr("wp_col_pos"), tr("wp_col_zwork"), tr("wp_col_zsafe"),
            tr("wp_col_feed"), tr("wp_col_time"), tr("wp_col_power")
        ])
        self.wp_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.wp_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.wp_table.setSelectionMode(QTableWidget.SingleSelection)
        self.wp_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        wp_layout.addWidget(self.wp_table)
        R.addWidget(self.wp_box, 3) # ให้ตารางกินพื้นที่เยอะที่สุด (Weight = 3)

        # Console & Log
        self.log_box = QGroupBox(tr("grp_console"))
        lv = QVBoxLayout(self.log_box)
        
        console_row = QHBoxLayout()
        self.console_input = QLineEdit()
        self.console_input.setPlaceholderText(tr("ph_console"))
        
        self.console_input.setStyleSheet("""
            QLineEdit {
                padding: 4px;
                font-family: monospace;
            }
        """)
        
        self.console_send_btn = _btn(tr("btn_send"), enabled=False)
        console_row.addWidget(self.console_input); console_row.addWidget(self.console_send_btn)
        lv.addLayout(console_row)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        
        self.log_view.setStyleSheet("""
            QTextEdit {
                font-family: monospace;
            }
        """)
        lv.addWidget(self.log_view)
        
        self.clear_log_btn = _btn(tr("btn_clear_log"), enabled=True)
        self.clear_log_btn.clicked.connect(self.app.clear_all_logs)
        lv.addWidget(self.clear_log_btn, alignment=Qt.AlignRight)
        
        R.addWidget(self.log_box, 1)

        # นำซ้ายและขวาใส่ Splitter
        splitter.addWidget(left_scroll)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1) # ฝั่งปุ่ม
        splitter.setStretchFactor(1, 3) # ฝั่งตารางกว้างกว่า
        
        root.addWidget(splitter)
        
        # Disable scroll wheel on spinboxes
        for w in self.findChildren(QSpinBox) + self.findChildren(QDoubleSpinBox):
            w.wheelEvent = lambda event: event.ignore()

    def _toggle_conn_type(self):
        if self.radio_serial.isChecked():
            self.conn_inputs.setCurrentWidget(self.serial_widget)
        else:
            self.conn_inputs.setCurrentWidget(self.tcp_widget)

    def retranslate_ui(self):
        """Dynamically update all translatable text in the control page."""
        self.conn_box.setTitle(tr("grp_connection"))
        self.port_lbl.setText(tr("lbl_port"))
        self.refresh_btn.setText(tr("btn_refresh"))
        self.connect_btn.setText(tr("btn_connect"))
        self.disconnect_btn.setText(tr("btn_disconnect"))

        self.status_box.setTitle(tr("grp_status"))

        self.cmd_box.setTitle(tr("grp_commands"))
        self.home_all_btn.setText(tr("btn_home_all"))
        self.home_x_btn.setText(tr("btn_home_x"))
        self.home_y_btn.setText(tr("btn_home_y"))
        self.home_z_btn.setText(tr("btn_home_z"))
        self.unlock_btn.setText(tr("btn_unlock"))
        self.zero_btn.setText(tr("btn_set_zero"))
        self.go_zero_btn.setText(tr("btn_go_zero"))
        self.go_work_zero_btn.setText(tr("btn_go_work_zero"))
        self.reset_btn.setText(tr("btn_reset"))
        self.estop_btn.setText(tr("btn_estop"))

        self.jog_box.setTitle(tr("grp_jog"))
        self.keyboard_cb.setText(tr("cb_keyboard_jog"))
        self.auto_unlock_cb.setText(tr("cb_auto_unlock"))
        self.step_lbl.setText(tr("lbl_step"))
        self.feed_lbl.setText(tr("lbl_feed"))

        self.move_btn.setText(tr("btn_move"))

        self.action_box.setTitle(tr("grp_project"))
        for lbl in self.teach_labels:
            lbl.setText(tr(lbl._i18n_key))
        self.load_points_gcode_btn.setText(tr("btn_load_gcode"))
        self.load_csv_pcb_btn.setText(tr("btn_import_csv"))
        self.save_waypoints_btn.setText(tr("btn_save_json"))
        self.load_waypoints_btn.setText(tr("btn_load_json"))
        self.export_gcode_btn.setText(tr("btn_exp_gcode"))
        self.export_panel_btn.setText(tr("btn_exp_panel"))
        self.import_vector_btn.setText(tr("btn_import_vector"))
        self.import_image_btn.setText(tr("btn_import_image"))
        self.capture_btn.setText(tr("btn_capture"))
        self.update_btn.setText(tr("btn_update_wp"))
        self.delete_btn.setText(tr("btn_delete_wp"))
        self.clear_btn.setText(tr("btn_clear_all"))
        self.preview3d_btn.setText(tr("btn_3d_preview"))

        self.wp_box.setTitle(tr("grp_waypoints"))
        self.wp_table.setHorizontalHeaderLabels([
            tr("wp_col_no"), tr("wp_col_pos"), tr("wp_col_zwork"), tr("wp_col_zsafe"),
            tr("wp_col_feed"), tr("wp_col_time"), tr("wp_col_power")
        ])

        self.log_box.setTitle(tr("grp_console"))
        self.console_input.setPlaceholderText(tr("ph_console"))
        self.console_send_btn.setText(tr("btn_send"))
        self.clear_log_btn.setText(tr("btn_clear_log"))

    def append_log(self, msg: str):
        self.log_view.append(msg)
