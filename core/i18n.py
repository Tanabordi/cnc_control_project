"""Internationalization (i18n) module for CNC Control.

Simple dictionary-based translation system supporting English and Thai.
"""

# Current language: "en" or "th"
_current_lang = "en"

TRANSLATIONS = {
    # ── App-level / Menu ──
    "window_title":          {"en": "CNC Control (GRBL-ESP32 / MKS DLC32)",
                              "th": "ควบคุม CNC"},
    "menu_control":          {"en": "Control",          "th": "ควบคุม"},
    "menu_gcode":            {"en": "G-code program",   "th": "โปรแกรม G-code"},
    "menu_settings":         {"en": "Settings",         "th": "ตั้งค่า"},
    "menu_exit":             {"en": "Exit",             "th": "ออก"},
    "page_control":          {"en": "Control",          "th": "ควบคุม"},
    "page_gcode":            {"en": "G-code program",   "th": "โปรแกรม G-code"},
    "page_settings":         {"en": "Settings",         "th": "ตั้งค่า"},

    # ── Control Page – Connection ──
    "grp_connection":        {"en": "🔌 Connection",    "th": "🔌 การเชื่อมต่อ"},
    "lbl_port":              {"en": "Port:",            "th": "พอร์ต:"},
    "btn_refresh":           {"en": "🔄 Refresh",       "th": "🔄 รีเฟรช"},
    "btn_connect":           {"en": "Connect",          "th": "เชื่อมต่อ"},
    "btn_disconnect":        {"en": "❌ Disconnect",    "th": "❌ ตัดการเชื่อมต่อ"},

    # ── Control Page – Machine Status ──
    "grp_status":            {"en": "📍 Machine Status", "th": "📍 สถานะเครื่องจักร"},
    "lbl_disconnected":      {"en": "Disconnected",     "th": "ไม่ได้เชื่อมต่อ"},

    # ── Control Page – Machine Commands ──
    "grp_commands":          {"en": "⚠️ Machine Commands", "th": "⚠️ คำสั่งเครื่อง"},
    "btn_home":              {"en": "🏠 Home",           "th": "🏠 Home"},
    "btn_home_all":          {"en": "🏠 Home All",       "th": "🏠 Home ทุกแกน"},
    "btn_home_x":            {"en": "🏠 Home X",         "th": "🏠 Home X"},
    "btn_home_y":            {"en": "🏠 Home Y",         "th": "🏠 Home Y"},
    "btn_home_z":            {"en": "🏠 Home Z",         "th": "🏠 Home Z"},
    "btn_go_work_zero":      {"en": "🎯 Go Work Zero",   "th": "🎯 ไปจุดศูนย์ชิ้นงาน"},
    "btn_unlock":            {"en": "🔓 Unlock",         "th": "🔓 ปลดล็อค"},
    "btn_set_zero":          {"en": "🎯 Set Zero (G54)", "th": "🎯 ตั้งจุดศูนย์ชิ้นงาน"},
    "btn_go_zero":           {"en": "🔙 Go Zero",       "th": "🔙 ไปจุดศูนย์"},
    "btn_reset":             {"en": "🔄 Reset",          "th": "🔄 รีเซ็ต"},
    "btn_estop":             {"en": "🛑 E-STOP",         "th": "🛑 หยุดฉุกเฉิน"},

    # ── Control Page – Jog Control ──
    "grp_jog":               {"en": "🕹️ Jog Control",   "th": "🕹️ ควบคุมทิศทาง"},
    "cb_keyboard_jog":       {"en": "Keyboard Jog",     "th": "Jog ด้วยคีย์บอร์ด"},
    "cb_auto_unlock":        {"en": "Auto Unlock",      "th": "ปลดล็อคอัตโนมัติ"},
    "lbl_step":              {"en": "Step:",             "th": "ระยะ:"},
    "lbl_feed":              {"en": "Feed:",             "th": "ความเร็ว:"},

    # ── Control Page – Move to Target ──
    "grp_move_target":       {"en": "🚀 Move to Precise Target", "th": "🚀 เคลื่อนที่ไปตำแหน่งเป้าหมาย"},
    "btn_move":              {"en": "Move",              "th": "เคลื่อนที่"},

    # ── Control Page – Project Actions ──
    "grp_project":           {"en": "📋 Project Actions", "th": "📋 จัดการโปรเจกต์"},
    "lbl_wp_feed":           {"en": "Feed:",              "th": "ความเร็ว:"},
    "lbl_wp_time":           {"en": "Time(s):",           "th": "เวลา:"},
    "lbl_wp_zsafe":          {"en": "Z Safe:",            "th": "Z ปลอดภัย:"},
    "lbl_wp_power":          {"en": "Power:",             "th": "กำลัง:"},
    "btn_load_gcode":        {"en": "📂 Load .gcode",     "th": "📂 โหลด .gcode"},
    "btn_import_csv":        {"en": "📊 Import PCB CSV",  "th": "📊 นำเข้า PCB CSV"},
    "btn_save_json":         {"en": "💾 Save .json",      "th": "💾 บันทึก .json"},
    "btn_load_json":         {"en": "📥 Load .json",      "th": "📥 โหลด .json"},
    "btn_exp_gcode":         {"en": "📤 Exp G-code",      "th": "📤 ส่งออก G-code"},
    "btn_exp_panel":         {"en": "📋 Exp Panel",       "th": "📋 ส่งออก Panel"},
    "btn_import_vector":     {"en": "📐 Import SVG/DXF",  "th": "📐 นำเข้า SVG/DXF"},
    "btn_import_image":      {"en": "🖼️ Import Image",   "th": "🖼️ นำเข้ารูปภาพ"},
    
    # ── Import Dialogs (Vector/Image/Calibration) ──
    "lbl_job_origin":        {"en": "Job Origin:",        "th": "จุดเริ่มต้นงาน:"},
    "origin_bottom_left":    {"en": "Bottom-Left (Default)", "th": "มุมล่างซ้าย"},
    "origin_center":         {"en": "Center of Bounding Box", "th": "กึ่งกลางชิ้นงาน"},
    "btn_calibrate_material":{"en": "🔧 Calibrate Material", "th": "🔧 ปรับตำแหน่งชิ้นงาน"},
    "dlg_calibration_title": {"en": "Material Calibration — 2-Point", "th": "ปรับตำแหน่ง — 2 จุดอ้างอิง"},
    "lbl_calib_step1":       {"en": "Step 1 — Jog to P1 (Bottom-Left corner):", "th": "ขั้นตอน 1 — เลื่อนหัวไปที่ P1:"},
    "lbl_calib_step2":       {"en": "Step 2 — Jog to P2 (Top-Right corner):", "th": "ขั้นตอน 2 — เลื่อนหัวไปที่ P2:"},

    "btn_capture":           {"en": "📍 Capture WP",      "th": "📍 บันทึกพิกัด"},
    "btn_update_wp":         {"en": "✏️ Update WP",       "th": "✏️ แก้ไขพิกัด"},
    "btn_delete_wp":         {"en": "🗑️ Delete WP",      "th": "🗑️ ลบพิกัด"},
    "btn_clear_all":         {"en": "🚨 Clear All",       "th": "🚨 ล้างทั้งหมด"},
    "btn_3d_preview":        {"en": "👁️ 3D Preview",     "th": "👁️ แสดงผล 3 มิติ"},

    # ── Control Page – Waypoints & Console ──
    "grp_waypoints":         {"en": "📍 Waypoints Table", "th": "📍 ตารางพิกัดทำงาน"},
    "wp_col_no":             {"en": "No.",                "th": "ลำดับ"},
    "wp_col_pos":            {"en": "Pos (X,Y)",          "th": "ตำแหน่ง"},
    "wp_col_zwork":          {"en": "Z work",             "th": "Z ทำงาน"},
    "wp_col_zsafe":          {"en": "Z safe",             "th": "Z ปลอดภัย"},
    "wp_col_feed":           {"en": "Feed",               "th": "ความเร็ว"},
    "wp_col_time":           {"en": "Time(s)",            "th": "เวลา"},
    "wp_col_power":          {"en": "Power",              "th": "กำลัง"},
    "grp_console":           {"en": "📋 Console / Log",   "th": "📋 คอนโซล / บันทึก"},
    "ph_console":            {"en": "Send direct GRBL command...", "th": "พิมพ์คำสั่ง GRBL โดยตรง..."},
    "btn_send":              {"en": "Send",               "th": "ส่ง"},
    "btn_clear_log":         {"en": "Clear Log",          "th": "ล้างบันทึก"},

    # ── Run Page ──
    "grp_gcode_program":     {"en": "G-code program",    "th": "โปรแกรม G-code"},
    "lbl_work_coords":       {"en": "Work coordinates:", "th": "พิกัดชิ้นงาน:"},
    "lbl_machine_coords":    {"en": "Machine coordinates:", "th": "พิกัดเครื่อง:"},
    "grp_state":             {"en": "State",              "th": "สถานะ"},
    "lbl_status":            {"en": "Status:",            "th": "สถานะ:"},
    "lbl_pins":              {"en": "Pins (Pn):",         "th": "พิน:"},
    "grp_log":               {"en": "Log",                "th": "บันทึก"},
    "grp_run_console":       {"en": "Console",            "th": "คอนโซล"},
    "ph_run_console":        {"en": "Send GRBL command (e.g. $I, ?, $$, G28 ...)",
                              "th": "พิมพ์คำสั่ง GRBL"},
    "cmd_col_no":            {"en": "#",                  "th": "#"},
    "cmd_col_command":       {"en": "Command",            "th": "คำสั่ง"},
    "cmd_col_state":         {"en": "State",              "th": "สถานะ"},
    "cmd_col_response":      {"en": "Response",           "th": "การตอบกลับ"},
    "cmd_in_queue":          {"en": "In queue",           "th": "รอคิว"},
    "cmd_running":           {"en": "Running",            "th": "กำลังทำงาน"},
    "cmd_done":              {"en": "Done",               "th": "เสร็จ"},
    "cmd_error":             {"en": "Error",              "th": "ผิดพลาด"},
    "btn_home_h":            {"en": "Home ($H)",          "th": "Home"},
    "btn_unlock_x":          {"en": "Unlock ($X)",        "th": "ปลดล็อค"},
    "btn_set_zero_g54":      {"en": "Set Work Zero (G54)","th": "ตั้งจุดศูนย์ชิ้นงาน"},
    "btn_go_zero_g53":       {"en": "Go Machine Zero (G53)","th": "ไปจุดศูนย์เครื่อง"},
    "btn_reset_ctrl_x":      {"en": "Reset (Ctrl+X)",     "th": "รีเซ็ต"},
    "cb_auto_x_reset":       {"en": "Auto $X after Reset","th": "ปลดล็อคอัตโนมัติหลังรีเซ็ต"},
    "btn_run_estop":         {"en": "E-STOP",             "th": "หยุดฉุกเฉิน"},
    "cb_check_mode":         {"en": "Check mode",         "th": "โหมดตรวจสอบ"},
    "cb_autoscroll":         {"en": "Autoscroll",         "th": "เลื่อนอัตโนมัติ"},
    "btn_open":              {"en": "Open",               "th": "เปิดไฟล์"},
    "btn_run_reset":         {"en": "Reset",              "th": "รีเซ็ต"},
    "btn_run_send":          {"en": "Send",               "th": "เริ่มทำงาน"},
    "btn_pause":             {"en": "Pause",              "th": "หยุดชั่วคราว"},
    "btn_resume":            {"en": "Resume",             "th": "ทำต่อ"},
    "btn_abort":             {"en": "Abort",              "th": "ยกเลิก"},
    "lbl_port_opened":       {"en": "Port opened",       "th": "เปิดพอร์ตแล้ว"},
    "lbl_run_disconnected":  {"en": "Disconnected",      "th": "ไม่ได้เชื่อมต่อ"},
    "dlg_confirm_run":       {"en": "Confirm Run",       "th": "ยืนยันการทำงาน"},
    "dlg_confirm_run_msg":   {"en": "Start streaming G-code?\n(Jog/Points will be locked during run for safety)",
                              "th": "ต้องการ Run G-code ใช่ไหม?\n"},
    "dlg_no_gcode":          {"en": "No G-code",          "th": "ไม่มี G-code"},
    "dlg_load_first":        {"en": "Load a G-code file first.", "th": "กรุณาโหลดไฟล์ G-code ก่อน"},
    "dlg_open_gcode":        {"en": "Open G-code",        "th": "เปิดไฟล์ G-code"},

    # ── Settings Page ──
    "tab_general":           {"en": "General",            "th": "ทั่วไป"},
    "tab_grbl":              {"en": "GRBL Parameters",    "th": "พารามิเตอร์ GRBL"},
    "grp_settings":          {"en": "Settings",           "th": "ตั้งค่า"},
    "lbl_baud":              {"en": "Baud rate",          "th": "อัตราบอด"},
    "lbl_poll_ms":           {"en": "Status poll interval (ms)", "th": "ช่วงเวลาสำรวจสถานะ"},
    "cb_auto_x_connect":     {"en": "Auto $X after Connect",    "th": "ปลดล็อคอัตโนมัติหลังเชื่อมต่อ"},
    "cb_auto_x_reset_s":     {"en": "Auto $X after Reset",      "th": "ปลดล็อคอัตโนมัติหลังรีเซ็ต"},
    "lbl_soft_limits":       {"en": "Soft Limits (mm)",   "th": "ขีดจำกัดซอฟต์"},
    "lbl_safe_z":            {"en": "Safe Z height (mm)", "th": "ความสูง Z ปลอดภัย"},
    "lbl_theme":             {"en": "Theme",              "th": "ธีม"},
    "btn_apply":             {"en": "Apply (No Save)",    "th": "ใช้งาน"},
    "btn_save_settings":     {"en": "Save to settings.json", "th": "บันทึกลง settings.json"},
    "btn_reload_settings":   {"en": "Reload from settings.json", "th": "โหลดจาก settings.json"},
    "btn_read_grbl":         {"en": "Read from GRBL ($$)","th": "อ่านค่าจาก GRBL"},
    "btn_test_conn":         {"en": "Test Connection ($I)","th": "ทดสอบการเชื่อมต่อ"},
    "btn_write_grbl":        {"en": "Write to GRBL",      "th": "เขียนค่าไป GRBL"},
    "grbl_col_param":        {"en": "Parameter",          "th": "พารามิเตอร์"},
    "grbl_col_value":        {"en": "Value",              "th": "ค่า"},
    "grbl_col_desc":         {"en": "Description",        "th": "คำอธิบาย"},
    "lbl_log_settings":      {"en": "Log:",               "th": "บันทึก:"},

    # ── Hard Limit Safety ──
    "hard_limit_title":      {"en": "⚠ Hard Limit Triggered",
                              "th": "⚠ ชนลิมิตสวิตช์"},
    "hard_limit_msg":        {"en": "Auto-recovery successful! Backed off 5mm.\n\nThe machine is locked for safety.\nClick 'Unlock' to continue using the machine.\n\n* Note: The direction that hit the sensor is temporarily locked.\nPlease move away from the sensor first.",
                              "th": "กู้คืนอัตโนมัติสำเร็จ! ถอยออกมา 5mm แล้ว\n\nเครื่องถูกล็อคเพื่อความปลอดภัย\nกรุณากด 'ปลดล็อค' เพื่อใช้งานต่อ\n\n* หมายเหตุ: ปุ่มทิศทางที่ชนเซ็นเซอร์จะถูกล็อคชั่วคราว\nให้คุณกดทิศทางตรงข้ามเพื่อขยับออกห่างเซ็นเซอร์ก่อน"},
    "hard_limit_unlock":     {"en": "Unlock",
                              "th": "ปลดล็อค"},
    "hard_limit_close":      {"en": "Close",              "th": "ปิด"},
    "hard_limit_log_hit":    {"en": "⚠ HARD LIMIT on axis [{axes}] — jog buttons locked",
                              "th": "⚠ ชนลิมิตสวิตช์ แกน [{axes}] — ปุ่ม Jog ถูกล็อค"},
    "hard_limit_log_start":  {"en": "🔧 Auto-Recovery starting... (back off 5mm)",
                              "th": "🔧 เริ่มกู้คืนอัตโนมัติ... (ถอย 5mm)"},
    "hard_limit_log_done":   {"en": "✅ Auto-Recovery complete — machine unlocked",
                              "th": "✅ กู้คืนอัตโนมัติสำเร็จ — เครื่องถูกปลดล็อค"},
    "hard_limit_log_fail":   {"en": "❌ Auto-Recovery failed: {err}",
                              "th": "❌ กู้คืนอัตโนมัติล้มเหลว: {err}"},

    # ── Network Scanner ──
    "btn_scan":              {"en": "🔍 Scan",           "th": "🔍 สแกน"},
    "scan_title":            {"en": "Network Scan — Find CNC Board",
                              "th": "สแกนเครือข่าย — ค้นหาบอร์ด CNC"},
    "scan_scanning":         {"en": "Scanning {subnet}...",
                              "th": "กำลังสแกน {subnet}..."},
    "scan_found":            {"en": "Found {count} device(s)",
                              "th": "พบ {count} อุปกรณ์"},
    "scan_no_device":        {"en": "No CNC board found on this network",
                              "th": "ไม่พบบอร์ด CNC ในเครือข่ายนี้"},
    "scan_select":           {"en": "Select",            "th": "เลือก"},
    "scan_rescan":           {"en": "🔄 Re-scan",        "th": "🔄 สแกนใหม่"},
    "scan_col_ip":           {"en": "IP Address",        "th": "IP"},
    "scan_col_port":         {"en": "Port",              "th": "พอร์ต"},
    "scan_col_info":         {"en": "Board Info",        "th": "ข้อมูลบอร์ด"},

    # ── Language selector ──
    "lbl_language":          {"en": "🌐 Language",        "th": "🌐 ภาษา"},
}


def tr(key: str) -> str:
    """Return the translated string for the given key in the current language."""
    entry = TRANSLATIONS.get(key)
    if entry is None:
        return key
    return entry.get(_current_lang, entry.get("en", key))


def set_language(lang: str):
    """Set the current language ('en' or 'th')."""
    global _current_lang
    if lang in ("en", "th"):
        _current_lang = lang


def get_language() -> str:
    """Return the current language code."""
    return _current_lang
