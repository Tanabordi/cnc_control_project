"""Vector import dialog — parse SVG / DXF files into CNC waypoints."""

import math
from pathlib import Path
from typing import List, Tuple, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QGroupBox, QWidget,
    QLineEdit, QDoubleSpinBox, QSpinBox,
    QFileDialog, QMessageBox, QSizePolicy,
    QDialogButtonBox, QComboBox,
)

from core.models import Point


# ---------------------------------------------------------------------------
# SVG parsing helpers  (uses svgelements)
# ---------------------------------------------------------------------------

def _parse_svg(filepath: str, num_points: int = 200) -> List[List[Tuple[float, float]]]:
    """
    Parse an SVG file and return a list of *polylines*.
    Each polyline is a list of (x, y) tuples representing a continuous path.

    ``num_points`` controls how many sample points are used when
    linearising curves (arcs, beziers, etc.).
    """
    from svgelements import SVG, Path as SvgPath, Shape, Polyline, Line, Rect, Circle, Ellipse

    svg = SVG.parse(filepath)
    polylines: List[List[Tuple[float, float]]] = []

    for element in svg.elements():
        coords: List[Tuple[float, float]] = []

        if isinstance(element, SvgPath):
            # Sample the path at many small steps to linearise curves
            try:
                length = element.length()
            except (ZeroDivisionError, ValueError, ArithmeticError):
                continue
            if length <= 0:
                continue

            steps = max(num_points, 2)
            for i in range(steps + 1):
                try:
                    pt = element.point(i / steps)
                    coords.append((float(pt.x), float(pt.y)))
                except (ZeroDivisionError, ValueError, ArithmeticError):
                    continue

        elif isinstance(element, (Line, Polyline)):
            # Simple line / polyline elements
            if hasattr(element, 'points') and element.points:
                for pt in element.points:
                    coords.append((float(pt.x), float(pt.y)))
            elif hasattr(element, 'd'):
                # Fall back to treating it as a path
                try:
                    path = SvgPath(element.d())
                    length = path.length()
                    if length <= 0:
                        continue
                    steps = max(num_points, 2)
                    for i in range(steps + 1):
                        pt = path.point(i / steps)
                        coords.append((float(pt.x), float(pt.y)))
                except Exception:
                    continue

        elif isinstance(element, Rect):
            x = float(element.x)
            y = float(element.y)
            w = float(element.width)
            h = float(element.height)
            coords = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]

        elif isinstance(element, (Circle, Ellipse)):
            cx = float(element.cx)
            cy = float(element.cy)
            rx = float(getattr(element, 'rx', getattr(element, 'r', 0)))
            ry = float(getattr(element, 'ry', getattr(element, 'r', 0)))
            n = max(num_points, 36)
            for i in range(n + 1):
                angle = 2 * math.pi * i / n
                coords.append((cx + rx * math.cos(angle), cy + ry * math.sin(angle)))

        # Filter out degenerate polylines
        if len(coords) >= 2:
            polylines.append(coords)

    return polylines


# ---------------------------------------------------------------------------
# DXF parsing helpers  (uses ezdxf)
# ---------------------------------------------------------------------------

def _parse_dxf(filepath: str, num_points: int = 200) -> List[List[Tuple[float, float]]]:
    """
    Parse a DXF file and return a list of polylines.
    Handles LINE, LWPOLYLINE, POLYLINE, CIRCLE, ARC, ELLIPSE, and SPLINE.
    """
    import ezdxf

    doc = ezdxf.readfile(filepath)
    msp = doc.modelspace()
    polylines: List[List[Tuple[float, float]]] = []

    for entity in msp:
        coords: List[Tuple[float, float]] = []
        etype = entity.dxftype()

        if etype == "LINE":
            s = entity.dxf.start
            e = entity.dxf.end
            coords = [(float(s.x), float(s.y)), (float(e.x), float(e.y))]

        elif etype == "LWPOLYLINE":
            for x, y, *_ in entity.get_points(format="xy"):
                coords.append((float(x), float(y)))
            if entity.closed and len(coords) >= 2:
                coords.append(coords[0])

        elif etype == "POLYLINE":
            for vertex in entity.vertices:
                loc = vertex.dxf.location
                coords.append((float(loc.x), float(loc.y)))
            if entity.is_closed and len(coords) >= 2:
                coords.append(coords[0])

        elif etype == "CIRCLE":
            cx = float(entity.dxf.center.x)
            cy = float(entity.dxf.center.y)
            r = float(entity.dxf.radius)
            n = max(num_points, 36)
            for i in range(n + 1):
                angle = 2 * math.pi * i / n
                coords.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))

        elif etype == "ARC":
            cx = float(entity.dxf.center.x)
            cy = float(entity.dxf.center.y)
            r = float(entity.dxf.radius)
            start_angle = math.radians(float(entity.dxf.start_angle))
            end_angle = math.radians(float(entity.dxf.end_angle))
            if end_angle <= start_angle:
                end_angle += 2 * math.pi
            n = max(num_points, 36)
            for i in range(n + 1):
                angle = start_angle + (end_angle - start_angle) * i / n
                coords.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))

        elif etype == "ELLIPSE":
            try:
                # ezdxf can flatten an ellipse to vertices
                pts = list(entity.vertices(entity.param_count(num_points)))
                for v in pts:
                    coords.append((float(v.x), float(v.y)))
            except Exception:
                pass

        elif etype == "SPLINE":
            try:
                pts = list(entity.flattening(0.1))
                for v in pts:
                    coords.append((float(v.x), float(v.y)))
            except Exception:
                pass

        if len(coords) >= 2:
            polylines.append(coords)

    return polylines


