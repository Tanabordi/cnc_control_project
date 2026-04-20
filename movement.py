"""Machine movement and jogging operations."""


def get_step(main_window):
    """Get current step size."""
    cp = main_window.control_page
    mode = cp.step_mode.currentText()
    return float(mode) if mode in ("0.1", "1", "10") else float(cp.step_mm.value())


def on_step_mode(main_window, txt: str):
    """Handle step mode change."""
    main_window.control_page.step_mm.setEnabled(txt == "Custom")


def jog(main_window, axis: str, delta: float):
    """Jog machine in specified axis."""
    f = main_window.control_page.feed.value()
    if not main_window.controller.jog(axis, delta, f):
        main_window.on_log(f"Soft limit blocked. Target position out of bounds.")


def move_to_target(main_window):
    """Move to target position."""
    cp = main_window.control_page
    x, y, z = cp.tx.value(), cp.ty.value(), cp.tz.value()
    f = cp.feed.value()
    if not main_window.controller.move_to_position(x, y, z, f):
        main_window.on_log(f"Soft limit blocked. Target: X{x:.3f} Y{y:.3f} Z{z:.3f}")
        return
