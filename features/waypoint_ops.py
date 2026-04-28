"""Waypoint and point operations."""

from pathlib import Path
import json

from PySide6.QtWidgets import QMessageBox, QFileDialog, QTableWidgetItem

from core.grbl_parser import clamp


def on_waypoint_clicked(main_window, row: int, col: int):
    """Handle waypoint table click."""
    if not main_window.controller.is_connected():
        return
    if main_window.controller.is_streaming():
        main_window.on_log("กำลัง Run/Stream อยู่: ไม่อนุญาตให้วิ่งไป Waypoint จากตาราง")
        return
    if row < 0 or row >= len(main_window.controller.points):
        return

    cp = main_window.control_page
    p = main_window.controller.points[row]
    cp.wp_feed.setValue(int(p.feed_to_next))
    cp.wp_laser_time.setValue(float(p.laser_time_s))
    cp.wp_z_safe.setValue(float(p.z_safe))
    cp.wp_power.setValue(int(p.power))
    cp.tx.setValue(float(p.x))
    cp.ty.setValue(float(p.y))
    cp.tz.setValue(float(p.z))
    cp.update_btn.setEnabled(True)

    f = int(p.feed_to_next) if p.feed_to_next else int(cp.feed.value())
    if not main_window.controller.move_to_waypoint(row, f):
        main_window.on_log(f"Soft limit blocked. Target: X{p.x:.3f} Y{p.y:.3f} Z{p.z:.3f}")
        return
    main_window.on_log(f"Go to waypoint #{row+1}: X{p.x:.3f} Y{p.y:.3f} Z{p.z:.3f} F{f}")


def update_selected_point(main_window):
    """Update selected waypoint with current position."""
    if not main_window.controller.is_connected():
        return
    if main_window.controller.is_streaming():
        main_window.on_log("กำลัง Run/Stream อยู่: ไม่อนุญาตให้ Update ระหว่าง Stream")
        return
    cp = main_window.control_page
    row = cp.wp_table.currentRow()
    if row is None or row < 0 or row >= len(main_window.controller.points):
        main_window.on_log("เลือกแถวที่ต้องการ Update ก่อน")
        return
    wpos = main_window.worker.last_wpos()
    if not wpos:
        main_window.on_log("No position received yet.")
        return
    x, y, z = wpos
    f = int(cp.wp_feed.value())
    t = float(cp.wp_laser_time.value())
    zs = float(cp.wp_z_safe.value())
    pw = int(cp.wp_power.value())

    if not main_window.controller.update_point(row, x, y, z, f, t, zs, pw):
        main_window.on_log(f"Soft limit blocked. Current: X{x:.3f} Y{y:.3f} Z{z:.3f}")
        return

    main_window._refresh_table_from_points()
    cp.wp_table.selectRow(row)
    main_window.on_log(f"Updated waypoint #{row+1} -> X{x:.3f} Y{y:.3f} Z{z:.3f} Zsafe{zs:.3f} F{f} T{t:.2f} S{pw}")


def _refresh_table_from_points(main_window):
    """Refresh waypoint table from controller points."""
    cp = main_window.control_page
    cp.wp_table.setRowCount(0)
    for i, p in enumerate(main_window.controller.points, start=1):
        r = cp.wp_table.rowCount()
        cp.wp_table.insertRow(r)
        cp.wp_table.setItem(r, 0, QTableWidgetItem(str(i)))
        cp.wp_table.setItem(r, 1, QTableWidgetItem(f"X{p.x:.3f} Y{p.y:.3f}"))
        cp.wp_table.setItem(r, 2, QTableWidgetItem(f"{p.z:.3f}"))
        cp.wp_table.setItem(r, 3, QTableWidgetItem(f"{p.z_safe:.3f}"))
        cp.wp_table.setItem(r, 4, QTableWidgetItem(str(int(p.feed_to_next))))
        cp.wp_table.setItem(r, 5, QTableWidgetItem(f"{float(p.laser_time_s):.2f}"))
        cp.wp_table.setItem(r, 6, QTableWidgetItem(str(int(p.power))))

    cp.preview3d_btn.setEnabled(len(main_window.controller.points) >= 2 and main_window.controller.is_connected())
    cp.export_gcode_btn.setEnabled(len(main_window.controller.points) >= 1 and main_window.controller.is_connected())
    cp.export_panel_btn.setEnabled(len(main_window.controller.points) >= 1 and main_window.controller.is_connected())
    cp.save_waypoints_btn.setEnabled(len(main_window.controller.points) >= 1)
    cp.delete_btn.setEnabled(len(main_window.controller.points) >= 1 and main_window.controller.is_connected())
    cp.update_btn.setEnabled(
        main_window.controller.is_connected() and (cp.wp_table.currentRow() >= 0) and (not main_window.controller.is_streaming())
    )


