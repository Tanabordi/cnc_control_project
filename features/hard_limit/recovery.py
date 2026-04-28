"""Hard Limit Auto-Recovery logic.

Extracted from gui/app.py to keep MainWindow slim.
Contains the multi-step recovery sequence: $X → $21=0 → jog back → finalize.
"""

from PySide6.QtCore import QTimer
from core.i18n import tr


_BACKOFF_MM = 5  # Distance to back off from sensor (mm)


def do_hard_limit_recovery(main_window, pn: str):
    """Execute auto-recovery sequence: $X → $21=0 → jog back → $21=1 → $X.

    Guard: only one recovery can run at a time. Duplicate calls are silently
    dropped so that the ALARM/status spam loop does not stack recoveries.
    """
    # ── Guard: prevent duplicate recovery ──
    if main_window._recovery_in_progress:
        return
    main_window._recovery_in_progress = True
    main_window._hard_limit_dialog_shown = True  # Prevent on_status / on_alarm from re-entering

    main_window.on_log(tr("hard_limit_log_start"))

    try:
        # Step 1: Send $X to unlock GRBL FIRST so it accepts commands
        main_window.worker.send_line("$X")
        main_window.on_log("> $X (Unlock GRBL for recovery)")

        # Determine backoff directions and lock the crash direction
        jog_parts = []
        for axis in "XYZ":
            if axis in pn.upper():
                backoff_dir = _compute_backoff_direction(main_window, axis)
                jog_parts.append(f"{axis}{backoff_dir}{_BACKOFF_MM:.3f}")

                # Lock the button that crashes into the sensor
                crash_dir = "-" if backoff_dir == "+" else "+"
                main_window._locked_jog_directions.add((axis, crash_dir))
                main_window.on_log(f"🔒 ล็อคปุ่มทิศทาง {axis}{crash_dir} ชั่วคราวป้องกันชนซ้ำ")

        main_window.update_jog_buttons_state()

        # Step 2: After 300ms → Disable hard limits temporarily
        QTimer.singleShot(300, lambda: _recovery_step2(main_window, jog_parts))

    except Exception as e:
        main_window._recovery_in_progress = False
        main_window.on_log(tr("hard_limit_log_fail").replace("{err}", str(e)))


def _recovery_step2(main_window, jog_parts: list):
    """Recovery Step 2: Disable hard limits and Jog back."""
    try:
        main_window.worker.send_line("$21=0")
        main_window.on_log("> $21=0 (Hard limits OFF)")

        # Jog away from sensor
        if jog_parts:
            jog_cmd = f"$J=G91 {' '.join(jog_parts)} F500"
            QTimer.singleShot(200, lambda: _send_jog(main_window, jog_cmd))

        # After 1500ms (wait for jog to finish) → finalize recovery
        # NOTE: We do NOT re-enable $21=1 here. It stays OFF.
        # $21=1 will be sent when user clicks Unlock in _do_unlock().
        # This prevents GRBL from firing ALARM:1 again if sensor is
        # still triggered, which was the root cause of the spam loop.
        QTimer.singleShot(1500, lambda: _recovery_finalize(main_window))
    except Exception as e:
        main_window._recovery_in_progress = False
        main_window.on_log(tr("hard_limit_log_fail").replace("{err}", str(e)))


def _send_jog(main_window, jog_cmd):
    main_window.worker.send_line(jog_cmd)
    main_window.on_log(f"> {jog_cmd} (Back off {_BACKOFF_MM}mm)")


def _recovery_finalize(main_window):
    """Recovery final step: unlock GRBL, lock UI, show dialog ONCE.

    Hard limits ($21) stay OFF — will be re-enabled when user clicks Unlock.
    """
    try:
        main_window.worker.send_line("$X")
        main_window.on_log("> $X (Unlock GRBL after backoff)")

        # Clear alarm state internally
        main_window.controller._alarm_active = False
        main_window.controller._ui_locked = True  # Keep UI locked until user acknowledges the dialog
        main_window._last_alarm_was_hard_limit = False
        main_window._hard_limit_pn = ""
        # Keep _hard_limit_dialog_shown = True so no new recovery triggers

        # ── Mark recovery as DONE ──
        main_window._recovery_in_progress = False

        main_window.update_jog_buttons_state()
        main_window.on_log(tr("hard_limit_log_done"))

        # Show the dialog NOW (exactly once)
        from features.hard_limit.dialog import show_hard_limit_dialog
        pn = main_window.worker._last_pn or "?"
        show_hard_limit_dialog(main_window, pn)

    except Exception as e:
        main_window._recovery_in_progress = False
        main_window.on_log(tr("hard_limit_log_fail").replace("{err}", str(e)))


def update_jog_buttons_state(main_window):
    """Update jog buttons enabled state considering directional locks and overall UI lock."""
    base_enabled = main_window.controller.is_connected() and not main_window.controller.is_streaming() and not main_window.controller._ui_locked
    for (axis, direction), btn in main_window.control_page.jog_button_map.items():
        if (axis, direction) in main_window._locked_jog_directions:
            btn.setEnabled(False)
        else:
            btn.setEnabled(base_enabled)


def check_sensor_unlock(main_window, axis: str, locked_direction: str):
    """Check if the sensor for a locked direction has cleared.

    Called ~500ms after a jog in the opposite direction. If the Pn
    field no longer contains the axis letter, unlock the button.
    """
    pn = ""
    if main_window.worker._last_status:
        pn = main_window.worker._last_status.get("pn", "")
    if axis not in pn.upper():
        # Sensor is no longer active → unlock
        if (axis, locked_direction) in main_window._locked_jog_directions:
            main_window._locked_jog_directions.discard((axis, locked_direction))
            main_window.update_jog_buttons_state()
            main_window.on_log(f"🔓 ปลดล็อคปุ่มทิศทาง {axis}{locked_direction} อัตโนมัติ (เซ็นเซอร์ไม่ตรวจจับแล้ว)")
    # else: sensor still triggered, keep locked


def _compute_backoff_direction(main_window, axis: str) -> str:
    """Determine the direction to back off from a triggered limit switch.

    Returns '+' or '-' as a string prefix for the jog command.
    Uses MPos compared to soft limits / machine origin to decide.
    """
    mpos = None
    if main_window.worker._last_status:
        mpos = main_window.worker._last_status.get("mpos")

    s = main_window.settings
    axis_idx = {"X": 0, "Y": 1, "Z": 2}.get(axis.upper(), 0)
    limits = [(s.xmin, s.xmax), (s.ymin, s.ymax), (s.zmin, s.zmax)]
    lo, hi = limits[axis_idx]

    if mpos:
        pos = mpos[axis_idx]
        # If soft limits are meaningful (not default ±1000)
        has_real_limits = not (lo == -1000.0 and hi == 1000.0)
        if has_real_limits:
            mid = (lo + hi) / 2.0
            # If closer to max → back off negative; closer to min → back off positive
            return "-" if pos > mid else "+"
        else:
            # Default heuristic: most GRBL machines have negative workspace
            # If MPos ≤ 0 → at home/negative end → back off positive
            # If MPos > 0 → at positive end → back off negative
            return "+" if pos <= 0 else "-"

    # No position data — default to positive (safest for negative-workspace machines)
    return "+"
