"""Machine movement and jogging operations."""


def get_step(main_window):
    """Get current step size."""
    cp = main_window.control_page
    mode = cp.step_mode.currentText()
    # Extract just the number part (e.g., "0.1 mm" -> "0.1")
    mode_value = mode.split()[0] if " " in mode else mode
    try:
        return float(mode_value)
    except ValueError:
        return 1.0


def on_step_mode(main_window, txt: str):
    """Handle step mode change — no custom mode anymore."""
    pass


def jog(main_window, axis: str, delta: float):
    """Jog machine in specified axis."""
    f = main_window.control_page.feed.value()
    if not main_window.controller.jog(axis, delta, f):
        main_window.on_log(f"Soft limit blocked. Target position out of bounds.")


def move_to_target(main_window):
    """Move to target position (all 3 axes)."""
    cp = main_window.control_page
    x, y, z = cp.tx.value(), cp.ty.value(), cp.tz.value()
    f = cp.feed.value()
    if not main_window.controller.move_to_position(x, y, z, f):
        main_window.on_log(f"Soft limit blocked. Target: X{x:.3f} Y{y:.3f} Z{z:.3f}")
        return


def move_single_axis(main_window, axis: str):
    """Move a single axis to the target value."""
    cp = main_window.control_page
    f = cp.feed.value()
    val_map = {"X": cp.tx.value(), "Y": cp.ty.value(), "Z": cp.tz.value()}
    val = val_map.get(axis, 0)
    cmd = f"G90 G0 {axis}{val:.3f} F{f}"
    main_window.on_log(f"[MOVE] {axis} → {val:.3f} (F{f})")
    main_window.worker.send_line(cmd)
