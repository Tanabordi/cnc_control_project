"""GRBL-specific commands."""

from PySide6.QtWidgets import QMessageBox


def set_work_zero(main_window):
    """Set G54 work zero at current position."""
    main_window.worker.send_line("G10 L20 P1 X0 Y0 Z0")
    main_window.on_log("Set G54 work zero at current position")


def go_machine_zero(main_window):
    """Go to machine zero in G53 coordinates."""
    main_window.worker.send_line("G90")
    main_window.worker.send_line("G53 G0 X0 Y0 Z0")
    main_window.on_log("Go to Machine Zero (G53)")


def go_work_zero(main_window):
    """Go to work zero (G0 X0 Y0 Z0)."""
    main_window.worker.send_line("G90")
    main_window.worker.send_line("G0 X0 Y0 Z0")
    main_window.on_log("Go to Work Zero (G0 X0 Y0 Z0)")


def do_home_all(main_window):
    """Home all axes ($H)."""
    if not main_window.controller.is_connected():
        return
    main_window.worker.send_line("$H")
    main_window.on_log("Homing All axes ($H)")


def do_home_x(main_window):
    """Home X axis ($HX)."""
    if not main_window.controller.is_connected():
        return
    main_window.worker.send_line("$HX")
    main_window.on_log("Homing X axis ($HX)")


def do_home_y(main_window):
    """Home Y axis ($HY)."""
    if not main_window.controller.is_connected():
        return
    main_window.worker.send_line("$HY")
    main_window.on_log("Homing Y axis ($HY)")


def do_home_z(main_window):
    """Home Z axis ($HZ)."""
    if not main_window.controller.is_connected():
        return
    main_window.worker.send_line("$HZ")
    main_window.on_log("Homing Z axis ($HZ)")


def do_reset(main_window):
    """Reset GRBL (soft reset).
    
    If auto_unlock_after_reset is enabled, the machine will auto-unlock.
    Otherwise, it stays locked until user presses Unlock.
    """
    if not main_window.controller.is_connected():
        return
    if not main_window.settings.auto_unlock_after_reset:
        main_window.controller._ui_locked = True
    main_window.worker.send_reset()


def do_estop(main_window):
    """Emergency stop."""
    if not main_window.controller.is_connected():
        return
    ret = QMessageBox.question(
        main_window, "Confirm E-STOP",
        "ต้องการสั่ง E-STOP ใช่ไหม?\n(จะส่ง HOLD ! + CTRL+X และไม่ Auto Unlock)",
        QMessageBox.Yes | QMessageBox.No
    )
    if ret != QMessageBox.Yes:
        return
    import time
    main_window.controller._estop_triggered = True
    main_window.controller._estop_time = time.time()
    main_window.controller._ui_locked = True
    main_window.worker.estop()


def send_console_command(main_window):
    """Send command from console input."""
    cp = main_window.control_page
    cmd = cp.console_input.text().strip()
    if not cmd:
        return
    main_window.worker.send_line(cmd)
    cp.console_input.clear()


def send_run_console_command(main_window):
    """Send command from run page console input."""
    rp = main_window.run_page
    cmd = rp.console_input.text().strip()
    if not cmd:
        return
    main_window.worker.send_line(cmd)
    rp.console_input.clear()
