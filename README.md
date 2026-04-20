# CNC Control — GRBL-ESP32 / MKS DLC32

โปรแกรมควบคุมเครื่อง CNC / Laser ผ่าน serial port (GRBL protocol)
สร้างด้วย Python + PySide6

---

## Requirements

```
Python 3.11+
PySide6
pyserial
matplotlib
```

ติดตั้ง dependencies:
```bash
pip install PySide6 pyserial matplotlib
```

---

## วิธีรัน

```bash
python Main.py
```

---

## ฟีเจอร์หลัก

### การเชื่อมต่อ
- เลือก COM port แล้วกด Connect
- Auto unlock (`$X`) หลัง connect / หลัง reset ได้ตั้งค่าใน Settings
- แสดง Work coordinates / Machine coordinates แบบ real-time (poll ทุก 150ms)

### Control Page
| ปุ่ม | หน้าที่ |
|---|---|
| Load Points (.gcode) | โหลด G-code แล้วแปลง G0/G1 เป็น waypoints |
| Import PCB CSV | นำเข้า component จาก KiCad CSV พร้อม dialog calibration |
| Save / Load Waypoints (.json) | บันทึก/โหลด waypoints เป็น JSON |
| Capture Waypoint | บันทึกตำแหน่งปัจจุบันเป็น waypoint ใหม่ |
| Update Selected | อัปเดต waypoint ที่เลือกด้วยตำแหน่งปัจจุบัน |
| Delete Selected | ลบ waypoint ที่เลือก |
| Clear Points | ล้าง waypoints ทั้งหมด |
| Preview 3D | แสดงเส้นทาง G-code ใน 3D (ต้องมีอย่างน้อย 2 points) |
| Export G-code (.gcode) | Export waypoints เป็น G-code (รองรับ Panel mode) |
| Export Panel (.gcode) | Export แบบ Panel พร้อม dialog calibration ตำแหน่งจริง |

**Jog:** ขยับหัวเครื่องด้วยปุ่มบน UI หรือ keyboard arrow keys
**คลิก waypoint ในตาราง:** เครื่องวิ่งไปที่ waypoint นั้นทันที

### Run Page
- โหลดไฟล์ G-code แล้ว stream ไปเครื่อง
- แสดง progress bar + เวลาที่เหลือโดยประมาณ
- แสดงตาราง G-code แต่ละบรรทัด (สถานะ: pending / sent / ok / error)
- 2D canvas แสดงเส้นทาง + จุดหัวเครื่อง real-time
- Start / Pause / Resume / Abort

### Settings Page
- Baud rate, poll interval
- Soft limits (XYZ min/max)
- Auto unlock behavior
- Theme (dark/light)

---

## Import PCB CSV (KiCad format)

CSV ที่รองรับ มีคอลัมน์: `Ref, Val, Package, PosX, PosY, Rot, Side`

**ขั้นตอน calibration:**
1. เลือก PCB Side (top/bottom)
2. เลือก component อ้างอิง P1 → Jog หัวไปที่ component จริงบนเครื่อง → กด Set P1
3. เลือก component อ้างอิง P2 → Jog → Set P2
4. Jog Z ลงแตะผิวชิ้นงาน → Set Z (Surface)
5. กด Confirm → ได้ waypoints ที่แปลงพิกัดแล้ว

---

## Export Panel G-code

ใช้สำหรับทำงานกับ PCB หลายชิ้นบน fixture เดียว

**ขั้นตอน:**
1. กำหนด Rows × Columns
2. เลือก Reference Waypoint (component อ้างอิง)
3. Jog ไปที่ reference บน PCB [1,1] → Set Origin
4. (ถ้า Columns > 1) Jog ไปที่ reference บน PCB [1,2] → Set Step X
5. (ถ้า Rows > 1) Jog ไปที่ reference บน PCB [2,1] → Set Step Y
6. กด Confirm → เลือก path บันทึกไฟล์

---

## โครงสร้างไฟล์

```
cnc_control/
├── Main.py              # Entry point
├── app.py               # App class (main window + business logic)
├── worker.py            # GrblWorker (QThread, serial, G-code streaming)
├── models.py            # Point, Segment dataclasses
├── gcode.py             # G-code parser + เวลาประมาณ
├── preview.py           # 3D preview window (matplotlib)
├── pcb_import.py        # PCB CSV parser, PcbCalibDialog, PanelExportDialog
├── settings.py          # AppSettings dataclass + load/save JSON
├── utils.py             # helper functions
├── pages/
│   ├── control_page.py  # UI หน้า Control
│   ├── run_page.py      # UI หน้า Run G-code
│   └── settings_page.py # UI หน้า Settings
├── CSV/                 # ตัวอย่างไฟล์ PCB CSV
└── settings.json        # config ที่บันทึกอัตโนมัติ
```

---

## ⚠️ Known Issues

### Merge Conflict ใน app.py (ยังไม่ resolve)
มี conflict markers `<<<<<<< HEAD` / `>>>>>>> NewFeatures` อยู่ใน `app.py` บริเวณ:
- `_home_state` logic (บรรทัด ~98-102)
- `on_log` homing sequence (บรรทัด ~309-324)

Branch `master` ใช้ `$3=4` (invert dir) ก่อน `$HZ` แล้ว reset `$3=0`
Branch `NewFeatures` ข้ามขั้นตอนนั้น
**ต้องตัดสินใจและแก้ conflict ก่อน production**

---

## Hardware ที่รองรับ

- GRBL-ESP32
- MKS DLC32
- ทุก controller ที่ใช้ GRBL protocol ผ่าน serial (115200 baud default)