def capture_point(main_window):
    """Capture current position as waypoint."""
    cp = main_window.control_page
    wpos = main_window.worker.last_wpos()
    if not wpos:
        main_window.on_log("No position received yet.")
        return
    x, y, z = wpos
    f = int(cp.wp_feed.value())
    t = float(cp.wp_laser_time.value())
    zs = float(cp.wp_z_safe.value())
    pw = int(cp.wp_power.value())
    main_window.controller.add_point(x, y, z, f, t, zs, pw)
    main_window._refresh_table_from_points()


def delete_selected_point(main_window):
    """Delete selected waypoint."""
    cp = main_window.control_page
    row = cp.wp_table.currentRow()
    if row is None or row < 0 or row >= len(main_window.controller.points):
        return
    if main_window.controller.delete_point(row):
        main_window._refresh_table_from_points()


def clear_points(main_window):
    """Clear all waypoints."""
    main_window.controller.clear_points()
    main_window._refresh_table_from_points()


def preview_3d(main_window):
    """Preview 3D path."""
    from gui.preview import Preview3DWindow
    if not main_window.controller.points or len(main_window.controller.points) < 2:
        QMessageBox.warning(main_window, "Preview 3D", "ต้องมีอย่างน้อย 2 points")
        return
    safe_z = clamp(main_window.settings.safe_z, main_window.settings.zmin, main_window.settings.zmax)
    Preview3DWindow(main_window.controller.points, safe_z=safe_z, parent=main_window).exec()


def load_points_gcode(main_window):
    """Load waypoints from G-code file."""
    path, _ = QFileDialog.getOpenFileName(main_window, "Load Points from G-code", "", "G-code (*.gcode *.nc *.ngc *.txt)")
    if not path:
        return

    default_feed = int(main_window.control_page.wp_feed.value())
    if main_window.controller.load_points_from_gcode(path, default_feed):
        main_window._refresh_table_from_points()
        main_window.on_log(f"Loaded points from G-code: {path} ({len(main_window.controller.points)} points)")
    else:
        QMessageBox.critical(main_window, "Error", "Failed to load points from G-code file.")


def load_pcb_csv(main_window):
    """Import PCB positions from CSV."""
    from features.importers.pcb_import import parse_pcb_csv, PcbCalibDialog
    path, _ = QFileDialog.getOpenFileName(
        main_window, "Import PCB CSV", "", "CSV Files (*.csv);;All Files (*)"
    )
    if not path:
        return

    try:
        components, has_side = parse_pcb_csv(path)
    except Exception as e:
        QMessageBox.critical(main_window, "Error", f"ไม่สามารถอ่านไฟล์ CSV ได้:\n{e}")
        return

    if not components:
        QMessageBox.warning(main_window, "Empty", "ไม่พบ component ในไฟล์ CSV")
        return

    main_window.on_log(f"PCB CSV: {len(components)} components จาก {path}")

    dlg = PcbCalibDialog(components, has_side, main_window.worker, main_window)
    if dlg.exec() != PcbCalibDialog.Accepted:
        return

    wp = dlg.get_waypoints(
        default_feed=int(main_window.control_page.wp_feed.value()),
        default_time=float(main_window.control_page.wp_laser_time.value()),
    )
    if not wp:
        QMessageBox.warning(main_window, "Error", "ไม่สามารถคำนวณ waypoints ได้ (ตรวจสอบ calibration points)")
        return

    main_window.controller.points = wp
    main_window._refresh_table_from_points()
    main_window.on_log(f"Imported {len(main_window.controller.points)} waypoints from PCB CSV")


def save_waypoints_json(main_window):
    """Save waypoints to JSON file."""
    if not main_window.controller.points:
        QMessageBox.warning(main_window, "No Points", "ไม่มี waypoints ที่จะบันทึก")
        return
    path, _ = QFileDialog.getSaveFileName(
        main_window, "Save Waypoints", "waypoints.json", "JSON (*.json)"
    )
    if not path:
        return
    try:
        main_window.controller.save_waypoints_json(path)
        main_window.on_log(f"Saved {len(main_window.controller.points)} waypoints -> {path}")
    except Exception as e:
        QMessageBox.critical(main_window, "Error", f"Failed to save waypoints:\n{e}")


def load_waypoints_json(main_window):
    """Load waypoints from JSON file."""
    path, _ = QFileDialog.getOpenFileName(
        main_window, "Load Waypoints", "", "JSON (*.json)"
    )
    if not path:
        return
    if main_window.controller.load_waypoints_json(path):
        main_window._refresh_table_from_points()
        main_window.on_log(f"Loaded {len(main_window.controller.points)} waypoints <- {path}")
    else:
        QMessageBox.critical(main_window, "Error", "Failed to load waypoints from JSON file.")
