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
    QCheckBox,
)

from core.models import Point


# ---------------------------------------------------------------------------
# Edge detection helpers
# ---------------------------------------------------------------------------

def detect_edges(
    img_bgr: np.ndarray,
    canny_lo: int = 50,
    canny_hi: int = 150,
    blur_k: int = 5,
    dilate_iter: int = 0,
) -> np.ndarray:
    """
    Convert a BGR image to a Canny edge map.

    Returns a single-channel uint8 image where edges are 255.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # Gaussian blur to suppress noise
    if blur_k > 0:
        k = blur_k | 1  # ensure odd
        gray = cv2.GaussianBlur(gray, (k, k), 0)

    edges = cv2.Canny(gray, canny_lo, canny_hi)

    # Optional dilation to thicken / close gaps
    if dilate_iter > 0:
        kernel = np.ones((3, 3), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=dilate_iter)

    return edges


def find_contour_polylines(
    edge_map: np.ndarray,
    min_length: int = 10,
    epsilon_factor: float = 0.002,
) -> List[List[Tuple[float, float]]]:
    """
    Find contours from a Canny edge map and return simplified polylines.

    Each polyline is a list of (x, y) pixel coordinates.
    Contours shorter than ``min_length`` pixels are discarded.

    ``epsilon_factor`` controls Douglas-Peucker simplification:
    lower = more detail, higher = fewer points.
    """
    contours, _ = cv2.findContours(
        edge_map, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
    )

    polylines: List[List[Tuple[float, float]]] = []

    for cnt in contours:
        # Skip tiny contours (noise)
        arc_len = cv2.arcLength(cnt, closed=False)
        if arc_len < min_length:
            continue

        # Douglas-Peucker simplification
        epsilon = epsilon_factor * arc_len
        approx = cv2.approxPolyDP(cnt, epsilon, closed=False)

        coords: List[Tuple[float, float]] = []
        for pt in approx:
            px, py = float(pt[0][0]), float(pt[0][1])
            coords.append((px, py))

        if len(coords) >= 2:
            polylines.append(coords)

    return polylines


# ---------------------------------------------------------------------------
# Preview canvas
# ---------------------------------------------------------------------------

def _cv_to_qimage(img_bgr: np.ndarray) -> QImage:
    """Convert an OpenCV BGR image to a QImage (RGB888)."""
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    bytes_per_line = ch * w
    return QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()


def _edge_to_qimage(edge_map: np.ndarray) -> QImage:
    """Convert a single-channel edge map to a QImage."""
    h, w = edge_map.shape
    return QImage(edge_map.data, w, h, w, QImage.Format_Grayscale8).copy()


class ImagePreviewCanvas(QWidget):
    """Side-by-side preview: original image (left) and edge overlay (right)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._original: Optional[QImage] = None
        self._edges: Optional[QImage] = None
        self._contour_img: Optional[QImage] = None
        self.setMinimumSize(400, 240)

    def set_images(
        self,
        original: Optional[np.ndarray],
        edge_map: Optional[np.ndarray],
        contours_vis: Optional[np.ndarray] = None,
    ):
        """Update the preview with new images."""
        self._original = _cv_to_qimage(original) if original is not None else None
        self._edges = _edge_to_qimage(edge_map) if edge_map is not None else None
        self._contour_img = (
            _cv_to_qimage(contours_vis) if contours_vis is not None else None
        )
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor(24, 24, 30))

        if self._original is None:
            painter.setPen(QColor(120, 120, 140))
            painter.setFont(QFont("Arial", 10))
            painter.drawText(self.rect(), Qt.AlignCenter, "No image loaded")
            painter.end()
            return

        # Split into two halves
        gap = 6
        half_w = (self.width() - gap) // 2
        full_h = self.height() - 28  # leave room for labels

        label_y = full_h + 18

        # --- Left: original ---
        if self._original:
            pix = QPixmap.fromImage(self._original)
            scaled = pix.scaled(half_w, full_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            ox = (half_w - scaled.width()) // 2
            oy = (full_h - scaled.height()) // 2
            painter.drawPixmap(ox, oy, scaled)

        painter.setPen(QColor(160, 170, 200))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(0, label_y, half_w, 16, Qt.AlignCenter, "Original")

        # --- Right: contour overlay or edge map ---
        right_x = half_w + gap
        right_img = self._contour_img if self._contour_img else self._edges
        if right_img:
            pix2 = QPixmap.fromImage(right_img)
            scaled2 = pix2.scaled(half_w, full_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            ox2 = right_x + (half_w - scaled2.width()) // 2
            oy2 = (full_h - scaled2.height()) // 2
            painter.drawPixmap(ox2, oy2, scaled2)

        painter.setPen(QColor(160, 170, 200))
        painter.drawText(right_x, label_y, half_w, 16, Qt.AlignCenter, "Detected Contours")

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
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Image — Edge Tracing")
        self.setModal(True)
        self.resize(1000, 660)

        self._filepath: Optional[str] = None
        self._img_bgr: Optional[np.ndarray] = None
        self._edge_map: Optional[np.ndarray] = None
        self._polylines: List[List[Tuple[float, float]]] = []

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

        self.info_lbl = QLabel("Select a .png or .jpg image to preview")
        self.info_lbl.setAlignment(Qt.AlignCenter)
        self.info_lbl.setStyleSheet("color: #888; font-size: 11px;")
        lv.addWidget(self.info_lbl)

        main.addWidget(left_w, 1)

        # ===== Right: controls =====
        right_w = QWidget()
        right_w.setFixedWidth(340)
        rv = QVBoxLayout(right_w)
        rv.setSpacing(8)

        # --- File selection ---
        file_box = QGroupBox("Image File")
        fv = QVBoxLayout(file_box)
        self.file_lbl = QLabel("No file selected")
        self.file_lbl.setWordWrap(True)
        self.file_lbl.setStyleSheet("color: #aaa;")
        fv.addWidget(self.file_lbl)
        self.browse_btn = QPushButton("📂  Browse…")
        self.browse_btn.setMinimumHeight(36)
        self.browse_btn.clicked.connect(self._browse_file)
        fv.addWidget(self.browse_btn)
        rv.addWidget(file_box)

        # --- Edge detection parameters ---
        edge_box = QGroupBox("Edge Detection (Canny)")
        ef = QFormLayout(edge_box)

        self.canny_lo_slider = QSlider(Qt.Horizontal)
        self.canny_lo_slider.setRange(1, 255)
        self.canny_lo_slider.setValue(50)
        self.canny_lo_lbl = QLabel("50")
        lo_row = QHBoxLayout()
        lo_row.addWidget(self.canny_lo_slider, 1)
        lo_row.addWidget(self.canny_lo_lbl)
        ef.addRow("Threshold Low:", lo_row)

        self.canny_hi_slider = QSlider(Qt.Horizontal)
        self.canny_hi_slider.setRange(1, 255)
        self.canny_hi_slider.setValue(150)
        self.canny_hi_lbl = QLabel("150")
        hi_row = QHBoxLayout()
        hi_row.addWidget(self.canny_hi_slider, 1)
        hi_row.addWidget(self.canny_hi_lbl)
        ef.addRow("Threshold High:", hi_row)

        self.blur_spin = QSpinBox()
        self.blur_spin.setRange(0, 31)
        self.blur_spin.setValue(5)
        self.blur_spin.setSingleStep(2)
        self.blur_spin.setToolTip("Gaussian blur kernel size (odd number, 0 = off).")
        ef.addRow("Blur Kernel:", self.blur_spin)

        self.dilate_spin = QSpinBox()
        self.dilate_spin.setRange(0, 10)
        self.dilate_spin.setValue(0)
        self.dilate_spin.setToolTip("Dilation iterations to thicken edges / close gaps.")
        ef.addRow("Dilate Iterations:", self.dilate_spin)

        self.min_length_spin = QSpinBox()
        self.min_length_spin.setRange(1, 10000)
        self.min_length_spin.setValue(20)
        self.min_length_spin.setToolTip("Minimum contour arc-length in pixels to keep.")
        ef.addRow("Min Contour Length:", self.min_length_spin)

        self.simplify_spin = QDoubleSpinBox()
        self.simplify_spin.setRange(0.0, 0.1)
        self.simplify_spin.setDecimals(4)
        self.simplify_spin.setValue(0.002)
        self.simplify_spin.setSingleStep(0.0005)
        self.simplify_spin.setToolTip(
            "Douglas-Peucker epsilon factor.\n"
            "Lower = more detail, higher = fewer points."
        )
        ef.addRow("Simplify Factor:", self.simplify_spin)

        self.invert_cb = QCheckBox("Invert edges")
        self.invert_cb.setToolTip("Invert the edge map before finding contours.")
        ef.addRow(self.invert_cb)

        self.redetect_btn = QPushButton("🔄  Re-detect Edges")
        self.redetect_btn.setMinimumHeight(32)
        self.redetect_btn.setEnabled(False)
        self.redetect_btn.clicked.connect(self._redetect)
        ef.addRow(self.redetect_btn)

        rv.addWidget(edge_box)

        # Connect sliders to live labels
        self.canny_lo_slider.valueChanged.connect(
            lambda v: self.canny_lo_lbl.setText(str(v))
        )
        self.canny_hi_slider.valueChanged.connect(
            lambda v: self.canny_hi_lbl.setText(str(v))
        )

        # --- Physical dimensions ---
        dim_box = QGroupBox("Physical Dimensions")
        df = QFormLayout(dim_box)

        self.target_width_spin = QDoubleSpinBox()
        self.target_width_spin.setRange(0.1, 99999.0)
        self.target_width_spin.setDecimals(2)
        self.target_width_spin.setValue(50.0)
        self.target_width_spin.setSuffix(" mm")
        self.target_width_spin.setToolTip(
            "How wide the final physical output should be.\n"
            "The pixel-to-mm scale is computed automatically\n"
            "from the contours' bounding box."
        )
        df.addRow("Target Width:", self.target_width_spin)

        self.z_surface_spin = QDoubleSpinBox()
        self.z_surface_spin.setRange(-9999.0, 9999.0)
        self.z_surface_spin.setDecimals(3)
        self.z_surface_spin.setValue(0.0)
        self.z_surface_spin.setSuffix(" mm")
        self.z_surface_spin.setToolTip("Z depth for engraving / cutting moves.")
        df.addRow("Z-Surface Depth:", self.z_surface_spin)

        self.z_safe_spin = QDoubleSpinBox()
        self.z_safe_spin.setRange(-9999.0, 9999.0)
        self.z_safe_spin.setDecimals(3)
        self.z_safe_spin.setValue(-2.0)
        self.z_safe_spin.setSuffix(" mm")
        self.z_safe_spin.setToolTip("Z height for rapid travel between contours.")
        df.addRow("Z-Safe:", self.z_safe_spin)

        self.feed_spin = QSpinBox()
        self.feed_spin.setRange(1, 50000)
        self.feed_spin.setValue(1000)
        self.feed_spin.setSuffix(" mm/min")
        self.feed_spin.setToolTip("Feed rate for cutting / engraving moves.")
        df.addRow("Feed Rate:", self.feed_spin)

        rv.addWidget(dim_box)

        # --- Status ---
        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        rv.addWidget(self.status_lbl)

        rv.addStretch(1)

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

        main.addWidget(right_w)

    # --------------------------------------------------------------- slots --

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image File",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.tiff);;All Files (*)",
        )
        if not path:
            return

        self._filepath = path
        self.file_lbl.setText(Path(path).name)
        self.file_lbl.setStyleSheet("color: #8ecfff; font-weight: bold;")

        self._load_image(path)

    def _load_image(self, path: str):
        """Load an image file and run edge detection."""
        img = cv2.imread(path)
        if img is None:
            QMessageBox.critical(
                self, "Load Error",
                f"Failed to load image:\n{path}"
            )
            return

        self._img_bgr = img
        self.redetect_btn.setEnabled(True)
        self._run_detection()

    def _redetect(self):
        """Re-run edge detection with updated parameters."""
        if self._img_bgr is None:
            return
        self._run_detection()

    def _run_detection(self):
        """Apply Canny edge detection and find contours."""
        img = self._img_bgr
        h, w = img.shape[:2]

        canny_lo = self.canny_lo_slider.value()
        canny_hi = self.canny_hi_slider.value()
        blur_k = self.blur_spin.value()
        dilate_iter = self.dilate_spin.value()
        min_length = self.min_length_spin.value()
        eps_factor = self.simplify_spin.value()

        # Edge detection
        self._edge_map = detect_edges(img, canny_lo, canny_hi, blur_k, dilate_iter)

        edge_for_contours = self._edge_map.copy()
        if self.invert_cb.isChecked():
            edge_for_contours = cv2.bitwise_not(edge_for_contours)

        # Find contours
        self._polylines = find_contour_polylines(
            edge_for_contours,
            min_length=min_length,
            epsilon_factor=eps_factor,
        )

        # Build contour visualisation on a dark background
        contour_vis = np.zeros((h, w, 3), dtype=np.uint8)
        contour_vis[:] = (24, 24, 30)  # dark background (BGR)

        n_poly = len(self._polylines)
        for idx, poly in enumerate(self._polylines):
            # Varying hue for each contour
            hue = int(120 + 140 * idx / max(n_poly, 1)) % 180
            color_hsv = np.uint8([[[hue, 220, 220]]])
            color_bgr = cv2.cvtColor(color_hsv, cv2.COLOR_HSV2BGR)[0][0]
            color = (int(color_bgr[0]), int(color_bgr[1]), int(color_bgr[2]))

            pts = np.array(poly, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(contour_vis, [pts], isClosed=False, color=color, thickness=1)

        # Update preview
        self.canvas.set_images(img, self._edge_map, contour_vis)

        if not self._polylines:
            self.status_lbl.setText(
                "⚠  No contours found. Try adjusting the Canny thresholds."
            )
            self.status_lbl.setStyleSheet("color: #ffaa44; font-size: 11px;")
            self.confirm_btn.setEnabled(False)
            return

        total_verts = sum(len(p) for p in self._polylines)
        self.confirm_btn.setEnabled(True)
        self.status_lbl.setText(
            f"✔  {len(self._polylines)} contour(s), "
            f"{total_verts} vertices total."
        )
        self.status_lbl.setStyleSheet("color: #88ff88; font-size: 11px;")

        # Update info label
        self.info_lbl.setText(
            f"{Path(self._filepath).name}  —  "
            f"{w} × {h} px  |  "
            f"{len(self._polylines)} contours detected"
        )
        self.info_lbl.setStyleSheet("color: #bbc; font-size: 11px;")

    # --------------------------------------------------------------- output --

    def get_waypoints(self) -> List[Point]:
        """
        Convert the detected contour polylines into a flat list of ``Point``
        objects using the current UI parameter values.

        Behaviour:
        - **Along a contour**: each vertex becomes a waypoint at ``z_surface``
          with ``power=255`` (laser on / tool engaged).
        - **Between contours**: a *travel* waypoint is inserted for the first
          point of each new contour with ``power=0`` and ``z=z_safe`` so the
          tool lifts before rapid-traveling to the next shape.
        """
        if not self._polylines:
            return []

        # --- Compute pixel → mm scale from the contours' bounding box ---
        all_x = [pt[0] for poly in self._polylines for pt in poly]
        all_y = [pt[1] for poly in self._polylines for pt in poly]
        px_xmin, px_xmax = min(all_x), max(all_x)
        px_ymin, px_ymax = min(all_y), max(all_y)
        px_width = (px_xmax - px_xmin) or 1.0

        target_width = self.target_width_spin.value()
        scale = target_width / px_width  # px → mm

        z_surface = self.z_surface_spin.value()
        z_safe = self.z_safe_spin.value()
        feed = self.feed_spin.value()

        points: List[Point] = []
        wp_idx = 1

        for poly_idx, poly in enumerate(self._polylines):
            # Remove duplicate consecutive vertices
            cleaned: List[Tuple[float, float]] = [poly[0]]
            for pt in poly[1:]:
                if pt != cleaned[-1]:
                    cleaned.append(pt)

            if len(cleaned) < 2:
                continue

            for vert_idx, (px, py) in enumerate(cleaned):
                # Convert pixel coords to mm (Y flipped so Y-up = positive)
                mm_x = round((px - px_xmin) * scale, 3)
                mm_y = round((px_ymax - py) * scale, 3)  # flip Y

                if vert_idx == 0:
                    # Travel point — move to the start of a new contour
                    # with laser off / tool raised
                    points.append(Point(
                        name=f"T{wp_idx}",
                        x=mm_x,
                        y=mm_y,
                        z=round(z_safe, 3),
                        feed_to_next=feed,
                        z_safe=z_safe,
                        power=0,
                    ))
                    wp_idx += 1

                # Cutting / engraving point along the contour
                points.append(Point(
                    name=f"E{wp_idx}",
                    x=mm_x,
                    y=mm_y,
                    z=round(z_surface, 3),
                    feed_to_next=feed,
                    z_safe=z_safe,
                    power=255,
                ))
                wp_idx += 1

        return points