# ---------------------------------------------------------------------------
# Preview canvas
# ---------------------------------------------------------------------------

class VectorPreviewCanvas(QWidget):
    """2D preview widget that draws the parsed vector polylines."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.polylines: List[List[Tuple[float, float]]] = []
        self.setMinimumSize(280, 280)
        self._margin = 32

    def set_polylines(self, polylines: List[List[Tuple[float, float]]]):
        self.polylines = polylines
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(24, 24, 30))

        if not self.polylines:
            painter.setPen(QColor(120, 120, 140))
            painter.setFont(QFont("Arial", 10))
            painter.drawText(self.rect(), Qt.AlignCenter, "No vector data loaded")
            painter.end()
            return

        # Compute bounding box across all polylines
        all_x = [pt[0] for poly in self.polylines for pt in poly]
        all_y = [pt[1] for poly in self.polylines for pt in poly]
        xmin, xmax = min(all_x), max(all_x)
        ymin, ymax = min(all_y), max(all_y)
        x_span = (xmax - xmin) or 1.0
        y_span = (ymax - ymin) or 1.0

        avail_w = self.width() - 2 * self._margin
        avail_h = self.height() - 2 * self._margin
        scale = min(avail_w / x_span, avail_h / y_span)
        ox = self._margin + (avail_w - x_span * scale) / 2
        oy = self._margin + (avail_h - y_span * scale) / 2

        def to_canvas(px, py):
            cx = ox + (px - xmin) * scale
            cy = oy + (y_span - (py - ymin)) * scale  # flip Y for screen
            return int(cx), int(cy)

        # Draw bounding rect
        tl = to_canvas(xmin, ymax)
        br = to_canvas(xmax, ymin)
        painter.setPen(QPen(QColor(60, 60, 80), 1, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(tl[0], tl[1], br[0] - tl[0], br[1] - tl[1])

        # Draw polylines with varying hue
        n_poly = len(self.polylines)
        for idx, poly in enumerate(self.polylines):
            hue = int(200 + 160 * idx / max(n_poly, 1)) % 360
            color = QColor.fromHsl(hue, 200, 160)
            painter.setPen(QPen(color, 1.5))
            for i in range(len(poly) - 1):
                x1, y1 = to_canvas(*poly[i])
                x2, y2 = to_canvas(*poly[i + 1])
                painter.drawLine(x1, y1, x2, y2)

        # Info text
        n_pts = sum(len(p) for p in self.polylines)
        painter.setPen(QColor(160, 170, 200))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(
            self._margin, self._margin - 8,
            f"{n_poly} paths  |  {n_pts} vertices  |  "
            f"Bounds: {x_span:.2f} × {y_span:.2f}"
        )

        painter.end()


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------

class VectorImportDialog(QDialog):
    """
    Dialog for importing SVG or DXF vector files into CNC waypoints.

    The user selects a file, configures scale / depth / feed parameters,
    and the dialog converts the vector paths into a list of ``Point``
    objects that can be appended to the main waypoint table.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Vector File (SVG / DXF)")
        self.setModal(True)
        self.resize(900, 620)

        self._filepath: Optional[str] = None
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

        self.canvas = VectorPreviewCanvas()
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lv.addWidget(self.canvas, 1)

        self.info_lbl = QLabel("Select a .svg or .dxf file to preview")
        self.info_lbl.setAlignment(Qt.AlignCenter)
        self.info_lbl.setStyleSheet("color: #888; font-size: 11px;")
        lv.addWidget(self.info_lbl)

        main.addWidget(left_w, 1)

        # ===== Right: controls =====
        right_w = QWidget()
        right_w.setFixedWidth(320)
        rv = QVBoxLayout(right_w)
        rv.setSpacing(8)

        # --- File selection ---
        file_box = QGroupBox("Vector File")
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

        # --- Parameters ---
        param_box = QGroupBox("Import Parameters")
        pf = QFormLayout(param_box)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.001, 10000.0)
        self.scale_spin.setDecimals(4)
        self.scale_spin.setValue(1.0)
        self.scale_spin.setSuffix("  (1 unit = 1 mm)")
        self.scale_spin.setToolTip(
            "Scale factor to convert file units to millimetres.\n"
            "E.g. if the file is in inches, set to 25.4."
        )
        pf.addRow("Scale Factor:", self.scale_spin)

        self.z_surface_spin = QDoubleSpinBox()
        self.z_surface_spin.setRange(-9999.0, 9999.0)
        self.z_surface_spin.setDecimals(3)
        self.z_surface_spin.setValue(0.0)
        self.z_surface_spin.setSuffix(" mm")
        self.z_surface_spin.setToolTip("Z depth for cutting / engraving moves (G1).")
        pf.addRow("Z-Surface Depth:", self.z_surface_spin)

        self.z_safe_spin = QDoubleSpinBox()
        self.z_safe_spin.setRange(-9999.0, 9999.0)
        self.z_safe_spin.setDecimals(3)
        self.z_safe_spin.setValue(-2.0)
        self.z_safe_spin.setSuffix(" mm")
        self.z_safe_spin.setToolTip(
            "Z height for rapid travel moves (G0) between paths.\n"
            "Must be above the surface to avoid collisions."
        )
        pf.addRow("Z-Safe:", self.z_safe_spin)

        self.feed_spin = QSpinBox()
        self.feed_spin.setRange(1, 50000)
        self.feed_spin.setValue(1000)
        self.feed_spin.setSuffix(" mm/min")
        self.feed_spin.setToolTip("Feed rate for cutting moves.")
        pf.addRow("Feed Rate:", self.feed_spin)

        rv.addWidget(param_box)

        # --- Sampling resolution (for curves) ---
        curve_box = QGroupBox("Curve Resolution")
        cf = QFormLayout(curve_box)

        self.resolution_spin = QSpinBox()
        self.resolution_spin.setRange(10, 5000)
        self.resolution_spin.setValue(200)
        self.resolution_spin.setToolTip(
            "Number of sample points used to linearise curves.\n"
            "Higher = smoother but more waypoints."
        )
        cf.addRow("Sample Points:", self.resolution_spin)

        rv.addWidget(curve_box)

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
            "Select Vector File",
            "",
            "Vector Files (*.svg *.dxf);;SVG Files (*.svg);;DXF Files (*.dxf);;All Files (*)",
        )
        if not path:
            return

        self._filepath = path
        self.file_lbl.setText(Path(path).name)
        self.file_lbl.setStyleSheet("color: #8ecfff; font-weight: bold;")

        self._load_file(path)

    def _load_file(self, path: str):
        """Parse the selected file and update the preview."""
        ext = Path(path).suffix.lower()
        num_pts = self.resolution_spin.value()

        try:
            if ext == ".svg":
                self._polylines = _parse_svg(path, num_points=num_pts)
            elif ext == ".dxf":
                self._polylines = _parse_dxf(path, num_points=num_pts)
            else:
                QMessageBox.warning(
                    self, "Unsupported Format",
                    f"File extension '{ext}' is not supported.\n"
                    "Please select a .svg or .dxf file."
                )
                return
        except Exception as exc:
            QMessageBox.critical(
                self, "Parse Error",
                f"Failed to parse the file:\n\n{exc}"
            )
            self._polylines = []
            self.canvas.set_polylines([])
            self.confirm_btn.setEnabled(False)
            return

        if not self._polylines:
            self.status_lbl.setText("⚠  No drawable paths found in this file.")
            self.status_lbl.setStyleSheet("color: #ffaa44; font-size: 11px;")
            self.canvas.set_polylines([])
            self.confirm_btn.setEnabled(False)
            return

        self.canvas.set_polylines(self._polylines)
        self.confirm_btn.setEnabled(True)

        total_vertices = sum(len(p) for p in self._polylines)
        self.status_lbl.setText(
            f"✔  Loaded {len(self._polylines)} path(s), "
            f"{total_vertices} vertices total."
        )
        self.status_lbl.setStyleSheet("color: #88ff88; font-size: 11px;")

        # Update info label with bounding-box dimensions
        all_x = [pt[0] for poly in self._polylines for pt in poly]
        all_y = [pt[1] for poly in self._polylines for pt in poly]
        w = max(all_x) - min(all_x)
        h = max(all_y) - min(all_y)
        scale = self.scale_spin.value()
        self.info_lbl.setText(
            f"{Path(path).name}  —  "
            f"Raw: {w:.2f} × {h:.2f} units  |  "
            f"Scaled: {w * scale:.2f} × {h * scale:.2f} mm"
        )
        self.info_lbl.setStyleSheet("color: #bbc; font-size: 11px;")

    # --------------------------------------------------------------- output --

    def get_waypoints(self) -> List[Point]:
        """
        Convert the parsed vector polylines into a flat list of ``Point``
        objects using the current UI parameter values.

        Each continuous polyline becomes a series of consecutive waypoints.
        Between polylines, the tool is assumed to rapid-travel at Z-Safe
        (handled by the G-code generator), so every first point of a new
        polyline is simply the next waypoint in sequence.
        """
        if not self._polylines:
            return []

        scale = self.scale_spin.value()
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

            for vert_idx, (vx, vy) in enumerate(cleaned):
                points.append(Point(
                    name=f"V{wp_idx}",
                    x=round(vx * scale, 3),
                    y=round(vy * scale, 3),
                    z=round(z_surface, 3),
                    feed_to_next=feed,
                    z_safe=z_safe,
                ))
                wp_idx += 1

        return points
