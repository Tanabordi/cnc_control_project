"""Universal 2-Point Calibration Dialog for crooked material alignment.

Allows the user to jog the CNC machine to two reference points on the
physical material.  The recorded machine positions are used by
``core.transform.compute_affine_2point`` to compute rotation + scale
compensation so the final cut aligns with the material, even if it is
placed crookedly on the CNC bed.

This dialog is generic — it works with any import type (vector, image).
The PCB import has its own ``PcbCalibDialog`` which selects components
as reference points; this dialog uses bounding-box corners instead.
"""

import math
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QWidget,
    QMessageBox, QComboBox, QDoubleSpinBox, QSpinBox,
    QGridLayout,
)

from core.worker import GrblWorker


class TwoPointCalibDialog(QDialog):
    """
    Calibration dialog — user jogs to 2 reference points on the material.

    Parameters
    ----------
    design_p1, design_p2 :
        Reference coordinates in design space (e.g. bounding-box corners,
        already in final scaled units).
    worker :
        The ``GrblWorker`` instance for live position and jog commands.
    parent :
        Parent widget.
    """

    def __init__(
        self,
        design_p1: Tuple[float, float],
        design_p2: Tuple[float, float],
        worker: GrblWorker,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Material Calibration — 2-Point")
        self.setModal(True)
        self.resize(460, 580)

        self._design_p1 = design_p1
        self._design_p2 = design_p2
        self.worker = worker
        self.machine_p1: Optional[Tuple[float, float]] = None
        self.machine_p2: Optional[Tuple[float, float]] = None

        self._build_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_pos)
        self._timer.start(150)

    # ------------------------------------------------------------------ UI --

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # --- Design reference info ---
        info_box = QGroupBox("Design Reference Points")
        iv = QVBoxLayout(info_box)
        iv.addWidget(QLabel(
            f"P1 (Bottom-Left):  X{self._design_p1[0]:.3f}  "
            f"Y{self._design_p1[1]:.3f}"
        ))
        iv.addWidget(QLabel(
            f"P2 (Top-Right):  X{self._design_p2[0]:.3f}  "
            f"Y{self._design_p2[1]:.3f}"
        ))
        design_dist = math.hypot(
            self._design_p2[0] - self._design_p1[0],
            self._design_p2[1] - self._design_p1[1],
        )
        iv.addWidget(QLabel(f"Distance P1→P2:  {design_dist:.3f} mm"))
        root.addWidget(info_box)

        # --- Live position ---
        pos_box = QGroupBox("Machine Work Position")
        pv = QVBoxLayout(pos_box)
        self.pos_lbl = QLabel("X: -.---   Y: -.---   Z: -.---")
        self.pos_lbl.setAlignment(Qt.AlignCenter)
        self.pos_lbl.setStyleSheet(
            "font-size: 13px; font-weight: bold; font-family: monospace;"
        )
        pv.addWidget(self.pos_lbl)
        root.addWidget(pos_box)

        # --- Jog controls ---
        jog_box = QGroupBox("Jog — Move Machine Head")
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
        root.addWidget(jog_box)

        self._jb_up.clicked.connect(lambda: self._jog("Y", +1))
        self._jb_dn.clicked.connect(lambda: self._jog("Y", -1))
        self._jb_lt.clicked.connect(lambda: self._jog("X", -1))
        self._jb_rt.clicked.connect(lambda: self._jog("X", +1))
        self._jb_zup.clicked.connect(lambda: self._jog("Z", +1))
        self._jb_zdn.clicked.connect(lambda: self._jog("Z", -1))

        # --- Set calibration points ---
        cal_box = QGroupBox("Calibration Points")
        cv = QVBoxLayout(cal_box)

        cv.addWidget(QLabel(
            "Step 1 — Jog to P1 (Bottom-Left corner) on the material:"
        ))
        self.p1_lbl = QLabel("  Not set")
        self.p1_lbl.setStyleSheet("color: #888;")
        cv.addWidget(self.p1_lbl)
        self.set_p1_btn = QPushButton("📍  Set P1  (Bottom-Left)")
        self.set_p1_btn.setMinimumHeight(36)
        self.set_p1_btn.clicked.connect(self._set_p1)
        cv.addWidget(self.set_p1_btn)

        cv.addSpacing(6)

        cv.addWidget(QLabel(
            "Step 2 — Jog to P2 (Top-Right corner) on the material:"
        ))
        self.p2_lbl = QLabel("  Not set")
        self.p2_lbl.setStyleSheet("color: #888;")
        cv.addWidget(self.p2_lbl)
        self.set_p2_btn = QPushButton("📍  Set P2  (Top-Right)")
        self.set_p2_btn.setMinimumHeight(36)
        self.set_p2_btn.clicked.connect(self._set_p2)
        cv.addWidget(self.set_p2_btn)

        root.addWidget(cal_box)

        # --- Result info ---
        self.result_lbl = QLabel("")
        self.result_lbl.setWordWrap(True)
        self.result_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        root.addWidget(self.result_lbl)

        root.addStretch(1)

        # --- Buttons ---
        self.confirm_btn = QPushButton("✔  Apply Calibration")
        self.confirm_btn.setMinimumHeight(42)
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self.accept)
        root.addWidget(self.confirm_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(32)
        cancel_btn.clicked.connect(self.reject)
        root.addWidget(cancel_btn)

    # --------------------------------------------------------------- slots --

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
            QMessageBox.warning(
                self, "Error",
                "No position received from the machine.\n"
                "Check connection."
            )
            return
        x, y, _ = wpos
        self.machine_p1 = (x, y)
        self.p1_lbl.setText(f"  ✔  X{x:.3f}  Y{y:.3f}")
        self.p1_lbl.setStyleSheet("color: #00aaff; font-weight: bold;")
        self._check_ready()

    def _set_p2(self):
        wpos = self.worker.last_wpos()
        if not wpos:
            QMessageBox.warning(
                self, "Error",
                "No position received from the machine.\n"
                "Check connection."
            )
            return
        x, y, _ = wpos
        self.machine_p2 = (x, y)
        self.p2_lbl.setText(f"  ✔  X{x:.3f}  Y{y:.3f}")
        self.p2_lbl.setStyleSheet("color: #ff8800; font-weight: bold;")
        self._check_ready()

    def _check_ready(self):
        if not (self.machine_p1 and self.machine_p2):
            return

        from core.transform import compute_affine_2point
        result = compute_affine_2point(
            self._design_p1, self._design_p2,
            self.machine_p1, self.machine_p2,
        )
        if result is None:
            self.result_lbl.setText("⚠  Degenerate points — distance is zero.")
            self.result_lbl.setStyleSheet("color: #ffaa44; font-size: 11px;")
            self.confirm_btn.setEnabled(False)
            return

        angle_deg = math.degrees(result.rotation)
        mach_dist = math.hypot(
            self.machine_p2[0] - self.machine_p1[0],
            self.machine_p2[1] - self.machine_p1[1],
        )
        design_dist = math.hypot(
            self._design_p2[0] - self._design_p1[0],
            self._design_p2[1] - self._design_p1[1],
        )
        self.result_lbl.setText(
            f"Machine distance P1→P2 : {mach_dist:.2f} mm\n"
            f"Design distance P1→P2  : {design_dist:.2f} mm\n"
            f"Scale factor           : {result.scale:.4f}x\n"
            f"Rotation angle         : {angle_deg:.2f}°"
        )
        self.result_lbl.setStyleSheet("color: #88ff88; font-size: 11px;")
        self.confirm_btn.setEnabled(True)

    # --------------------------------------------------------------- output --

    def get_calibration(
        self,
    ) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
        """Return ``(machine_p1, machine_p2)`` or ``None`` if not set."""
        if self.machine_p1 and self.machine_p2:
            return (self.machine_p1, self.machine_p2)
        return None

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)
