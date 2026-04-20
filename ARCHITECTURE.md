# Architecture — CNC Control

เอกสารสำหรับนักพัฒนาที่จะมาทำงานต่อ

---

## ภาพรวม Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Main.py  (entry point)                                      │
│    └─ App(QWidget)  [app.py]                                 │
│         ├─ ControlPage  [pages/control_page.py]  ← UI only  │
│         ├─ RunPage      [pages/run_page.py]      ← UI only  │
│         ├─ SettingsPage [pages/settings_page.py] ← UI only  │
│         └─ GrblWorker(QThread)  [worker.py]                  │
│                └─ serial.Serial  ← COM port                  │
└─────────────────────────────────────────────────────────────┘
```

**กฎสำคัญ:**
- `App` คือ controller ทั้งหมด — business logic อยู่ใน `app.py`
- `ControlPage / RunPage / SettingsPage` มีแค่ widget ไม่มี logic
- `GrblWorker` รันใน thread แยก — สื่อสารกลับมา `App` ผ่าน Qt Signals เท่านั้น

---

## ไฟล์และ Class หลัก

### `Main.py`
Entry point เดียว — สร้าง `QApplication` + `App` แล้ว exec loop
ตั้ง locale เป็น English เพื่อให้ float parse ได้ถูกต้อง (จุดทศนิยม `.`)

---

### `app.py` — App class

Class หลักของโปรแกรม ทำหน้าที่:
- สร้าง UI skeleton (top bar + QStackedWidget)
- ถือ `self.points: list[Point]` — waypoints ทั้งหมด
- รับ signals จาก `GrblWorker` แล้วอัปเดต UI
- ส่ง commands ไป worker

**Methods สำคัญ:**

| Method | หน้าที่ |
|---|---|
| `do_connect()` / `do_disconnect()` | เชื่อมต่อ/ตัด serial |
| `jog(axis, delta)` | ส่ง `$J=G91` command พร้อมเช็ค soft limits |
| `capture_point()` | บันทึกตำแหน่งปัจจุบันเป็น `Point` ใหม่ |
| `update_selected_point()` | อัปเดต point ที่เลือกด้วยตำแหน่งปัจจุบัน |
| `_refresh_table_from_points()` | วาด waypoint table ใหม่จาก `self.points` |
| `load_pcb_csv()` | เปิด dialog import PCB CSV |
| `export_gcode()` | Export waypoints → G-code (มี panel option) |
| `export_panel_gcode()` | Export panel พร้อม calibration dialog |
| `_build_panel_lines(offsets)` | สร้าง G-code lines จาก list of (r,c,ox,oy) |
| `on_status(payload)` | อัปเดต position labels ทุกหน้า |
| `on_log(msg)` | append log ทุกหน้า + handle homing sequence |
| `on_alarm(state)` | แสดง alarm dialog + lock jog |

**PanelConfigDialog** (ใน app.py):
Dialog เล็กสำหรับ Export G-code → checkbox "Export as Panel" + rows/cols spinners

---

### `worker.py` — GrblWorker(QThread)

QThread ที่วิ่งตลอด — poll status + stream G-code

**Signals ที่ emit:**

| Signal | Type | ความหมาย |
|---|---|---|
| `status` | `dict` | status payload จาก `<Idle\|WPos:x,y,z\|...>` |
| `log` | `str` | ข้อความ log ทุกบรรทัดที่รับจากเครื่อง |
| `connected` | `bool` | เปิด/ปิด serial สำเร็จ |
| `stream_state` | `str` | `"idle"/"running"/"paused"/"done"/"error"` |
| `line_sent` | `(int, str)` | index + command ที่ส่งไป |
| `line_ack` | `int` | index ที่ได้รับ `ok` กลับมา |
| `line_error_at` | `(int, str)` | index + error message |
| `stream_progress` | `(int, int)` | (lines_done, lines_total) |
| `alarm` | `str` | `"ALARM:N"` |
| `grbl_reset` | — | GRBL ส่ง startup banner (เครื่อง reset) |
| `grbl_param_line` | `str` | บรรทัดจาก `$$` command |

**Methods สำคัญ:**

| Method | หน้าที่ |
|---|---|
| `connect_serial(port, baud)` | เปิด port + emit `connected` |
| `disconnect_serial()` | ปิด port |
| `send_line(cmd)` | ส่ง command เดี่ยว (ไม่ผ่าน stream queue) |
| `start_stream(lines)` | เริ่ม stream list of G-code lines |
| `pause_stream()` / `resume_stream()` | หยุด/ดำเนินต่อ |
| `abort_stream()` | หยุดและล้าง queue |
| `last_wpos()` | คืนค่า `(x, y, z)` ล่าสุด หรือ `None` |

**Stream protocol:**
ส่งทีละบรรทัด รอ `ok` ก่อนส่งบรรทัดต่อไป (line-by-line with ack)

---

### `models.py` — Data Models

```python
@dataclass
class Point:
    name: str           # ชื่อ เช่น "P1", "C8"
    x: float            # Work coordinate X (mm)
    y: float            # Work coordinate Y (mm)
    z: float            # Z work — ความลึกทำงาน (mm)
    feed_to_next: int   # Feed rate ไปจุดถัดไป (mm/min)
    laser_time_s: float # เวลาหยุดยิง laser (วินาที) — G4 P
    z_safe: float       # Z safe สำหรับเคลื่อนที่ระหว่างจุด (mm)
    power: int          # Laser power S0-S255

