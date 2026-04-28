# CNC Control — GRBL-ESP32 / MKS DLC32

โปรแกรมควบคุมเครื่อง CNC / Laser ผ่าน Serial หรือ TCP/IP (GRBL protocol)  
สร้างด้วย Python + PySide6

CNC / Laser control software via Serial or TCP/IP (GRBL protocol).  
Built with Python + PySide6.

---

## Requirements / ความต้องการของระบบ

```
Python 3.11+
PySide6
pyserial
matplotlib
opencv-python (สำหรับ Image Import / for Image Import)
svgelements   (สำหรับ SVG Import / for SVG Import)
ezdxf         (สำหรับ DXF Import / for DXF Import)
```

ติดตั้ง dependencies / Install dependencies:
```bash
pip install -r requirements.txt
```

---

## วิธีรัน / How to Run

```bash
python Main.py
```

---

## ฟีเจอร์หลัก / Key Features

### การเชื่อมต่อ / Connection
- เชื่อมต่อผ่าน Serial COM port หรือ TCP/IP socket
- **Network Scanner:** สแกนหาบอร์ด CNC ในวง WiFi เดียวกันอัตโนมัติ (ไม่ต้องจำ IP)
- **Network Scanner:** Auto-discover CNC boards on the local WiFi network (no need to memorize IP)
- Auto unlock (`$X`) หลัง connect / หลัง reset ได้ตั้งค่าใน Settings
- แสดง Work coordinates / Machine coordinates แบบ real-time

### Control Page / หน้าควบคุม
| ปุ่ม / Button | หน้าที่ / Function |
|---|---|
| 🔍 Scan | สแกนหาบอร์ด CNC ในวงเครือข่าย / Scan for CNC boards on network |
| Load Points (.gcode) | โหลด G-code แปลงเป็น waypoints / Load G-code as waypoints |
| Import PCB CSV | นำเข้า component จาก KiCad CSV พร้อม calibration |
| Import Vector (SVG/DXF) | นำเข้าไฟล์ vector เป็น CNC waypoints |
| Import Image | แปลงภาพเป็นเส้นขอบด้วย edge detection |
| Save / Load Waypoints | บันทึก/โหลด waypoints เป็น JSON |
| Capture Waypoint | บันทึกตำแหน่งปัจจุบันเป็น waypoint ใหม่ |
| Export G-code | Export waypoints เป็น G-code (รองรับ Panel mode) |
| Preview 3D | แสดงเส้นทาง G-code ใน 3D |

**Jog:** ขยับหัวเครื่องด้วยปุ่มบน UI หรือ keyboard arrow keys  
**คลิก waypoint ในตาราง:** เครื่องวิ่งไปที่ waypoint นั้นทันที

### Run Page / หน้ารัน G-code
- โหลดไฟล์ G-code แล้ว stream ไปเครื่อง
- แสดง progress bar + เวลาที่เหลือโดยประมาณ
- 2D canvas แสดงเส้นทาง + จุดหัวเครื่อง real-time
- Start / Pause / Resume / Abort

### Settings Page / หน้าตั้งค่า
- Baud rate, poll interval, soft limits
- Auto unlock behavior
- Theme (dark/light)
- อ่าน/เขียน GRBL parameters ($$ / Read/Write GRBL parameters)

### Hard Limit Recovery / ระบบกู้คืนอัตโนมัติ
- ตรวจจับ Hard Limit (ALARM:1) อัตโนมัติ
- ถอยหลังออกจากเซ็นเซอร์ 5mm
- ล็อคทิศทางที่ชน ป้องกันชนซ้ำ
- ปลดล็อคอัตโนมัติเมื่อขยับออกจากเซ็นเซอร์

---

## โครงสร้างโปรเจกต์ / Project Structure

