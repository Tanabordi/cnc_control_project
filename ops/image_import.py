"""Image import dialog — edge-trace PNG / JPG files into CNC waypoints."""

import math
from pathlib import Path
from typing import List, Tuple, Optional

import cv2
import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QGroupBox, QWidget,
    QDoubleSpinBox, QSpinBox, QSlider,
    QFileDialog, QMessageBox, QSizePolicy,
    QCheckBox, QComboBox
)

from core.models import Point
from core.transform import (
    compute_bounding_box, center_shift_polylines,
    compute_affine_2point, apply_affine_to_polylines,
)


# ---------------------------------------------------------------------------
# OpenCV Edge Tracing
# ---------------------------------------------------------------------------

def _trace_edges(
    img_bgr: np.ndarray,
    thresh1: int,
    thresh2: int,
    blur_k: int = 5,
    invert: bool = False
) -> Tuple[np.ndarray, List[List[Tuple[float, float]]]]:
    """
    Run Canny edge detection and find continuous contours.

    Returns:
        edge_map: 8-bit single-channel image of the edges (for preview).
        polylines: List of paths. Each path is a list of (x,y) pixel coordinates.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    if invert:
        gray = cv2.bitwise_not(gray)

    if blur_k > 0:
        k = max(1, blur_k)
        if k % 2 == 0:
            k += 1
        gray = cv2.GaussianBlur(gray, (k, k), 0)

    edges = cv2.Canny(gray, thresh1, thresh2)

    # findContours returns a list of arrays: shape (N, 1, 2)
    contours, _ = cv2.findContours(
        edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_TC89_L1
    )

    polylines = []
    for cnt in contours:
        if len(cnt) < 2:
            continue
        poly = []
        for pt in cnt:
            x, y = pt[0]
            poly.append((float(x), float(y)))
        polylines.append(poly)

    return edges, polylines


# ---------------------------------------------------------------------------
# Preview canvas
# ---------------------------------------------------------------------------

class ImagePreviewCanvas(QWidget):
    """Shows the original image superimposed with the detected edge polylines."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 320)
        self._margin = 16

        self._pixmap = QPixmap()
        self._polylines: List[List[Tuple[float, float]]] = []
        self._img_w = 0
        self._img_h = 0

    def set_image(self, bgr_array: np.ndarray):
        h, w, c = bgr_array.shape
        self._img_w = w
        self._img_h = h
        rgb = cv2.cvtColor(bgr_array, cv2.COLOR_BGR2RGB)
        bytes_per_line = 3 * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg)
        self.update()

    def set_polylines(self, polylines: List[List[Tuple[float, float]]]):
        self._polylines = polylines
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(24, 24, 30))

        if self._pixmap.isNull():
            painter.setPen(QColor(120, 120, 140))
            painter.drawText(self.rect(), Qt.AlignCenter, "No image loaded")
            painter.end()
            return

        avail_w = self.width() - 2 * self._margin
        avail_h = self.height() - 2 * self._margin
        scale = min(avail_w / self._img_w, avail_h / self._img_h)
        ox = self._margin + (avail_w - self._img_w * scale) / 2
        oy = self._margin + (avail_h - self._img_h * scale) / 2

        # Dim the background image so edges pop
        painter.setOpacity(0.3)
        dst_rect = self.rect().adjusted(int(ox), int(oy), -int(ox), -int(oy))
        # Keep aspect ratio
        scaled_pix = self._pixmap.scaled(
            int(self._img_w * scale),
            int(self._img_h * scale),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        painter.drawPixmap(int(ox), int(oy), scaled_pix)
        painter.setOpacity(1.0)

        # Draw polylines
        painter.setRenderHint(QPainter.Antialiasing)
        n_poly = len(self._polylines)

        def to_canvas(px, py):
            return int(ox + px * scale), int(oy + py * scale)

        for idx, poly in enumerate(self._polylines):
            hue = int(120 + 240 * idx / max(n_poly, 1)) % 360
            color = QColor.fromHsl(hue, 240, 150)
            painter.setPen(QPen(color, 1.5))
            for i in range(len(poly) - 1):
                x1, y1 = to_canvas(*poly[i])
                x2, y2 = to_canvas(*poly[i + 1])
                painter.drawLine(x1, y1, x2, y2)

        # Info
        painter.setPen(QColor(160, 170, 200))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(
            self._margin, self._margin - 4,
            f"Image: {self._img_w}x{self._img_h} px  |  "
            f"Paths: {n_poly}"
        )
        painter.end()


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------

class ImageImportDialog(QDialog):
    """
    Dialog for importing PNG / JPG images via Canny edge detection
    and converting the detected contours into CNC waypoints.

    The user selects an image, adjusts edge detection parameters,
    sets the physical target width, and the dialog generates ``Point``
    objects where:
    - Travel between contours uses ``power=0`` at ``z_safe``
    - Cutting along contour edges uses ``power=255`` at ``z_surface``
    
    Supports:
      - Job Origin selection (Bottom-Left or Center)
      - Material Calibration via 2-point affine transform
    """

    def __init__(self, worker=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Image — Edge Tracing")
        self.setModal(True)
        self.setMinimumSize(800, 600)

        self._filepath: Optional[str] = None
        self._img_bgr: Optional[np.ndarray] = None
        self._edge_map: Optional[np.ndarray] = None
        self._polylines: List[List[Tuple[float, float]]] = []
        
        self._worker = worker
        self._calib_machine_p1: Optional[Tuple[float, float]] = None
        self._calib_machine_p2: Optional[Tuple[float, float]] = None

        self._build_ui()

    # ------------------------------------------------------------------ UI --

    def _build_ui(self):
        main = QHBoxLayout(self)
        main.setSpacing(10)

        # ===== Left: preview canvas =====
        left_w = QWidget()
        lv = QVBoxLayout(left_w)
        lv.setContentsMargins(0, 0, 0, 0)

        self.canvas = ImagePreviewCanvas()
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lv.addWidget(self.canvas, 1)

        self.info_lbl = QLabel("Select an image to trace")
        self.info_lbl.setAlignment(Qt.AlignCenter)
        self.info_lbl.setStyleSheet("color: #888; font-size: 11px;")
        lv.addWidget(self.info_lbl)

        main.addWidget(left_w, 1)

        # ===== Right: controls =====
        right_w = QWidget()
        right_w.setMinimumWidth(320)
        rv = QVBoxLayout(right_w)
        rv.setSpacing(8)

        # --- File selection ---
        file_box = QGroupBox("Image File")
        fv = QVBoxLayout(file_box)
        self.file_lbl = QLabel("No file selected")
        self.file_lbl.setWordWrap(True)
        self.file_lbl.setStyleSheet("color: #aaa;")
        fv.addWidget(self.file_lbl)
        self.browse_btn = QPushButton("📂  Browse Image…")
        self.browse_btn.setMinimumHeight(36)
        self.browse_btn.clicked.connect(self._browse_file)
        fv.addWidget(self.browse_btn)
        rv.addWidget(file_box)

        # --- Canny Settings ---
        edge_box = QGroupBox("Edge Detection Tuning")
        ev = QVBoxLayout(edge_box)

        t1_layout = QHBoxLayout()
        t1_layout.addWidget(QLabel("Canny T1:"))
        self.t1_slider = QSlider(Qt.Horizontal)
        self.t1_slider.setRange(0, 500)
        self.t1_slider.setValue(100)
        self.t1_slider.valueChanged.connect(self._recalc_edges)
        t1_layout.addWidget(self.t1_slider)
        ev.addLayout(t1_layout)

        t2_layout = QHBoxLayout()
        t2_layout.addWidget(QLabel("Canny T2:"))
        self.t2_slider = QSlider(Qt.Horizontal)
        self.t2_slider.setRange(0, 500)
        self.t2_slider.setValue(200)
        self.t2_slider.valueChanged.connect(self._recalc_edges)
        t2_layout.addWidget(self.t2_slider)
        ev.addLayout(t2_layout)

        self.invert_cb = QCheckBox("Invert Colors before trace")
        self.invert_cb.stateChanged.connect(self._recalc_edges)
        ev.addWidget(self.invert_cb)

        rv.addWidget(edge_box)

        # --- Physical Parameters ---
        param_box = QGroupBox("Physical Export Parameters")
        pf = QFormLayout(param_box)

        self.target_width_spin = QDoubleSpinBox()
        self.target_width_spin.setRange(1.0, 5000.0)
        self.target_width_spin.setDecimals(1)
        self.target_width_spin.setValue(100.0)
        self.target_width_spin.setSuffix(" mm")
        self.target_width_spin.setToolTip(
            "Width of the image in real-world machine space.\n"
            "The height will be scaled proportionally."
        )
        pf.addRow("Target Width:", self.target_width_spin)

        # --- Job Origin selector ---
        self.origin_combo = QComboBox()
        self.origin_combo.addItems(["Bottom-Left (Default)", "Center of Bounding Box"])
        self.origin_combo.setToolTip(
            "Bottom-Left: coordinates start from the bottom-left corner.\n"
            "Center: the machine's current position = design center."
        )
        pf.addRow("Job Origin:", self.origin_combo)

        self.z_surface_spin = QDoubleSpinBox()
        self.z_surface_spin.setRange(-9999.0, 9999.0)
        self.z_surface_spin.setDecimals(3)
        self.z_surface_spin.setValue(0.0)
        self.z_surface_spin.setSuffix(" mm")
        pf.addRow("Z-Surface Depth:", self.z_surface_spin)

        self.z_safe_spin = QDoubleSpinBox()
        self.z_safe_spin.setRange(-9999.0, 9999.0)
        self.z_safe_spin.setDecimals(3)
        self.z_safe_spin.setValue(-2.0)
        self.z_safe_spin.setSuffix(" mm")
        pf.addRow("Z-Safe Height:", self.z_safe_spin)

        self.feed_spin = QSpinBox()
        self.feed_spin.setRange(1, 50000)
        self.feed_spin.setValue(1500)
        self.feed_spin.setSuffix(" mm/min")
        pf.addRow("Feed Rate:", self.feed_spin)

        rv.addWidget(param_box)

        # --- Status ---
        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        rv.addWidget(self.status_lbl)
        
        # --- Calibration status ---
        self.calib_status_lbl = QLabel("")
        self.calib_status_lbl.setWordWrap(True)
        self.calib_status_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        rv.addWidget(self.calib_status_lbl)

        rv.addStretch(1)

        # --- Calibrate Material button (optional) ---
        self.calibrate_btn = QPushButton("🔧  Calibrate Material (Optional)")
        self.calibrate_btn.setMinimumHeight(36)
        self.calibrate_btn.setEnabled(False)
        self.calibrate_btn.setToolTip(
            "Open the 2-Point Calibration dialog to compensate\n"
            "for crooked material placement on the CNC bed."
        )
        self.calibrate_btn.clicked.connect(self._open_calibration)
        rv.addWidget(self.calibrate_btn)

        # --- Buttons ---
        self.confirm_btn = QPushButton("✔  Import Waypoints")
        self.confirm_btn.setMinimumHeight(42)
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self.accept)
        rv.addWidget(self.confirm_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(32)
        cancel_btn.clicked.connect(self.reject)
        rv.addWidget(cancel_btn)

        from PySide6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(340)
        scroll.setWidget(right_w)
        main.addWidget(scroll)

    # --------------------------------------------------------------- slots --

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*)",
        )
        if not path:
            return

        img = cv2.imread(path)
        if img is None:
            QMessageBox.critical(self, "Error", f"Failed to open image:\n{path}")
            return

        self._filepath = path
        self._img_bgr = img
        self.file_lbl.setText(Path(path).name)
        self.file_lbl.setStyleSheet("color: #8ecfff; font-weight: bold;")
        self.canvas.set_image(img)

        self._calib_machine_p1 = None
        self._calib_machine_p2 = None
        self.calib_status_lbl.setText("")

        self._recalc_edges()

    def _recalc_edges(self):
        if self._img_bgr is None:
            return

        t1 = self.t1_slider.value()
        t2 = self.t2_slider.value()
        inv = self.invert_cb.isChecked()

        edges, polys = _trace_edges(self._img_bgr, t1, t2, invert=inv)
        self._edge_map = edges
        self._polylines = polys

        self.canvas.set_polylines(polys)

        n_pts = sum(len(p) for p in polys)
        if not polys:
            self.status_lbl.setText("⚠  No edges found. Adjust Canny sliders.")
            self.status_lbl.setStyleSheet("color: #ffaa44; font-size: 11px;")
            self.confirm_btn.setEnabled(False)
            self.calibrate_btn.setEnabled(False)
        else:
            self.status_lbl.setText(f"✔  Found {len(polys)} path(s), {n_pts} vertices.")
            self.status_lbl.setStyleSheet("color: #88ff88; font-size: 11px;")
            self.confirm_btn.setEnabled(True)
            self.calibrate_btn.setEnabled(self._worker is not None)

    def _get_working_polylines(self) -> List[List[Tuple[float, float]]]:
        """Convert raw pixels into scaled (mm), Y-flipped, and optionally center-shifted coords."""
        if not self._polylines:
            return []

        # 1. Bounding box in raw pixel space to determine scale
        px_xmin, px_ymin, px_xmax, px_ymax = compute_bounding_box(self._polylines)
        px_width = (px_xmax - px_xmin) or 1.0

        target_width = self.target_width_spin.value()
        scale = target_width / px_width  # px -> mm

        # 2. Convert to mm space and flip Y (so Y-up = positive)
        # We anchor (px_xmin, px_ymax) to (0,0) so the image sits in the top-right quadrant
        scaled_polylines = []
        for poly in self._polylines:
            scaled_poly = []
            for px, py in poly:
                mm_x = (px - px_xmin) * scale
                mm_y = (px_ymax - py) * scale  # flip Y
                scaled_poly.append((mm_x, mm_y))
            scaled_polylines.append(scaled_poly)

        # 3. Shift origin if requested
        if self.origin_combo.currentIndex() == 1:  # Center
            return center_shift_polylines(scaled_polylines)
        
        return scaled_polylines

    def _open_calibration(self):
        """Open the 2-Point Calibration dialog."""
        if not self._polylines:
            QMessageBox.warning(self, "No Data", "Load an image first.")
            return
        if self._worker is None:
            QMessageBox.warning(
                self, "Not Connected",
                "Machine is not connected.\n"
                "Connect to the CNC first to use calibration."
            )
            return

        working_polylines = self._get_working_polylines()
        xmin, ymin, xmax, ymax = compute_bounding_box(working_polylines)
        
        design_p1 = (xmin, ymin)
        design_p2 = (xmax, ymax)

        from ops.calibration_dialog import TwoPointCalibDialog
        dlg = TwoPointCalibDialog(design_p1, design_p2, self._worker, self)
        if dlg.exec() != QDialog.Accepted:
            return

        calib = dlg.get_calibration()
        if calib:
            self._calib_machine_p1, self._calib_machine_p2 = calib
            import math as _math
            result = compute_affine_2point(
                design_p1, design_p2,
                self._calib_machine_p1, self._calib_machine_p2,
            )
            if result:
                angle_deg = _math.degrees(result.rotation)
                self.calib_status_lbl.setText(
                    f"✔  Calibration set — "
                    f"Rotation: {angle_deg:.2f}°  Scale: {result.scale:.4f}x"
                )
                self.calib_status_lbl.setStyleSheet(
                    "color: #88ff88; font-size: 11px;"
                )

    # --------------------------------------------------------------- output --

    def get_waypoints(self) -> List[Point]:
        """
        Convert the image contours into a flat list of CNC ``Point`` objects.

        **Transform order:**
        1. Calculate pixel bounding box and scaling factor
        2. Convert to mm and flip Y to match CNC coords
        3. If "Center" origin, shift so center → (0, 0)
        4. If calibration was performed, apply rotation + translation
        """
        if not self._polylines:
            return []

        z_surface = self.z_surface_spin.value()
        z_safe = self.z_safe_spin.value()
        feed = self.feed_spin.value()

        # Step 1, 2, 3: Scale (and flip Y) and optional Center Shift
        working_polylines = self._get_working_polylines()

        # Step 4: Apply affine transform if calibration was set
        if self._calib_machine_p1 and self._calib_machine_p2:
            xmin, ymin, xmax, ymax = compute_bounding_box(working_polylines)
            design_p1 = (xmin, ymin)
            design_p2 = (xmax, ymax)

            result = compute_affine_2point(
                design_p1, design_p2,
                self._calib_machine_p1, self._calib_machine_p2,
            )
            if result:
                working_polylines = apply_affine_to_polylines(
                    working_polylines,
                    anchor=design_p1,
                    cos_r=result.cos_r,
                    sin_r=result.sin_r,
                    translation=self._calib_machine_p1,
                )

        # --- Generate Point objects ---
        points: List[Point] = []
        wp_idx = 1

        for poly_idx, poly in enumerate(working_polylines):
            # Remove duplicate consecutive vertices
            cleaned: List[Tuple[float, float]] = [poly[0]]
            for pt in poly[1:]:
                if pt != cleaned[-1]:
                    cleaned.append(pt)

            if len(cleaned) < 2:
                continue

            for vert_idx, (vx, vy) in enumerate(cleaned):
                if vert_idx == 0:
                    # Rapid move to start of contour (power 0, z_safe)
                    points.append(Point(
                        name=f"C{wp_idx}",
                        x=round(vx, 3),
                        y=round(vy, 3),
                        z=round(z_safe, 3),
                        feed_to_next=feed,
                        z_safe=z_safe,
                        power=0
                    ))
                    wp_idx += 1
                
                # Plunge / cut move (power 255, z_surface)
                points.append(Point(
                    name=f"C{wp_idx}",
                    x=round(vx, 3),
                    y=round(vy, 3),
                    z=round(z_surface, 3),
                    feed_to_next=feed,
                    z_safe=z_safe,
                    power=255
                ))
                wp_idx += 1

        return points
