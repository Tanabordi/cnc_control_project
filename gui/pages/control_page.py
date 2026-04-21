from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QComboBox, QSpinBox, QDoubleSpinBox, QSizePolicy,
    QTableWidget, QHeaderView, QTextEdit, QLineEdit,
    QApplication, QSplitter, QScrollArea, QFrame, QCheckBox, QGridLayout
)
from PySide6.QtCore import Qt
from core.utils import _btn

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
        conn_box = QGroupBox("🔌 Connection")
        c = QHBoxLayout(conn_box)
        c.setContentsMargins(6, 6, 6, 6)
        self.port_box = QComboBox()
        self.refresh_btn = _btn("🔄 Refresh", enabled=True)
        self.connect_btn = _btn("Connect", enabled=True)
        self.connect_btn.setObjectName("connect_btn")
        self.disconnect_btn = _btn("❌ Disconnect", enabled=False)
        c.addWidget(QLabel("Port:"))
        c.addWidget(self.port_box, 1)
        c.addWidget(self.refresh_btn)
        c.addWidget(self.connect_btn)
        c.addWidget(self.disconnect_btn)
        top_bar.addWidget(conn_box, 1)

        # 2. Machine Status (ขวาบน - ข้อมูลที่สำคัญที่สุดสำหรับ PCB)
        status_box = QGroupBox("📍 Machine Status")
        sg = QHBoxLayout(status_box)
        sg.setContentsMargins(10, 6, 10, 6)
        
        self.state_lbl = QLabel("Disconnected")
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
        top_bar.addWidget(status_box, 2)
        
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
        cmd_box = QGroupBox("⚠️ Machine Commands")
        cmd_layout = QHBoxLayout(cmd_box)
        self.home_btn = _btn("🏠 Home"); self.unlock_btn = _btn("🔓 Unlock")
        self.zero_btn = _btn("🎯 Set Zero (G54)"); self.go_zero_btn = _btn("🔙 Go Zero")
        self.reset_btn = _btn("🔄 Reset"); self.estop_btn = _btn("🛑 E-STOP")
        self.estop_btn.setObjectName("estop_btn")
        for b in [self.home_btn, self.unlock_btn, self.zero_btn, self.go_zero_btn, self.reset_btn, self.estop_btn]:
            cmd_layout.addWidget(b)
        L.addWidget(cmd_box)

        # B. Jogging Control (ปุ่มขยับเครื่อง)
        jog_box = QGroupBox("🕹️ Jog Control")
        jl = QHBoxLayout(jog_box)
        
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
        self.keyboard_cb = QCheckBox("Keyboard Jog"); self.auto_unlock_cb = QCheckBox("Auto Unlock")
        step_row = QHBoxLayout(); step_row.addWidget(QLabel("Step:")); 
        self.step_mode = QComboBox(); self.step_mode.addItems(["0.1", "1", "10", "Custom"])
        self.step_mm = QDoubleSpinBox(); self.step_mm.setEnabled(False)
        step_row.addWidget(self.step_mode); step_row.addWidget(self.step_mm)
        
        feed_row = QHBoxLayout(); feed_row.addWidget(QLabel("Feed:"))
        self.feed = QSpinBox(); self.feed.setRange(1, 20000); self.feed.setValue(1000)
        feed_row.addWidget(self.feed)
        
        jog_settings.addWidget(self.keyboard_cb); jog_settings.addWidget(self.auto_unlock_cb)
        jog_settings.addLayout(step_row); jog_settings.addLayout(feed_row)
        jl.addLayout(jog_settings)
        L.addWidget(jog_box)

        # C. Move to Target (พิมพ์พิกัดแล้ววิ่งไป)
        tgt_box = QGroupBox("🚀 Move to Precise Target")
        tgt_row = QHBoxLayout(tgt_box)
        self.tx = QDoubleSpinBox(); self.tx.setRange(-999, 999); self.tx.setDecimals(3)
        self.ty = QDoubleSpinBox(); self.ty.setRange(-999, 999); self.ty.setDecimals(3)
        self.tz = QDoubleSpinBox(); self.tz.setRange(-999, 999); self.tz.setDecimals(3)
        self.move_btn = _btn("Move")
        for lbl, widget in [("X:", self.tx), ("Y:", self.ty), ("Z:", self.tz)]:
            tgt_row.addWidget(QLabel(lbl)); tgt_row.addWidget(widget)
        tgt_row.addWidget(self.move_btn)
        L.addWidget(tgt_box)

        # D. Project & Waypoint Actions (ปุ่มนำเข้า/ส่งออกที่เคยหายไป)
        action_box = QGroupBox("📋 Project Actions")
        al = QVBoxLayout(action_box)
        
        # แถวบน: การตั้งค่า Waypoint
        teach = QHBoxLayout()
        self.wp_feed = QSpinBox(); self.wp_feed.setRange(1, 20000); self.wp_feed.setValue(1200)
        self.wp_laser_time = QDoubleSpinBox(); self.wp_laser_time.setValue(0.50)
        self.wp_z_safe = QDoubleSpinBox(); self.wp_z_safe.setRange(-999, 0); self.wp_z_safe.setValue(-2.0)
        self.wp_power = QSpinBox(); self.wp_power.setRange(0, 255); self.wp_power.setValue(255)
        for lbl, widget in [("Feed:", self.wp_feed), ("Time(s):", self.wp_laser_time), ("Z Safe:", self.wp_z_safe), ("Power:", self.wp_power)]:
            teach.addWidget(QLabel(lbl)); teach.addWidget(widget)
        al.addLayout(teach)

        # แถวปุ่มปฏิบัติการ
        self.load_points_gcode_btn = _btn("📂 Load .gcode")
        self.load_csv_pcb_btn = _btn("📊 Import PCB CSV")
        self.save_waypoints_btn = _btn("💾 Save .json")
        self.load_waypoints_btn = _btn("📥 Load .json", enabled=True)
        self.export_gcode_btn = _btn("📤 Exp G-code")
        self.export_panel_btn = _btn("📋 Exp Panel")
        
        self.import_vector_btn = _btn("📐 Import SVG/DXF")
        self.import_image_btn = _btn("🖼️ Import Image")
        
        self.capture_btn = _btn("📍 Capture WP"); self.capture_btn.setStyleSheet("background-color: #198754; color: white;")
        self.update_btn = _btn("✏️ Update WP")
        self.delete_btn = _btn("🗑️ Delete WP")
        self.clear_btn = _btn("🚨 Clear All")
        self.preview3d_btn = _btn("👁️ 3D Preview")

        btn_grid = QGridLayout()
        btn_grid.addWidget(self.load_csv_pcb_btn, 0, 0); btn_grid.addWidget(self.load_points_gcode_btn, 0, 1); btn_grid.addWidget(self.preview3d_btn, 0, 2)
        btn_grid.addWidget(self.save_waypoints_btn, 1, 0); btn_grid.addWidget(self.load_waypoints_btn, 1, 1); btn_grid.addWidget(self.export_gcode_btn, 1, 2)
        btn_grid.addWidget(self.capture_btn, 2, 0); btn_grid.addWidget(self.update_btn, 2, 1); btn_grid.addWidget(self.export_panel_btn, 2, 2)
        btn_grid.addWidget(self.delete_btn, 3, 0); btn_grid.addWidget(self.clear_btn, 3, 1)
        btn_grid.addWidget(self.import_vector_btn, 4, 0); btn_grid.addWidget(self.import_image_btn, 4, 1)
        al.addLayout(btn_grid)
        L.addWidget(action_box)
        
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
        wp_box = QGroupBox("📍 Waypoints Table")
        wp_layout = QVBoxLayout(wp_box)
        self.wp_table = QTableWidget()
        self.wp_table.setColumnCount(7)
        self.wp_table.setHorizontalHeaderLabels(["No.", "Pos (X,Y)", "Z work", "Z safe", "Feed", "Time(s)", "Power"])
        self.wp_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.wp_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.wp_table.setSelectionMode(QTableWidget.SingleSelection)
        self.wp_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        wp_layout.addWidget(self.wp_table)
        R.addWidget(wp_box, 3) # ให้ตารางกินพื้นที่เยอะที่สุด (Weight = 3)

        # Console & Log
        log_box = QGroupBox("📋 Console_Log")
        lv = QVBoxLayout(log_box)
        
        console_row = QHBoxLayout()
        self.console_input = QLineEdit()
        self.console_input.setPlaceholderText("Send direct GRBL command...")
        
        self.console_input.setStyleSheet("""
            QLineEdit {
                padding: 4px;
                font-family: monospace;
            }
        """)
        
        self.console_send_btn = _btn("Send", enabled=False)
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
        
        self.clear_log_btn = _btn("Clear Log", enabled=True)
        self.clear_log_btn.clicked.connect(self.app.clear_all_logs)
        lv.addWidget(self.clear_log_btn, alignment=Qt.AlignRight)
        
        R.addWidget(log_box, 1)

        # นำซ้ายและขวาใส่ Splitter
        splitter.addWidget(left_scroll)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1) # ฝั่งปุ่ม
        splitter.setStretchFactor(1, 2) # ฝั่งตารางกว้างกว่า
        
        root.addWidget(splitter)

    def append_log(self, msg: str):
        self.log_view.append(msg)
