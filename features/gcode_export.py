"""G-code export operations."""

from pathlib import Path
from PySide6.QtWidgets import QMessageBox, QFileDialog

from gui.dialogs import PanelConfigDialog


def export_gcode(main_window):
    """Export waypoints to G-code file."""
    if not main_window.controller.points:
        QMessageBox.warning(main_window, "No Points", "Capture points first.")
        return

    cfg_dlg = PanelConfigDialog(parent=main_window)
    if cfg_dlg.exec() != PanelConfigDialog.Accepted:
        return

    path, _ = QFileDialog.getSaveFileName(main_window, "Export G-code", "points.gcode", "G-code (*.gcode *.nc *.ngc)")
    if not path:
        return

    rows = cols = 1
    if cfg_dlg.is_panel():
        rows, cols = cfg_dlg.get_layout()

    lines = main_window.controller.generate_gcode_lines(main_window.controller.points, rows, cols)

    try:
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        main_window.on_log(f"Exported: {path}")
    except Exception as e:
        QMessageBox.critical(main_window, "Error", f"Failed to export G-code:\n{e}")


def export_panel_gcode(main_window):
    """Export panel G-code with calibration dialog."""
    if not main_window.controller.points:
        QMessageBox.warning(main_window, "No Points", "Capture points first.")
        return

    from features.importers.pcb_import import PanelExportDialog
    dlg = PanelExportDialog(main_window.controller.points, main_window.worker, main_window)
    if dlg.exec() != PanelExportDialog.Accepted:
        return

    path, _ = QFileDialog.getSaveFileName(main_window, "Export Panel G-code", "points_panel.gcode", "G-code (*.gcode *.nc *.ngc)")
    if not path:
        return

    try:
        offsets = dlg.get_offsets()
        lines = ["G90", "G21", "G54"] + main_window.controller._build_panel_lines(main_window.controller.points, offsets)
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        main_window.on_log(f"Exported panel: {path}")
    except Exception as e:
        QMessageBox.critical(main_window, "Error", f"Failed to export panel G-code:\n{e}")