@dataclass
class Segment:
    kind: str           # "G0" หรือ "G1"
    x0,y0,z0: float     # จุดเริ่มต้น
    x1,y1,z1: float     # จุดปลาย
```

**G-code ที่ได้จาก Point หนึ่งจุด:**
```gcode
G0 X{x} Y{y} Z{z_safe}   ← เคลื่อนที่ไว (rapid)
G1 Z{z} F{feed}            ← ลง Z ทำงาน
M3 S{power}                ← เปิด laser
G4 P{laser_time_s}         ← รอ
M5                         ← ปิด laser
G0 Z{z_safe}               ← ขึ้น Z safe
```

---

### `pcb_import.py` — PCB Import & Panel Export

**`parse_pcb_csv(path)`**
อ่าน KiCad position CSV คืน `(list[PcbComponent], has_side: bool)`
คอลัมน์ที่ต้องมี: `Ref, Val, Package, PosX, PosY, Rot` (และ `Side` ถ้ามี)

**`PcbComponent`** dataclass:
`ref, val, package, pos_x, pos_y, rot, side`

**`PcbCanvas(QWidget)`**
2D canvas วาด component เป็นจุด แสดง P1/P2 markers calibration
อัปเดตเมื่อ `set_p1_idx()` / `set_p2_idx()` / `set_side()`

**`PcbCalibDialog(QDialog)`**
Dialog import PCB CSV
- ซ้าย: PcbCanvas
- ขวา: เลือก side, jog controls, Set P1 / Set P2 / Set Z
- `get_waypoints(default_feed, default_time)` → คำนวณ affine transform จาก 2 calibration points แล้วแปลง PcbComponent coordinates → `list[Point]`

**Calibration math:**
```
transform = scale + rotation + translation
คำนวณจาก: (p1_csv, p1_machine) และ (p2_csv, p2_machine)
Z offset = z_surface (ค่าที่ set)
```

**`PanelCanvas(QWidget)`**
Canvas วาด grid ของ PCB copies
- เปลี่ยนตาม `rows`, `cols`, `ref_idx`
- สีพิเศษ: [1,1]=เขียว (origin), [1,2]=น้ำเงิน (step X), [2,1]=ส้ม (step Y)
- จุดสีฟ้า = reference waypoint, สีเหลือง = waypoints อื่น

**`PanelExportDialog(QDialog)`**
Dialog export panel G-code แบบ physical calibration
- กำหนด Rows × Columns
- เลือก Reference Waypoint
- Set Origin (PCB [1,1]) — วัดตำแหน่ง reference บน PCB แรก
- Set Step X (PCB [1,2]) — วัดระยะห่าง column
- Set Step Y (PCB [2,1]) — วัดระยะห่าง row
- `get_offsets()` → `list[(row, col, offset_x, offset_y)]`

**Offset calculation:**
```
base_offset = (origin_machine - ref_waypoint_coords)
vec_x = step_x_machine - origin_machine
vec_y = step_y_machine - origin_machine
PCB[r][c] offset = base_offset + c*vec_x + r*vec_y
```

---

### `gcode.py` — G-code Parser

**`parse_gcode_to_segments(lines)`** → `list[Segment]`
Parse G0/G1 commands รองรับ G90 (absolute) / G91 (relative)

**`estimate_run_time(lines)`** → `float` (วินาที)
ประมาณเวลารันจาก feed rate + ระยะทาง

ใช้ `matplotlib` สำหรับ 2D plot ใน RunPage

---

### `preview.py` — 3D Preview

**`Preview3DWindow(QDialog)`**
แสดงเส้นทาง waypoints ใน 3D ด้วย matplotlib
G0 = เส้นสีเทา, G1 = เส้นสีแดง

---

### `settings.py` — Settings

**`AppSettings`** dataclass เก็บ:

| Field | Default | ความหมาย |
|---|---|---|
| `baud` | 115200 | Baud rate |
| `status_poll_ms` | 150 | ความถี่ poll (ms) |
| `auto_unlock_after_connect` | True | ส่ง `$X` ทันทีหลัง connect |
| `auto_unlock_after_reset` | False | ส่ง `$X` หลัง reset |
| `xmin/xmax/ymin/ymax/zmin/zmax` | ±1000 | Soft limits |
| `last_port` | "" | COM port ที่ใช้ล่าสุด |
| `safe_z` | 5.0 | Z safe default |
| `theme` | "dark" | dark / light |

บันทึก/โหลดจาก `settings.json` ในโฟลเดอร์โปรแกรม

---

### `utils.py` — Helpers

| Function | หน้าที่ |
|---|---|
| `clamp(n, lo, hi)` | จำกัดค่าในช่วง |
| `_btn(text, ...)` | สร้าง QPushButton พร้อม style |
| `_set_enabled(btns, ok)` | enable/disable หลายปุ่มพร้อมกัน |
| `_read_text(path)` | อ่านไฟล์คืน list of lines |
| `_ts()` | timestamp string `HH:MM:SS` |
| `_strip_gcode_line(line)` | ตัด comment (`;` และ `(...)`) |
| `_parse_words(line)` | parse G-code words → `dict` เช่น `{"G":1,"X":10.5}` |
| `parse_xyz(csv_str)` | parse `"x,y,z"` string → tuple |
| `extract_field(line, key)` | ดึงค่าจาก GRBL status line เช่น `WPos:` |
| `extract_state(line)` | ดึง state จาก `<Idle\|...>` |
| `apply_theme(theme)` | ตั้ง Qt palette dark/light |

---

## Data Flow

### Connect → Poll → Display
```
App.do_connect()
  └→ worker.connect_serial(port)
       └→ serial.Serial.open()
       └→ worker.start()  ← thread เริ่มทำงาน
            └→ loop: ส่ง "?" ทุก 150ms
            └→ parse response "<Idle|WPos:x,y,z|...>"
            └→ emit status(payload)
  ←─ App.on_status(payload) ← update labels