```
cnc_control_project/
│
├── Main.py                         # 🚀 จุดเริ่มต้นโปรแกรม / Entry point
├── README.md
├── requirements.txt
│
├── core/                           # 🧠 Core logic — ไม่มี UI / No UI dependencies
│   ├── controller.py               #   CNCController (business logic หลัก)
│   ├── models.py                   #   Point, Segment dataclasses
│   ├── settings.py                 #   AppSettings + load/save JSON
│   ├── worker.py                   #   GrblWorker (QThread, serial/TCP, G-code streaming)
│   ├── transform.py                #   Affine math (2-point calibration)
│   ├── i18n.py                     #   ระบบแปลภาษา EN/TH / Internationalization
│   └── grbl_parser.py              #   GRBL response parsing + utility functions
│
├── gui/                            # 🖥️ UI layer — เฉพาะหน้าจอ / Display only
│   ├── app.py                      #   MainWindow (slim — delegates to features)
│   ├── preview.py                  #   3D preview window (matplotlib)
│   ├── theme.py                    #   apply_theme() — dark/light palette
│   ├── ui_helpers.py               #   Widget helpers (_btn, _set_enabled)
│   ├── dialogs/                    #   📦 Dialog windows
│   │   └── panel_config_dialog.py  #     PanelConfigDialog (export settings)
│   └── pages/                      #   📄 หน้าจอหลัก / Main pages
│       ├── control_page.py         #     หน้า Control (jog, waypoints, commands)
│       ├── run_page.py             #     หน้า Run G-code (stream, progress)
│       └── settings_page.py        #     หน้า Settings (baud, limits, GRBL params)
│
├── features/                       # ⚙️ Feature modules — แยกตามฟีเจอร์ / By feature
│   ├── connection.py               #   📡 Serial/TCP connection management
│   ├── network_scanner.py          #   🔍 Network Scanner logic & dialog
│   ├── grbl_commands.py            #   🔧 GRBL commands ($H, $X, E-STOP, console)
│   ├── movement.py                 #   🕹️ Jog, step mode, move to target
│   ├── waypoint_ops.py             #   📍 Waypoint CRUD, file I/O, 3D preview
│   ├── gcode_parser.py             #   📜 G-code parsing, segment extraction, time estimation
│   ├── gcode_export.py             #   💾 G-code export + panel export
│   ├── signal_handlers.py          #   📡 Worker signal routing (status, log, alarm)
│   │
│   ├── hard_limit/                 #   🛡️ Hard Limit Recovery — ระบบกู้คืนอัตโนมัติ
│   │   ├── recovery.py             #     Auto-recovery logic (backoff, direction locks)
│   │   └── dialog.py               #     Hard limit notification dialog
│   │
│   └── importers/                  #   📥 File import features — นำเข้าไฟล์งาน
│       ├── vector_import.py        #     SVG/DXF import dialog
│       ├── image_import.py         #     Image edge tracing dialog (OpenCV)
│       ├── pcb_import.py           #     PCB CSV import + calibration
│       └── calibration_dialog.py   #     2-Point calibration (generic)
│
├── tests/                          # 🧪 Unit tests
│   └── test_transform.py           #   Test affine transform math
│
└── sample_data/                    # 📂 ไฟล์ตัวอย่าง / Sample data files
    ├── *-bottom-pos.csv
    └── *-top-pos.csv
```

---

## Import PCB CSV (KiCad format)

CSV ที่รองรับ มีคอลัมน์: `Ref, Val, Package, PosX, PosY, Rot, Side`

**ขั้นตอน calibration / Calibration steps:**
1. เลือก PCB Side (top/bottom)
2. เลือก component อ้างอิง P1 → Jog หัวไปที่ component จริง → กด Set P1
3. เลือก component อ้างอิง P2 → Jog → Set P2
4. Jog Z ลงแตะผิวชิ้นงาน → Set Z (Surface)
5. กด Confirm → ได้ waypoints ที่แปลงพิกัดแล้ว

---

## Export Panel G-code

ใช้สำหรับทำงานกับ PCB หลายชิ้นบน fixture เดียว  
Used for working with multiple PCBs on a single fixture.

**ขั้นตอน / Steps:**
1. กำหนด Rows × Columns
2. เลือก Reference Waypoint
3. Jog ไปที่ reference บน PCB [1,1] → Set Origin
4. (ถ้า Columns > 1) Jog ไปที่ PCB [1,2] → Set Step X
5. (ถ้า Rows > 1) Jog ไปที่ PCB [2,1] → Set Step Y
6. กด Confirm → เลือก path บันทึกไฟล์

---

## Hardware ที่รองรับ / Supported Hardware

- GRBL-ESP32
- MKS DLC32
- ทุก controller ที่ใช้ GRBL protocol / Any GRBL-compatible controller
- เชื่อมต่อผ่าน Serial (USB) หรือ TCP/IP (WiFi/LAN)
