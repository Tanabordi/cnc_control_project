import csv
import math
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QWidget, QComboBox,
    QMessageBox, QSpinBox, QSizePolicy, QGridLayout,
)

from models import Point


@dataclass
class PcbComponent:
    ref: str
    val: str
    package: str
    pos_x: float
    pos_y: float
    rot: float
    side: str


def parse_pcb_csv(path: str):
    """Returns (list[PcbComponent], has_side_column: bool)"""
    components = []
    has_side = False

    with open(path, encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        headers = [h.strip() for h in (reader.fieldnames or [])]
        has_side = "Side" in headers

        for row in reader:
            try:
                ref = row.get("Ref", "").strip()
                val = row.get("Val", "").strip()
                package = row.get("Package", "").strip()
                pos_x = float(row.get("PosX", 0))
                pos_y = float(row.get("PosY", 0))
                rot = float(row.get("Rot", 0))
                side = row.get("Side", "top").strip().lower() if has_side else "top"
                if ref:
                    components.append(PcbComponent(ref, val, package, pos_x, pos_y, rot, side))
            except (ValueError, KeyError):
                continue

    return components, has_side


class PcbCanvas(QWidget):
    """2D preview of PCB components with calibration point markers."""

    def __init__(self, components, side: str, parent=None):
        super().__init__(parent)
        self.components = components
        self.side = side
        self.p1_set = False
        self.p2_set = False
        self.setMinimumSize(300, 300)
        self._margin = 44
        self._recompute_bounds()

    def _recompute_bounds(self):
        if not self.components:
            self.data_xmin = self.data_xmax = 0.0
            self.data_ymin = self.data_ymax = 0.0
            return
        xs = [c.pos_x for c in self.components]
        ys = [c.pos_y for c in self.components]
        self.data_xmin, self.data_xmax = min(xs), max(xs)
        self.data_ymin, self.data_ymax = min(ys), max(ys)

    def _to_canvas(self, csv_x: float, csv_y: float):
        """CSV coords → canvas pixel coords. KiCad Y-up → canvas Y-down."""
        w = self.width() - 2 * self._margin
        h = self.height() - 2 * self._margin
        x_span = (self.data_xmax - self.data_xmin) or 1.0
        y_span = (self.data_ymax - self.data_ymin) or 1.0

        # Bottom-side: mirror X around board centre
        if self.side == "bottom":
            csv_x = self.data_xmin + self.data_xmax - csv_x

        tx = self._margin + (csv_x - self.data_xmin) / x_span * w
        ty = self._margin + (1.0 - (csv_y - self.data_ymin) / y_span) * h
        return tx, ty

    def paintEvent(self, event):
        if not self.components:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background
        painter.fillRect(self.rect(), QColor(18, 56, 18))

        # PCB board outline
        tl = self._to_canvas(self.data_xmin, self.data_ymax)
        br = self._to_canvas(self.data_xmax, self.data_ymin)
        rx = int(min(tl[0], br[0]))
        ry = int(min(tl[1], br[1]))
        rw = int(abs(br[0] - tl[0]))
        rh = int(abs(br[1] - tl[1]))
        painter.setPen(QPen(QColor(70, 170, 70), 2))
        painter.setBrush(QBrush(QColor(28, 90, 28)))
        painter.drawRect(rx, ry, rw, rh)

        # Components
        painter.setFont(QFont("Arial", 7))
        for comp in self.components:
            cx, cy = self._to_canvas(comp.pos_x, comp.pos_y)
            painter.setPen(QPen(QColor(255, 220, 0), 1))
            painter.setBrush(QBrush(QColor(255, 200, 0, 210)))
            r = 4
            painter.drawEllipse(int(cx - r), int(cy - r), r * 2, r * 2)
            painter.setPen(QColor(210, 210, 160))
            painter.drawText(int(cx + 6), int(cy + 4), comp.ref)

        # Calibration corner markers
        if self.side == "bottom":
            p1_csv = (self.data_xmax, self.data_ymax)
            p2_csv = (self.data_xmin, self.data_ymin)
        else:
            p1_csv = (self.data_xmin, self.data_ymax)
            p2_csv = (self.data_xmax, self.data_ymin)

        p1x, p1y = self._to_canvas(*p1_csv)
        p2x, p2y = self._to_canvas(*p2_csv)

        # P1 — top-left (blue when set, grey when not)
        c1 = QColor(0, 170, 255) if self.p1_set else QColor(70, 110, 150)
        painter.setPen(QPen(c1, 2))
        painter.setBrush(QBrush(c1))
        painter.drawEllipse(int(p1x - 8), int(p1y - 8), 16, 16)
        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", 8, QFont.Bold))
        painter.drawText(int(p1x - 5), int(p1y + 4), "P1")

        # P2 — bottom-right (orange when set, grey when not)
        c2 = QColor(255, 120, 0) if self.p2_set else QColor(150, 100, 60)
        painter.setPen(QPen(c2, 2))
        painter.setBrush(QBrush(c2))
        painter.drawEllipse(int(p2x - 8), int(p2y - 8), 16, 16)
        painter.setPen(Qt.white)
        painter.drawText(int(p2x - 5), int(p2y + 4), "P2")

        # Dimension labels
        painter.setPen(QColor(160, 200, 160))
        painter.setFont(QFont("Arial", 8))
        bw = round(self.data_xmax - self.data_xmin, 2)
        bh = round(self.data_ymax - self.data_ymin, 2)
        painter.drawText(rx, ry - 6, f"{bw} mm")
        painter.drawText(4, ry + rh // 2, f"{bh}mm")

        painter.end()


class PcbCalibDialog(QDialog):
    """
    Step-by-step PCB calibration dialog.
    User jogs to 2 corner points to define the board origin and orientation.
    """

    def __init__(self, components, has_side: bool, worker, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import PCB CSV — Calibration")
        self.setModal(True)
        self.resize(1050, 680)

        self.components = components
        self.worker = worker
        self.p1_machine = None   # (x, y) or None
        self.p2_machine = None   # (x, y) or None

        xs = [c.pos_x for c in components]
        ys = [c.pos_y for c in components]
        self.csv_xmin, self.csv_xmax = min(xs), max(xs)
        self.csv_ymin, self.csv_ymax = min(ys), max(ys)

        # Determine initial side from CSV
        if has_side:
            sides = set(c.side for c in components)
            self._side = "bottom" if "bottom" in sides else "top"
        else:
            self._side = "top"

        self._build_ui(has_side)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_pos)
        self._timer.start(150)

    # ------------------------------------------------------------------ UI --

    def _build_ui(self, has_side: bool):
        main = QHBoxLayout(self)
        main.setSpacing(10)

        # ===== Left: canvas =====
        left_w = QWidget()
        lv = QVBoxLayout(left_w)
        lv.setContentsMargins(0, 0, 0, 0)

        board_w = round(self.csv_xmax - self.csv_xmin, 2)
        board_h = round(self.csv_ymax - self.csv_ymin, 2)
        info_lbl = QLabel(
            f"PCB Preview  —  {len(self.components)} components  |  "
            f"Board: {board_w} × {board_h} mm"
        )
        info_lbl.setAlignment(Qt.AlignCenter)
        lv.addWidget(info_lbl)

        self.canvas = PcbCanvas(self.components, self._side)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lv.addWidget(self.canvas, 1)

        # Corner legend
        legend = QHBoxLayout()
        dot_p1 = QLabel("●")
        dot_p1.setStyleSheet("color: #00aaff; font-size: 14px;")
        legend.addWidget(dot_p1)
        legend.addWidget(QLabel("P1 = TOP-LEFT ของบอร์ด"))
        legend.addSpacing(20)
        dot_p2 = QLabel("●")
        dot_p2.setStyleSheet("color: #ff7700; font-size: 14px;")
        legend.addWidget(dot_p2)
        legend.addWidget(QLabel("P2 = BOTTOM-RIGHT ของบอร์ด"))
        legend.addStretch(1)
        lv.addLayout(legend)

        main.addWidget(left_w, 1)

        # ===== Right: controls (fixed width) =====
        right_w = QWidget()
        right_w.setFixedWidth(350)
        rv = QVBoxLayout(right_w)
        rv.setSpacing(8)

        # --- Side selector ---
        side_box = QGroupBox("PCB Side")
        sv = QHBoxLayout(side_box)
        if has_side:
            sides_found = sorted(set(c.side for c in self.components))
            sv.addWidget(QLabel(f"จาก CSV: {', '.join(sides_found)}"))
        else:
            sv.addWidget(QLabel("ไม่มี Side ใน CSV — เลือก:"))
        self.side_combo = QComboBox()
        self.side_combo.addItems(["top", "bottom"])
        self.side_combo.setCurrentText(self._side)
        self.side_combo.currentTextChanged.connect(self._on_side_changed)
        sv.addWidget(self.side_combo)
        rv.addWidget(side_box)

        # --- Live position ---
        pos_box = QGroupBox("Machine Work Position")
        pv = QVBoxLayout(pos_box)
        self.pos_lbl = QLabel("X: -.---   Y: -.---   Z: -.---")
        self.pos_lbl.setAlignment(Qt.AlignCenter)
        self.pos_lbl.setStyleSheet(
            "font-size: 13px; font-weight: bold; font-family: monospace;"
        )
        pv.addWidget(self.pos_lbl)
        rv.addWidget(pos_box)

        # --- Jog controls ---
        jog_box = QGroupBox("Jog — ขยับหัวเครื่อง")
        jv = QVBoxLayout(jog_box)

        grid = QGridLayout()
        grid.setSpacing(4)
        self._jb_up   = QPushButton("▲ Y+")
        self._jb_dn   = QPushButton("▼ Y−")
        self._jb_lt   = QPushButton("◀ X−")
        self._jb_rt   = QPushButton("▶ X+")
        self._jb_zup  = QPushButton("Z+")
        self._jb_zdn  = QPushButton("Z−")
        for b in (self._jb_up, self._jb_dn, self._jb_lt,
                  self._jb_rt, self._jb_zup, self._jb_zdn):
            b.setMinimumSize(QSize(54, 36))
        grid.addWidget(self._jb_up,  0, 1)
        grid.addWidget(self._jb_lt,  1, 0)
        grid.addWidget(self._jb_rt,  1, 2)
        grid.addWidget(self._jb_dn,  2, 1)
        grid.addWidget(self._jb_zup, 0, 4)
        grid.addWidget(self._jb_zdn, 2, 4)
        jv.addLayout(grid)

        step_row = QHBoxLayout()
        step_row.addWidget(QLabel("Step (mm):"))
        self.jog_step = QComboBox()
        self.jog_step.addItems(["0.1", "1", "10"])
        self.jog_step.setCurrentText("1")
        step_row.addWidget(self.jog_step)
        step_row.addWidget(QLabel("Feed:"))
        self.jog_feed = QSpinBox()
        self.jog_feed.setRange(1, 10000)
        self.jog_feed.setValue(2000)
        step_row.addWidget(self.jog_feed)
        jv.addLayout(step_row)

        rv.addWidget(jog_box)

        self._jb_up.clicked.connect(lambda: self._jog("Y", +1))
        self._jb_dn.clicked.connect(lambda: self._jog("Y", -1))
        self._jb_lt.clicked.connect(lambda: self._jog("X", -1))
        self._jb_rt.clicked.connect(lambda: self._jog("X", +1))
        self._jb_zup.clicked.connect(lambda: self._jog("Z", +1))
        self._jb_zdn.clicked.connect(lambda: self._jog("Z", -1))

        # --- Calibration steps ---
        cal_box = QGroupBox("Calibration Points")
        cv = QVBoxLayout(cal_box)

        cv.addWidget(QLabel("Step 1 — Jog หัวไปที่มุม TOP-LEFT ของบอร์ดจริง:"))
        self.p1_lbl = QLabel("  ยังไม่ได้กำหนด")
        self.p1_lbl.setStyleSheet("color: #888;")
        cv.addWidget(self.p1_lbl)
        self.set_p1_btn = QPushButton("📍  Set P1  (Top-Left)")
        self.set_p1_btn.setMinimumHeight(36)
        self.set_p1_btn.clicked.connect(self._set_p1)
        cv.addWidget(self.set_p1_btn)

        cv.addSpacing(6)

        cv.addWidget(QLabel("Step 2 — Jog หัวไปที่มุม BOTTOM-RIGHT ของบอร์ดจริง:"))
        self.p2_lbl = QLabel("  ยังไม่ได้กำหนด")
        self.p2_lbl.setStyleSheet("color: #888;")
        cv.addWidget(self.p2_lbl)
        self.set_p2_btn = QPushButton("📍  Set P2  (Bottom-Right)")
        self.set_p2_btn.setMinimumHeight(36)
        self.set_p2_btn.clicked.connect(self._set_p2)
        cv.addWidget(self.set_p2_btn)

        rv.addWidget(cal_box)

        self.scale_lbl = QLabel("")
        self.scale_lbl.setWordWrap(True)
        self.scale_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        rv.addWidget(self.scale_lbl)

        rv.addStretch(1)

        self.confirm_btn = QPushButton("✔  Confirm & Import Waypoints")
        self.confirm_btn.setMinimumHeight(42)
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self.accept)
        rv.addWidget(self.confirm_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(32)
        cancel_btn.clicked.connect(self.reject)
        rv.addWidget(cancel_btn)

        main.addWidget(right_w)

    # --------------------------------------------------------------- slots --

    def _on_side_changed(self, text: str):
        self._side = text
        self.canvas.side = text
        self.canvas.update()

    def _refresh_pos(self):
        wpos = self.worker.last_wpos()
        if wpos:
            x, y, z = wpos
            self.pos_lbl.setText(f"X: {x:9.3f}   Y: {y:9.3f}   Z: {z:9.3f}")

    def _jog(self, axis: str, sign: int):
        step = float(self.jog_step.currentText())
        feed = self.jog_feed.value()
        delta = sign * step
        self.worker.send_line(f"$J=G91 {axis}{delta:.3f} F{feed}")

    def _set_p1(self):
        wpos = self.worker.last_wpos()
        if not wpos:
            QMessageBox.warning(self, "Error", "ยังไม่ได้รับ position จากเครื่อง\nตรวจสอบการเชื่อมต่อ")
            return
        x, y, _ = wpos
        self.p1_machine = (x, y)
        self.p1_lbl.setText(f"  ✔  X{x:.3f}   Y{y:.3f}")
        self.p1_lbl.setStyleSheet("color: #00aaff; font-weight: bold;")
        self.canvas.p1_set = True
        self.canvas.update()
        self._check_ready()

    def _set_p2(self):
        wpos = self.worker.last_wpos()
        if not wpos:
            QMessageBox.warning(self, "Error", "ยังไม่ได้รับ position จากเครื่อง\nตรวจสอบการเชื่อมต่อ")
            return
        x, y, _ = wpos
        self.p2_machine = (x, y)
        self.p2_lbl.setText(f"  ✔  X{x:.3f}   Y{y:.3f}")
        self.p2_lbl.setStyleSheet("color: #ff8800; font-weight: bold;")
        self.canvas.p2_set = True
        self.canvas.update()
        self._check_ready()

    def _check_ready(self):
        if not (self.p1_machine and self.p2_machine):
            return
        dx = self.p2_machine[0] - self.p1_machine[0]
        dy = self.p2_machine[1] - self.p1_machine[1]
        mach_dist = math.sqrt(dx * dx + dy * dy)
        board_diag = math.sqrt(
            (self.csv_xmax - self.csv_xmin) ** 2 +
            (self.csv_ymax - self.csv_ymin) ** 2
        )
        scale = mach_dist / board_diag if board_diag > 0 else 0.0
        self.scale_lbl.setText(
            f"Machine distance P1→P2 : {mach_dist:.2f} mm\n"
            f"Board diagonal (CSV)   : {board_diag:.2f} mm\n"
            f"Scale factor           : {scale:.4f}x"
        )
        self.confirm_btn.setEnabled(True)

    # --------------------------------------------------------------- output --

    def get_waypoints(self, default_feed: int = 1200, default_time: float = 0.5):
        """
        Apply 2-point affine transform (rotation + uniform scale) to every
        component centre and return a list of Point waypoints.
        """
        if not (self.p1_machine and self.p2_machine):
            return []

        mx1, my1 = self.p1_machine
        mx2, my2 = self.p2_machine

        # CSV reference corners depend on side
        # top  : physical P1 = top-left  → CSV (xmin, ymax)
        #         physical P2 = bot-right → CSV (xmax, ymin)
        # bottom (board flipped around Y-axis):
        #         physical P1 = top-left  → CSV (xmax, ymax)
        #         physical P2 = bot-right → CSV (xmin, ymin)
        if self._side == "bottom":
            csv_p1x, csv_p1y = self.csv_xmax, self.csv_ymax
            csv_p2x, csv_p2y = self.csv_xmin, self.csv_ymin
        else:
            csv_p1x, csv_p1y = self.csv_xmin, self.csv_ymax
            csv_p2x, csv_p2y = self.csv_xmax, self.csv_ymin

        # Direction vectors
        dcx = csv_p2x - csv_p1x
        dcy = csv_p2y - csv_p1y
        dmx = mx2 - mx1
        dmy = my2 - my1

        csv_len  = math.sqrt(dcx * dcx + dcy * dcy)
        mach_len = math.sqrt(dmx * dmx + dmy * dmy)

        if csv_len == 0 or mach_len == 0:
            return []

        scale = mach_len / csv_len
        rot   = math.atan2(dmy, dmx) - math.atan2(dcy, dcx)
        cos_r = math.cos(rot) * scale
        sin_r = math.sin(rot) * scale

        points = []
        for comp in self.components:
            lx = comp.pos_x - csv_p1x
            ly = comp.pos_y - csv_p1y
            rx = lx * cos_r - ly * sin_r
            ry = lx * sin_r + ly * cos_r
            points.append(Point(
                name=comp.ref,
                x=round(mx1 + rx, 3),
                y=round(my1 + ry, 3),
                z=0.0,
                feed_to_next=default_feed,
                laser_time_s=default_time,
            ))

        return points

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)