```

### Capture Waypoint
```
User กด [Capture Waypoint]
  └→ App.capture_point()
       └→ worker.last_wpos()  ← ค่า position ล่าสุดใน memory
       └→ Point(name, x, y, z, feed, time, z_safe, power)
       └→ self.points.append(p)
       └→ _refresh_table_from_points()  ← update table UI
```

### Export G-code
```
App.export_gcode()
  └→ PanelConfigDialog (ถ้าต้องการ panel)
  └→ QFileDialog.getSaveFileName()
  └→ สร้าง lines:
       ["G90", "G21", "G54"]
       + _point_lines(p, ox, oy) สำหรับแต่ละ point
           G0 X Y Z_safe
           G1 Z F
           M3 S
           G4 P
           M5
           G0 Z_safe
  └→ write to file
```

### Stream G-code
```
User กด [Start] ใน RunPage
  └→ worker.start_stream(lines)
       └→ _stream_queue = deque(lines)
       └→ loop: ส่งทีละบรรทัด รอ "ok"
       └→ emit line_sent(idx, cmd)
       └→ emit line_ack(idx)
       └→ emit stream_progress(done, total)
  ←─ App._on_stream_progress() → RunPage.update_progress()
```

---

## ⚠️ สิ่งที่ต้องทำก่อนเริ่มพัฒนา

### 1. แก้ Merge Conflict ใน app.py (สำคัญมาก)

มี conflict markers อยู่ 2 จุด:

**จุดที่ 1 (~บรรทัด 98):** `_home_state` initial logic
**จุดที่ 2 (~บรรทัด 309-324):** homing sequence ใน `on_log()`

- **Branch master:** ส่ง `$3=4` (invert direction) ก่อน `$HZ` แล้ว reset `$3=0` หลัง homing เสร็จ
  เหมาะกับเครื่องที่ต้องกลับทิศ motor ก่อน home Z
- **Branch NewFeatures:** ไม่มีขั้นตอน invert direction

ต้องเลือกว่าเครื่องต้องการแบบไหน แล้วลบ conflict markers ออก

### 2. ทดสอบ Save Waypoints button
ปุ่ม Save Waypoints (.json) enabled เฉพาะเมื่อ `len(self.points) >= 1`
ตรวจสอบใน `_refresh_table_from_points()` บรรทัด ~470

---

## Branch ปัจจุบัน

- `master` — stable branch
- `NewFeatures` — branch ที่กำลังพัฒนา (current)

มี unresolved merge conflict ระหว่าง 2 branches อยู่ใน `app.py`
