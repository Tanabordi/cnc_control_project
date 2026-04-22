from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QComboBox, QSpinBox, QDoubleSpinBox, QSizePolicy,
    QTableWidget, QHeaderView, QTextEdit, QLineEdit,
    QApplication, QSplitter, QScrollArea, QFrame, QCheckBox, QGridLayout
)
from PySide6.QtCore import Qt
from core.utils import _btn
from core.i18n import tr

# จำลองตารางเพื่อให้ไม่ติด Error
WaypointTable = QTableWidget

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
        c = QHBoxLayout(self.conn_box)
        c.setContentsMargins(6, 6, 6, 6)
        self.port_box = QComboBox()
        self.refresh_btn = _btn(tr("btn_refresh"), enabled=True)
        self.connect_btn = _btn(tr("btn_connect"), enabled=True)
        self.connect_btn.setObjectName("connect_btn")
        self.disconnect_btn = _btn(tr("btn_disconnect"), enabled=False)
        self.port_lbl = QLabel(tr("lbl_port"))
        c.addWidget(self.port_lbl)
        c.addWidget(self.port_box, 1)
        c.addWidget(self.refresh_btn)
        c.addWidget(self.connect_btn)
        c.addWidget(self.disconnect_btn)
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
        L = QVBoxLayout(left)
        L.setContentsMargins(0, 0, 4, 0)
        
        # A. Quick Commands (โซนอันตราย/ตั้งค่าเครื่อง)
        self.cmd_box = QGroupBox(tr("grp_commands"))
        cmd_layout = QHBoxLayout(self.cmd_box)
        self.home_btn = _btn(tr("btn_home")); self.unlock_btn = _btn(tr("btn_unlock"))
        self.zero_btn = _btn(tr("btn_set_zero")); self.go_zero_btn = _btn(tr("btn_go_zero"))
        self.reset_btn = _btn(tr("btn_reset")); self.estop_btn = _btn(tr("btn_estop"))
        self.estop_btn.setObjectName("estop_btn")
        for b in [self.home_btn, self.unlock_btn, self.zero_btn, self.go_zero_btn, self.reset_btn, self.estop_btn]:
            cmd_layout.addWidget(b)
        L.addWidget(self.cmd_box)

        # B. Jogging Control (ปุ่มขยับเครื่อง)
        self.jog_box = QGroupBox(tr("grp_jog"))
        jl = QHBoxLayout(self.jog_box)
        
        grid = QGridLayout()
        self.btn_y_plus = _btn("Y+"); self.btn_y_minus = _btn("Y-")
        self.btn_x_plus = _btn("X+"); self.btn_x_minus = _btn("X-")
        self.btn_z_plus = _btn("Z+"); self.btn_z_minus = _btn("Z-")
        self.jog_buttons = [self.btn_x_plus, self.btn_x_minus, self.btn_y_plus, self.btn_y_minus, self.btn_z_plus, self.btn_z_minus]
        
        grid.addWidget(self.btn_y_plus, 0, 1); grid.addWidget(self.btn_x_minus, 1, 0)
        grid.addWidget(self.btn_x_plus, 1, 2); grid.addWidget(self.btn_y_minus, 2, 1)
        grid.addWidget(self.btn_z_plus, 0, 3); grid.addWidget(self.btn_z_minus, 2, 3)
        jl.addLayout(grid)

        # การตั้งค่า Jog (Step / Feed)
        jog_settings = QVBoxLayout()
        self.keyboard_cb = QCheckBox(tr("cb_keyboard_jog")); self.auto_unlock_cb = QCheckBox(tr("cb_auto_unlock"))
        step_row = QHBoxLayout(); self.step_lbl = QLabel(tr("lbl_step")); step_row.addWidget(self.step_lbl)
        self.step_mode = QComboBox(); self.step_mode.addItems(["0.1", "1", "10", "Custom"])
        self.step_mm = QDoubleSpinBox(); self.step_mm.setEnabled(False)
        step_row.addWidget(self.step_mode); step_row.addWidget(self.step_mm)
        
        feed_row = QHBoxLayout(); self.feed_lbl = QLabel(tr("lbl_feed")); feed_row.addWidget(self.feed_lbl)
        self.feed = QSpinBox(); self.feed.setRange(1, 20000); self.feed.setValue(1000)
        feed_row.addWidget(self.feed)
        
        jog_settings.addWidget(self.keyboard_cb); jog_settings.addWidget(self.auto_unlock_cb)
        jog_settings.addLayout(step_row); jog_settings.addLayout(feed_row)
        jl.addLayout(jog_settings)
        L.addWidget(self.jog_box)

        # C. Move to Target (พิมพ์พิกัดแล้ววิ่งไป)
        self.tgt_box = QGroupBox(tr("grp_move_target"))
        tgt_row = QHBoxLayout(self.tgt_box)
        self.tx = QDoubleSpinBox(); self.tx.setRange(-999, 999); self.tx.setDecimals(3)
        self.ty = QDoubleSpinBox(); self.ty.setRange(-999, 999); self.ty.setDecimals(3)
        self.tz = QDoubleSpinBox(); self.tz.setRange(-999, 999); self.tz.setDecimals(3)
        self.move_btn = _btn(tr("btn_move"))
        for lbl, widget in [("X:", self.tx), ("Y:", self.ty), ("Z:", self.tz)]:
            tgt_row.addWidget(QLabel(lbl)); tgt_row.addWidget(widget)
        tgt_row.addWidget(self.move_btn)
        L.addWidget(self.tgt_box)

        # D. Project & Waypoint Actions (ปุ่มนำเข้า/ส่งออกที่เคยหายไป)
        self.action_box = QGroupBox(tr("grp_project"))
        al = QVBoxLayout(self.action_box)
        
        # แถมบน: การตั้งค่า Waypoint
        teach = QHBoxLayout()
        self.wp_feed = QSpinBox(); self.wp_feed.setRange(1, 20000); self.wp_feed.setValue(1200)
        self.wp_laser_time = QDoubleSpinBox(); self.wp_laser_time.setValue(0.50)
        self.wp_z_safe = QDoubleSpinBox(); self.wp_z_safe.setRange(-999, 0); self.wp_z_safe.setValue(-2.0)
        self.wp_power = QSpinBox(); self.wp_power.setRange(0, 255); self.wp_power.setValue(255)
        self.teach_labels = []
        for lbl_key, widget in [("lbl_wp_feed", self.wp_feed), ("lbl_wp_time", self.wp_laser_time),
                                ("lbl_wp_zsafe", self.wp_z_safe), ("lbl_wp_power", self.wp_power)]:
            lbl = QLabel(tr(lbl_key))
            lbl._i18n_key = lbl_key
            self.teach_labels.append(lbl)
            teach.addWidget(lbl); teach.addWidget(widget)
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

        btn_grid = QGridLayout()
        btn_grid.addWidget(self.load_csv_pcb_btn, 0, 0); btn_grid.addWidget(self.load_points_gcode_btn, 0, 1); btn_grid.addWidget(self.preview3d_btn, 0, 2)
        btn_grid.addWidget(self.save_waypoints_btn, 1, 0); btn_grid.addWidget(self.load_waypoints_btn, 1, 1); btn_grid.addWidget(self.export_gcode_btn, 1, 2)
        btn_grid.addWidget(self.capture_btn, 2, 0); btn_grid.addWidget(self.update_btn, 2, 1); btn_grid.addWidget(self.export_panel_btn, 2, 2)
        btn_grid.addWidget(self.delete_btn, 3, 0); btn_grid.addWidget(self.clear_btn, 3, 1)
        btn_grid.addWidget(self.import_vector_btn, 4, 0); btn_grid.addWidget(self.import_image_btn, 4, 1)
        al.addLayout(btn_grid)
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
        self.log_view.setMaximumHeight(150)
        
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
        splitter.setStretchFactor(1, 2) # ฝั่งตารางกว้างกว่า
        
        root.addWidget(splitter)

    def retranslate_ui(self):
        """Dynamically update all translatable text in the control page."""
        self.conn_box.setTitle(tr("grp_connection"))
        self.port_lbl.setText(tr("lbl_port"))
        self.refresh_btn.setText(tr("btn_refresh"))
        self.connect_btn.setText(tr("btn_connect"))
        self.disconnect_btn.setText(tr("btn_disconnect"))

        self.status_box.setTitle(tr("grp_status"))

        self.cmd_box.setTitle(tr("grp_commands"))
        self.home_btn.setText(tr("btn_home"))
        self.unlock_btn.setText(tr("btn_unlock"))
        self.zero_btn.setText(tr("btn_set_zero"))
        self.go_zero_btn.setText(tr("btn_go_zero"))
        self.reset_btn.setText(tr("btn_reset"))
        self.estop_btn.setText(tr("btn_estop"))

        self.jog_box.setTitle(tr("grp_jog"))
        self.keyboard_cb.setText(tr("cb_keyboard_jog"))
        self.auto_unlock_cb.setText(tr("cb_auto_unlock"))
        self.step_lbl.setText(tr("lbl_step"))
        self.feed_lbl.setText(tr("lbl_feed"))

        self.tgt_box.setTitle(tr("grp_move_target"))
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
