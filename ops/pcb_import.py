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
    QDoubleSpinBox,
)

from core.models import Point


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
        self.p1_csv_pos = None   # (x, y) in CSV space — selected reference component
        self.p2_csv_pos = None   # (x, y) in CSV space — selected reference component
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

        # P1 reference component marker
        if self.p1_csv_pos:
            p1x, p1y = self._to_canvas(*self.p1_csv_pos)
            c1 = QColor(0, 170, 255) if self.p1_set else QColor(70, 110, 150)
            painter.setPen(QPen(c1, 2))
            painter.setBrush(QBrush(c1))
            painter.drawEllipse(int(p1x - 9), int(p1y - 9), 18, 18)
            painter.setPen(Qt.white)
            painter.setFont(QFont("Arial", 8, QFont.Bold))
            painter.drawText(int(p1x - 5), int(p1y + 4), "P1")

        # P2 reference component marker
        if self.p2_csv_pos:
            p2x, p2y = self._to_canvas(*self.p2_csv_pos)
            c2 = QColor(255, 120, 0) if self.p2_set else QColor(150, 100, 60)
            painter.setPen(QPen(c2, 2))
            painter.setBrush(QBrush(c2))
            painter.drawEllipse(int(p2x - 9), int(p2y - 9), 18, 18)
            painter.setPen(Qt.white)
            painter.setFont(QFont("Arial", 8, QFont.Bold))
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
    User selects 2 reference components, jogs to each on the real board,
    and the affine transform is computed from those known positions.
    """

    def __init__(self, components, has_side: bool, worker, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import PCB CSV — Calibration")
        self.setModal(True)
        self.resize(1050, 720)

        self.components = components
        self.worker = worker
        self.p1_machine = None   # (x, y) or None
        self.p2_machine = None   # (x, y) or None
        self.z_surface = None    # float or None

        # Determine initial side from CSV
        if has_side:
            sides = set(c.side for c in components)
            self._side = "bottom" if "bottom" in sides else "top"
        else:
            self._side = "top"

        self._build_ui(has_side)

        # Initialize canvas markers from default combo selections
        self._on_p1_comp_changed(0)
        self._on_p2_comp_changed(self.p2_comp_combo.count() - 1)

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

        xs = [c.pos_x for c in self.components]
        ys = [c.pos_y for c in self.components]
        board_w = round(max(xs) - min(xs), 2)
        board_h = round(max(ys) - min(ys), 2)
        info_lbl = QLabel(
            f"PCB Preview  —  {len(self.components)} components  |  "
            f"Board: {board_w} × {board_h} mm"
        )
        info_lbl.setAlignment(Qt.AlignCenter)
        lv.addWidget(info_lbl)

        self.canvas = PcbCanvas(self.components, self._side)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lv.addWidget(self.canvas, 1)

        # Legend
        legend = QHBoxLayout()
        dot_p1 = QLabel("●")
        dot_p1.setStyleSheet("color: #00aaff; font-size: 14px;")
        legend.addWidget(dot_p1)
        legend.addWidget(QLabel("P1 = component อ้างอิงจุดที่ 1"))
        legend.addSpacing(20)
        dot_p2 = QLabel("●")
        dot_p2.setStyleSheet("color: #ff7700; font-size: 14px;")
        legend.addWidget(dot_p2)
        legend.addWidget(QLabel("P2 = component อ้างอิงจุดที่ 2"))
        legend.addStretch(1)
        lv.addLayout(legend)

        main.addWidget(left_w, 1)

        # ===== Right: controls (fixed width) =====
        right_w = QWidget()
        right_w.setFixedWidth(370)
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
        self.jog_step.addItems(["0.1", "1", "10", "Custom..."])
        self.jog_step.setCurrentText("1")
        self.jog_step.currentTextChanged.connect(self._on_step_changed)
        step_row.addWidget(self.jog_step)
        self.jog_step_custom = QDoubleSpinBox()
        self.jog_step_custom.setRange(0.001, 9999.0)
        self.jog_step_custom.setDecimals(3)
        self.jog_step_custom.setValue(5.0)
        self.jog_step_custom.setVisible(False)
        step_row.addWidget(self.jog_step_custom)
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

        # Step 1
        cv.addWidget(QLabel("Step 1 — เลือก component อ้างอิง P1:"))
        self.p1_comp_combo = QComboBox()
        for c in self.components:
            self.p1_comp_combo.addItem(f"{c.ref}  ({c.pos_x:.2f}, {c.pos_y:.2f})", c)
        self.p1_comp_combo.currentIndexChanged.connect(self._on_p1_comp_changed)
        cv.addWidget(self.p1_comp_combo)
        cv.addWidget(QLabel("  Jog หัวไปแตะ component นั้น แล้วกด Set P1:"))
        self.p1_lbl = QLabel("  ยังไม่ได้กำหนด")
        self.p1_lbl.setStyleSheet("color: #888;")
        cv.addWidget(self.p1_lbl)
        self.set_p1_btn = QPushButton("📍  Set P1")
        self.set_p1_btn.setMinimumHeight(36)
        self.set_p1_btn.clicked.connect(self._set_p1)
        cv.addWidget(self.set_p1_btn)

        cv.addSpacing(6)

        # Step 2
        cv.addWidget(QLabel("Step 2 — เลือก component อ้างอิง P2:"))
        self.p2_comp_combo = QComboBox()
        for c in self.components:
            self.p2_comp_combo.addItem(f"{c.ref}  ({c.pos_x:.2f}, {c.pos_y:.2f})", c)
        self.p2_comp_combo.setCurrentIndex(len(self.components) - 1)
        self.p2_comp_combo.currentIndexChanged.connect(self._on_p2_comp_changed)
        cv.addWidget(self.p2_comp_combo)
        cv.addWidget(QLabel("  Jog หัวไปแตะ component นั้น แล้วกด Set P2:"))
        self.p2_lbl = QLabel("  ยังไม่ได้กำหนด")
        self.p2_lbl.setStyleSheet("color: #888;")
        cv.addWidget(self.p2_lbl)
        self.set_p2_btn = QPushButton("📍  Set P2")
        self.set_p2_btn.setMinimumHeight(36)
        self.set_p2_btn.clicked.connect(self._set_p2)
        cv.addWidget(self.set_p2_btn)

        cv.addSpacing(6)

        # Step 3
        cv.addWidget(QLabel("Step 3 — Jog Z ลงแตะผิวชิ้นงาน แล้วกด Set Z:"))
        self.z_lbl = QLabel("  ยังไม่ได้กำหนด")
        self.z_lbl.setStyleSheet("color: #888;")
        cv.addWidget(self.z_lbl)
        self.set_z_btn = QPushButton("📍  Set Z  (Surface)")
        self.set_z_btn.setMinimumHeight(36)
        self.set_z_btn.clicked.connect(self._set_z_surface)
        cv.addWidget(self.set_z_btn)

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

    def _on_p1_comp_changed(self, idx: int):
        comp = self.p1_comp_combo.itemData(idx)
        if comp:
            self.canvas.p1_csv_pos = (comp.pos_x, comp.pos_y)
            self.canvas.update()

    def _on_p2_comp_changed(self, idx: int):
        comp = self.p2_comp_combo.itemData(idx)
        if comp:
            self.canvas.p2_csv_pos = (comp.pos_x, comp.pos_y)
            self.canvas.update()

    def _refresh_pos(self):
        wpos = self.worker.last_wpos()
        if wpos:
            x, y, z = wpos
            self.pos_lbl.setText(f"X: {x:9.3f}   Y: {y:9.3f}   Z: {z:9.3f}")

    def _on_step_changed(self, text: str):
        self.jog_step_custom.setVisible(text == "Custom...")

    def _jog(self, axis: str, sign: int):
        if self.jog_step.currentText() == "Custom...":
            step = self.jog_step_custom.value()
        else:
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
        comp = self.p1_comp_combo.currentData()
        self.p1_lbl.setText(f"  ✔  {comp.ref} → X{x:.3f}  Y{y:.3f}")
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
        comp = self.p2_comp_combo.currentData()
        self.p2_lbl.setText(f"  ✔  {comp.ref} → X{x:.3f}  Y{y:.3f}")
        self.p2_lbl.setStyleSheet("color: #ff8800; font-weight: bold;")
        self.canvas.p2_set = True
        self.canvas.update()
        self._check_ready()

    def _set_z_surface(self):
        wpos = self.worker.last_wpos()
        if not wpos:
            QMessageBox.warning(self, "Error", "ยังไม่ได้รับ position จากเครื่อง\nตรวจสอบการเชื่อมต่อ")
            return
        _, _, z = wpos
        self.z_surface = z
        self.z_lbl.setText(f"  ✔  Z{z:.3f}")
        self.z_lbl.setStyleSheet("color: #88ff88; font-weight: bold;")
        self._check_ready()

    def _check_ready(self):
        if not (self.p1_machine and self.p2_machine and self.z_surface is not None):
            return
        p1_comp = self.p1_comp_combo.currentData()
        p2_comp = self.p2_comp_combo.currentData()
        dcx = p2_comp.pos_x - p1_comp.pos_x
        dcy = p2_comp.pos_y - p1_comp.pos_y
        csv_dist = math.sqrt(dcx * dcx + dcy * dcy)
        dx = self.p2_machine[0] - self.p1_machine[0]
        dy = self.p2_machine[1] - self.p1_machine[1]
        mach_dist = math.sqrt(dx * dx + dy * dy)
        scale = mach_dist / csv_dist if csv_dist > 0 else 0.0
        self.scale_lbl.setText(
            f"Machine distance P1→P2  : {mach_dist:.2f} mm\n"
            f"Component distance (CSV): {csv_dist:.2f} mm\n"
            f"Scale factor            : {scale:.4f}x"
        )
        self.confirm_btn.setEnabled(True)

    # --------------------------------------------------------------- output --

    def get_waypoints(self, default_feed: int = 1200, default_time: float = 0.5):
        """
        Apply 2-point affine transform (rotation + uniform scale) anchored to
        two user-selected reference components and return a list of Point waypoints.
        """
        if not (self.p1_machine and self.p2_machine):
            return []

        p1_comp = self.p1_comp_combo.currentData()
        p2_comp = self.p2_comp_combo.currentData()

        csv_p1x, csv_p1y = p1_comp.pos_x, p1_comp.pos_y
        csv_p2x, csv_p2y = p2_comp.pos_x, p2_comp.pos_y

        mx1, my1 = self.p1_machine
        mx2, my2 = self.p2_machine

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
                z=round(self.z_surface, 3),
                feed_to_next=default_feed,
                laser_time_s=default_time,
            ))

        return points

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Panel Export — Canvas + Dialog
# ---------------------------------------------------------------------------

class PanelCanvas(QWidget):
    """Canvas showing a grid of PCB copies with waypoints highlighted."""

    def __init__(self, points, parent=None):
        super().__init__(parent)
        self.points = points
        self.rows = 1
        self.cols = 1
        self.ref_idx = 0
        self.origin_set = False
        self.step_x_set = False
        self.step_y_set = False
        self.setMinimumSize(300, 300)
        self._margin = 24

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(30, 30, 35))

        if not self.points:
            painter.end()
            return

        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        pcb_w = (xmax - xmin) or 10.0
        pcb_h = (ymax - ymin) or 10.0

        gap_x = pcb_w * 0.10
        gap_y = pcb_h * 0.10
        total_w = self.cols * pcb_w + max(0, self.cols - 1) * gap_x
        total_h = self.rows * pcb_h + max(0, self.rows - 1) * gap_y

        avail_w = self.width() - 2 * self._margin
        avail_h = self.height() - 2 * self._margin
        if total_w <= 0 or total_h <= 0:
            painter.end()
            return

        scale = min(avail_w / total_w, avail_h / total_h)
        cell_w = pcb_w * scale
        cell_h = pcb_h * scale
        step_px_x = (pcb_w + gap_x) * scale
        step_px_y = (pcb_h + gap_y) * scale

        draw_w = total_w * scale
        draw_h = total_h * scale
        base_x = (self.width() - draw_w) / 2
        base_y = (self.height() - draw_h) / 2

        for r in range(self.rows):
            for c in range(self.cols):
                cx_px = int(base_x + c * step_px_x)
                cy_px = int(base_y + r * step_px_y)
                cw_px = int(cell_w)
                ch_px = int(cell_h)

                is_origin = (r == 0 and c == 0)
                is_sx = (r == 0 and c == 1)
                is_sy = (r == 1 and c == 0)

                if is_origin and self.origin_set:
                    border = QColor(100, 220, 100)
                    fill = QColor(30, 100, 30)
                elif is_sx and self.step_x_set:
                    border = QColor(80, 160, 255)
                    fill = QColor(20, 55, 100)
                elif is_sy and self.step_y_set:
                    border = QColor(255, 160, 60)
                    fill = QColor(80, 50, 15)
                else:
                    border = QColor(70, 140, 70)
                    fill = QColor(28, 80, 28)

                painter.setPen(QPen(border, 2))
                painter.setBrush(QBrush(fill))
                painter.drawRect(cx_px, cy_px, cw_px, ch_px)

                font_size = max(6, int(ch_px * 0.13))
                painter.setFont(QFont("Arial", font_size))
                painter.setPen(QColor(160, 200, 160))
                painter.drawText(cx_px + 4, cy_px + font_size + 3, f"[{r+1},{c+1}]")

                for i, p in enumerate(self.points):
                    dot_x = cx_px + int((p.x - xmin) / pcb_w * cw_px) if pcb_w else cx_px + cw_px // 2
                    dot_y = cy_px + int((1.0 - (p.y - ymin) / pcb_h) * ch_px) if pcb_h else cy_px + ch_px // 2

                    is_ref = (i == self.ref_idx)
                    rad = 7 if is_ref else 4
                    color = QColor(0, 200, 255) if is_ref else QColor(255, 200, 0, 200)
                    painter.setPen(QPen(color, 1))
                    painter.setBrush(QBrush(color))
                    painter.drawEllipse(int(dot_x - rad), int(dot_y - rad), rad * 2, rad * 2)

        painter.setPen(QColor(180, 180, 180))
        painter.setFont(QFont("Arial", 9))
        n = self.rows * self.cols
        painter.drawText(self._margin, self._margin - 6,
                         f"Panel Preview  —  {self.rows} × {self.cols} = {n} PCBs")
        painter.end()


class PanelExportDialog(QDialog):
    """
    Panel export calibration dialog.
    User jogs to the same reference waypoint on each PCB anchor position
    (origin, step-X, step-Y) so the exact panel offsets are measured.
    """

    def __init__(self, points, worker, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Panel G-code — Calibration")
        self.setModal(True)
        self.resize(1050, 720)

        self.points = points
        self.worker = worker
        self._origin = None       # (x, y) machine pos — ref on PCB [1,1]
        self._step_x_pos = None   # (x, y) machine pos — ref on PCB [1,2]
        self._step_y_pos = None   # (x, y) machine pos — ref on PCB [2,1]

        self._build_ui()
        self._update_steps_visibility()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_pos)
        self._timer.start(150)

    # ------------------------------------------------------------------ UI --

    def _build_ui(self):
        main = QHBoxLayout(self)
        main.setSpacing(10)

        # ===== Left: canvas =====
        left_w = QWidget()
        lv = QVBoxLayout(left_w)
        lv.setContentsMargins(0, 0, 0, 0)

        self.canvas = PanelCanvas(self.points)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lv.addWidget(self.canvas, 1)

        legend = QHBoxLayout()
        for color, text in [("#00c8ff", "Reference waypoint"), ("#ffcc00", "Other waypoints")]:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 14px;")
            legend.addWidget(dot)
            legend.addWidget(QLabel(text))
            legend.addSpacing(16)
        legend.addStretch(1)
        lv.addLayout(legend)

        main.addWidget(left_w, 1)

        # ===== Right: controls =====
        right_w = QWidget()
        right_w.setFixedWidth(390)
        rv = QVBoxLayout(right_w)
        rv.setSpacing(8)

        # --- Panel config ---
        cfg_box = QGroupBox("Panel Configuration")
        cfg_grid = QGridLayout(cfg_box)
        cfg_grid.addWidget(QLabel("Rows:"), 0, 0)
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 50)
        self.rows_spin.setValue(1)
        cfg_grid.addWidget(self.rows_spin, 0, 1)
        cfg_grid.addWidget(QLabel("Columns:"), 1, 0)
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 50)
        self.cols_spin.setValue(1)
        cfg_grid.addWidget(self.cols_spin, 1, 1)
        self.total_lbl = QLabel("Total: 1 PCB")
        cfg_grid.addWidget(self.total_lbl, 2, 0, 1, 2)
        rv.addWidget(cfg_box)
        self.rows_spin.valueChanged.connect(self._on_grid_changed)
        self.cols_spin.valueChanged.connect(self._on_grid_changed)

        # --- Reference waypoint ---
        ref_box = QGroupBox("Reference Waypoint")
        ref_v = QVBoxLayout(ref_box)
        ref_v.addWidget(QLabel("เลือก waypoint อ้างอิง:"))
        self.ref_combo = QComboBox()
        for p in self.points:
            self.ref_combo.addItem(f"{p.name}  (X{p.x:.3f}, Y{p.y:.3f})")
        self.ref_combo.currentIndexChanged.connect(self._on_ref_changed)
        ref_v.addWidget(self.ref_combo)
        rv.addWidget(ref_box)

        # --- Live position ---
        pos_box = QGroupBox("Machine Work Position")
        pv = QVBoxLayout(pos_box)
        self.pos_lbl = QLabel("X: -.---   Y: -.---   Z: -.---")
        self.pos_lbl.setAlignment(Qt.AlignCenter)
        self.pos_lbl.setStyleSheet(
            "font-size: 13px; font-weight: bold; font-family: monospace;")
        pv.addWidget(self.pos_lbl)
        rv.addWidget(pos_box)

        # --- Jog controls ---
        jog_box = QGroupBox("Jog — ขยับหัวเครื่อง")
        jv = QVBoxLayout(jog_box)
        grid = QGridLayout()
        grid.setSpacing(4)
        self._jb_up  = QPushButton("▲ Y+")
        self._jb_dn  = QPushButton("▼ Y−")
        self._jb_lt  = QPushButton("◀ X−")
        self._jb_rt  = QPushButton("▶ X+")
        self._jb_zup = QPushButton("Z+")
        self._jb_zdn = QPushButton("Z−")
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
        self.jog_step.addItems(["0.1", "1", "10", "Custom..."])
        self.jog_step.setCurrentText("1")
        self.jog_step.currentTextChanged.connect(self._on_step_changed)
        step_row.addWidget(self.jog_step)
        self.jog_step_custom = QDoubleSpinBox()
        self.jog_step_custom.setRange(0.001, 9999.0)
        self.jog_step_custom.setDecimals(3)
        self.jog_step_custom.setValue(5.0)
        self.jog_step_custom.setVisible(False)
        step_row.addWidget(self.jog_step_custom)
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

        # --- Set positions ---
        steps_box = QGroupBox("Set Panel Positions")
        sv = QVBoxLayout(steps_box)

        sv.addWidget(QLabel("Step 1 — Jog ไปที่ reference waypoint บน PCB [1,1] แล้วกด:"))
        self.origin_lbl = QLabel("  ยังไม่ได้กำหนด")
        self.origin_lbl.setStyleSheet("color: #888;")
        sv.addWidget(self.origin_lbl)
        self.set_origin_btn = QPushButton("📍  Set Origin  (PCB [1,1])")
        self.set_origin_btn.setMinimumHeight(36)
        self.set_origin_btn.clicked.connect(self._set_origin)
        sv.addWidget(self.set_origin_btn)

        sv.addSpacing(6)

        self._step_x_widget = QWidget()
        sx_v = QVBoxLayout(self._step_x_widget)
        sx_v.setContentsMargins(0, 0, 0, 0)
        sx_v.addWidget(QLabel("Step 2 — Jog ไปที่ reference waypoint บน PCB [1,2] แล้วกด:"))
        self.step_x_lbl = QLabel("  ยังไม่ได้กำหนด")
        self.step_x_lbl.setStyleSheet("color: #888;")
        sx_v.addWidget(self.step_x_lbl)
        self.set_step_x_btn = QPushButton("📍  Set Step X  (PCB [1,2])")
        self.set_step_x_btn.setMinimumHeight(36)
        self.set_step_x_btn.clicked.connect(self._set_step_x)
        sx_v.addWidget(self.set_step_x_btn)
        sv.addWidget(self._step_x_widget)

        sv.addSpacing(6)

        self._step_y_widget = QWidget()
        sy_v = QVBoxLayout(self._step_y_widget)
        sy_v.setContentsMargins(0, 0, 0, 0)
        sy_v.addWidget(QLabel("Step 3 — Jog ไปที่ reference waypoint บน PCB [2,1] แล้วกด:"))
        self.step_y_lbl = QLabel("  ยังไม่ได้กำหนด")
        self.step_y_lbl.setStyleSheet("color: #888;")
        sy_v.addWidget(self.step_y_lbl)
        self.set_step_y_btn = QPushButton("📍  Set Step Y  (PCB [2,1])")
        self.set_step_y_btn.setMinimumHeight(36)
        self.set_step_y_btn.clicked.connect(self._set_step_y)
        sy_v.addWidget(self.set_step_y_btn)
        sv.addWidget(self._step_y_widget)

        rv.addWidget(steps_box)

        self.info_lbl = QLabel("")
        self.info_lbl.setWordWrap(True)
        self.info_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        rv.addWidget(self.info_lbl)

        rv.addStretch(1)

        self.confirm_btn = QPushButton("✔  Confirm & Export Panel G-code")
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

    def _on_grid_changed(self):
        rows = self.rows_spin.value()
        cols = self.cols_spin.value()
        self.total_lbl.setText(f"Total: {rows * cols} PCBs")
        self.canvas.rows = rows
        self.canvas.cols = cols
        # Reset step measurements when grid size changes
        self._step_x_pos = None
        self._step_y_pos = None
        self.canvas.step_x_set = False
        self.canvas.step_y_set = False
        self.step_x_lbl.setText("  ยังไม่ได้กำหนด")
        self.step_x_lbl.setStyleSheet("color: #888;")
        self.step_y_lbl.setText("  ยังไม่ได้กำหนด")
        self.step_y_lbl.setStyleSheet("color: #888;")
        self.canvas.update()
        self._update_steps_visibility()
        self._check_ready()

    def _on_ref_changed(self, idx: int):
        self.canvas.ref_idx = idx
        self.canvas.update()

    def _update_steps_visibility(self):
        self._step_x_widget.setVisible(self.cols_spin.value() > 1)
        self._step_y_widget.setVisible(self.rows_spin.value() > 1)

    def _refresh_pos(self):
        wpos = self.worker.last_wpos()
        if wpos:
            x, y, z = wpos
            self.pos_lbl.setText(f"X: {x:9.3f}   Y: {y:9.3f}   Z: {z:9.3f}")

    def _on_step_changed(self, text: str):
        self.jog_step_custom.setVisible(text == "Custom...")

    def _jog(self, axis: str, sign: int):
        step = (self.jog_step_custom.value()
                if self.jog_step.currentText() == "Custom..."
                else float(self.jog_step.currentText()))
        self.worker.send_line(f"$J=G91 {axis}{sign * step:.3f} F{self.jog_feed.value()}")

    def _set_origin(self):
        wpos = self.worker.last_wpos()
        if not wpos:
            QMessageBox.warning(self, "Error", "ยังไม่ได้รับ position จากเครื่อง")
            return
        x, y, _ = wpos
        self._origin = (x, y)
        self.canvas.origin_set = True
        self.canvas.update()
        ref = self.points[self.ref_combo.currentIndex()]
        self.origin_lbl.setText(f"  ✔  {ref.name} → X{x:.3f}  Y{y:.3f}")
        self.origin_lbl.setStyleSheet("color: #64dc64; font-weight: bold;")
        self._update_info()
        self._check_ready()

    def _set_step_x(self):
        wpos = self.worker.last_wpos()
        if not wpos:
            QMessageBox.warning(self, "Error", "ยังไม่ได้รับ position จากเครื่อง")
            return
        x, y, _ = wpos
        self._step_x_pos = (x, y)
        self.canvas.step_x_set = True
        self.canvas.update()
        ref = self.points[self.ref_combo.currentIndex()]
        self.step_x_lbl.setText(f"  ✔  {ref.name} PCB[1,2] → X{x:.3f}  Y{y:.3f}")
        self.step_x_lbl.setStyleSheet("color: #50a0ff; font-weight: bold;")
        self._update_info()
        self._check_ready()

    def _set_step_y(self):
        wpos = self.worker.last_wpos()
        if not wpos:
            QMessageBox.warning(self, "Error", "ยังไม่ได้รับ position จากเครื่อง")
            return
        x, y, _ = wpos
        self._step_y_pos = (x, y)
        self.canvas.step_y_set = True
        self.canvas.update()
        ref = self.points[self.ref_combo.currentIndex()]
        self.step_y_lbl.setText(f"  ✔  {ref.name} PCB[2,1] → X{x:.3f}  Y{y:.3f}")
        self.step_y_lbl.setStyleSheet("color: #ffa030; font-weight: bold;")
        self._update_info()
        self._check_ready()

    def _update_info(self):
        import math
        lines = []
        if self._origin and self._step_x_pos:
            dx = self._step_x_pos[0] - self._origin[0]
            dy = self._step_x_pos[1] - self._origin[1]
            lines.append(f"Step X: ΔX={dx:.3f}  ΔY={dy:.3f}  |{math.hypot(dx, dy):.2f} mm|")
        if self._origin and self._step_y_pos:
            dx = self._step_y_pos[0] - self._origin[0]
            dy = self._step_y_pos[1] - self._origin[1]
            lines.append(f"Step Y: ΔX={dx:.3f}  ΔY={dy:.3f}  |{math.hypot(dx, dy):.2f} mm|")
        self.info_lbl.setText("\n".join(lines))

    def _check_ready(self):
        ok = self._origin is not None
        if self.cols_spin.value() > 1:
            ok = ok and (self._step_x_pos is not None)
        if self.rows_spin.value() > 1:
            ok = ok and (self._step_y_pos is not None)
        self.confirm_btn.setEnabled(ok)

    # --------------------------------------------------------------- output --

    def get_offsets(self):
        """Returns list of (row, col, offset_x, offset_y) for every PCB copy."""
        ref = self.points[self.ref_combo.currentIndex()]
        base_ox = self._origin[0] - ref.x
        base_oy = self._origin[1] - ref.y

        vec_x = (self._step_x_pos[0] - self._origin[0],
                 self._step_x_pos[1] - self._origin[1]) if self._step_x_pos else (0.0, 0.0)
        vec_y = (self._step_y_pos[0] - self._origin[0],
                 self._step_y_pos[1] - self._origin[1]) if self._step_y_pos else (0.0, 0.0)

        offsets = []
        for r in range(self.rows_spin.value()):
            for c in range(self.cols_spin.value()):
                offsets.append((r, c,
                                 base_ox + c * vec_x[0] + r * vec_y[0],
                                 base_oy + c * vec_x[1] + r * vec_y[1]))
        return offsets

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)
