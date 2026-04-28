"""Hard Limit Auto-Recovery logic.

Extracted from gui/app.py to keep MainWindow slim.
Contains the multi-step recovery sequence: $X → $21=0 → jog back → finalize.
"""

from PySide6.QtCore import QTimer
from core.i18n import tr


_BACKOFF_STEP_MM = 2      # ระยะถอยแต่ละรอบ (mm)
_BACKOFF_MAX_MM = 50      # ระยะถอยสูงสุด (mm)
_SAFETY_MARGIN_MM = 3     # ถอยเพิ่มหลัง clear sensor (mm)
_STEP_WAIT_MS = 800       # รอ jog เสร็จแต่ละรอบ (ms)
_UNLOCK_RETRY_MAX = 5     # จำนวนครั้งสูงสุดที่ลอง unlock + $21=0


def do_hard_limit_recovery(main_window, pn: str):
    """Execute auto-recovery sequence: $X+$21=0 → iterative jog back → finalize.

    Guard: only one recovery can run at a time.
    """
    if main_window._recovery_in_progress:
        return
    main_window._recovery_in_progress = True
    main_window._hard_limit_dialog_shown = True

    main_window.on_log(tr("hard_limit_log_start"))

    try:
        # Determine backoff directions and lock the crash direction
        # Skip axes already locked from previous recovery
        jog_axes_dirs = []
        already_locked_axes = {a for a, _ in main_window._locked_jog_directions}
        for axis in "XYZ":
            if axis in pn.upper() and axis not in already_locked_axes:
                backoff_dir = _compute_backoff_direction(main_window, axis)
                jog_axes_dirs.append((axis, backoff_dir))

                crash_dir = "-" if backoff_dir == "+" else "+"
                main_window._locked_jog_directions.add((axis, crash_dir))
                main_window.on_log(f"🔒 ล็อคปุ่มทิศทาง {axis}{crash_dir} ชั่วคราวป้องกันชนซ้ำ")

        main_window._recovery_total_backoff = 0
        main_window._recovery_locked_directions = set(main_window._locked_jog_directions)
        main_window.update_jog_buttons_state()

        # Disable alarm pause in worker so we keep polling during recovery
        main_window.worker._alarm_pause_until = 0.0
        main_window.worker._recovery_mode = True

        # Step 1: Aggressively send $X + $21=0 together (no delay!)
        # Send as raw bytes in one write to minimize gap for GRBL re-alarm
        main_window.worker._write_raw(b"$X\n$21=0\n")
        main_window.on_log("> $X + $21=0 (Unlock + Hard limits OFF — combined)")

        # Step 2: After 500ms, verify GRBL accepted and start backoff
        QTimer.singleShot(500, lambda: _verify_unlock_and_start(
            main_window, jog_axes_dirs, attempt=1
        ))

    except Exception as e:
        main_window._recovery_in_progress = False
        main_window.worker._recovery_mode = False
        main_window.on_log(tr("hard_limit_log_fail").replace("{err}", str(e)))


def _verify_unlock_and_start(main_window, jog_axes_dirs: list, attempt: int):
    """Verify GRBL accepted $X+$21=0, retry if still in alarm."""
    state = ""
    if main_window.worker._last_status:
        state = main_window.worker._last_status.get("state", "").lower()

    if "alarm" in state:
        if attempt >= _UNLOCK_RETRY_MAX:
            main_window.on_log(f"❌ ไม่สามารถ unlock GRBL ได้หลัง {_UNLOCK_RETRY_MAX} ครั้ง — ลอง Reset เครื่อง")
            main_window._recovery_in_progress = False
            main_window.worker._recovery_mode = False
            return

        main_window.on_log(f"⚠ GRBL ยัง Alarm อยู่ — ลองอีกครั้ง ({attempt}/{_UNLOCK_RETRY_MAX})")
        # Retry: send $X + $21=0 again
        main_window.worker._write_raw(b"$X\n$21=0\n")
        QTimer.singleShot(500, lambda: _verify_unlock_and_start(
            main_window, jog_axes_dirs, attempt + 1
        ))
        return

    # GRBL is unlocked — start backoff
    main_window.on_log(f"✅ GRBL unlocked สำเร็จ (attempt {attempt})")

    if jog_axes_dirs:
        QTimer.singleShot(200, lambda: _recovery_backoff_loop(main_window, jog_axes_dirs))
    else:
        QTimer.singleShot(1500, lambda: _recovery_finalize(main_window))


def _recovery_backoff_loop(main_window, jog_axes_dirs: list):
    """Iteratively jog back until sensor clears or max backoff is reached."""
    # Abort if disconnected during recovery
    if not main_window.controller.is_connected():
        main_window.on_log("❌ Connection lost during recovery — aborting")
        main_window._recovery_in_progress = False
        main_window.worker._recovery_mode = False
        return

    # Force status poll
    main_window.worker._write_raw(b"?")

    # Before each jog, send $X in case GRBL re-alarmed (switch bounce)
    main_window.worker._write_raw(b"$X\n")

    pn = ""
    if main_window.worker._last_status:
        pn = main_window.worker._last_status.get("pn", "").upper()

    still_active = any(axis in pn for axis, _ in jog_axes_dirs)

    if not still_active and main_window._recovery_total_backoff > 0:
        # Sensor cleared -> safety margin backoff
        jog_parts = [f"{axis}{direction}{_SAFETY_MARGIN_MM:.3f}" for axis, direction in jog_axes_dirs]
        jog_cmd = f"$J=G91 {' '.join(jog_parts)} F500"
        main_window.worker.send_line(jog_cmd)
        main_window.on_log(f"> {jog_cmd} (Safety margin {_SAFETY_MARGIN_MM}mm)")
        QTimer.singleShot(1500, lambda: _recovery_finalize(main_window))
        return

    if main_window._recovery_total_backoff >= _BACKOFF_MAX_MM:
        main_window.on_log(f"⚠ หยุดการถอย (ถอยเกิน {_BACKOFF_MAX_MM}mm แล้วเซ็นเซอร์ยังทำงานอยู่)")
        _recovery_finalize(main_window)
        return

    # Back off one step
    jog_parts = [f"{axis}{direction}{_BACKOFF_STEP_MM:.3f}" for axis, direction in jog_axes_dirs]
    jog_cmd = f"$J=G91 {' '.join(jog_parts)} F500"
    main_window.worker.send_line(jog_cmd)
    main_window._recovery_total_backoff += _BACKOFF_STEP_MM
    main_window.on_log(f"> {jog_cmd} (Iterative backoff: {main_window._recovery_total_backoff}mm)")

    QTimer.singleShot(_STEP_WAIT_MS, lambda: _recovery_backoff_loop(main_window, jog_axes_dirs))


def _recovery_finalize(main_window):
    """Recovery final step: show dialog. $21 stays OFF until user jogs away."""
    try:
        main_window.worker._write_raw(b"$X\n")
        main_window.on_log("> $X (Unlock GRBL after backoff)")

        main_window.controller._alarm_active = False
        main_window.controller._ui_locked = True
        main_window._last_alarm_was_hard_limit = False
        main_window._hard_limit_pn = ""

        main_window._recovery_in_progress = False
        main_window._recovery_completed = True
        main_window.worker._recovery_mode = False

        # IMPORTANT: Keep _locked_jog_directions — don't clear them!
        # They will be cleared only when user jogs away and we verify via $21=1 test
        main_window.update_jog_buttons_state()
        main_window.on_log(tr("hard_limit_log_done"))

        if main_window._locked_jog_directions:
            locked_str = ", ".join(f"{a}{d}" for a, d in main_window._locked_jog_directions)
            main_window.on_log(f"🔒 ปุ่มที่ยังล็อค: {locked_str} — jog ทิศตรงข้ามเพื่อปลดล็อค")

        from features.hard_limit.dialog import show_hard_limit_dialog
        pn = main_window.worker._last_pn or "?"
        show_hard_limit_dialog(main_window, pn)

    except Exception as e:
        main_window._recovery_in_progress = False
        main_window.worker._recovery_mode = False
        main_window.on_log(tr("hard_limit_log_fail").replace("{err}", str(e)))


def update_jog_buttons_state(main_window):
    """Update jog buttons enabled state considering directional locks and overall UI lock."""
    base_enabled = (main_window.controller.is_connected()
                    and not main_window.controller.is_streaming()
                    and not main_window.controller._ui_locked)

    for (axis, direction), btn in main_window.control_page.jog_button_map.items():
        if (axis, direction) in main_window._locked_jog_directions:
            btn.setEnabled(False)
        else:
            btn.setEnabled(base_enabled)


def check_sensor_unlock(main_window, axis: str, locked_direction: str):
    """Check if sensor has cleared by trying to re-enable $21=1.

    Instead of relying on Pn (unreliable when $21=0), we try to
    re-enable hard limits. If GRBL doesn't alarm within 1 second,
    the sensor is truly clear → unlock buttons.

    This is called after user jogs in the opposite direction.
    """
    if getattr(main_window, '_recovery_in_progress', False):
        return

    # Don't check if this axis is no longer locked
    if (axis, locked_direction) not in main_window._locked_jog_directions:
        return

    main_window.on_log(f"🔍 ตรวจสอบเซ็นเซอร์แกน {axis}...")

    # Set a flag so we can catch any ALARM:1 that results from re-enabling $21=1
    main_window._sensor_test_in_progress = True
    main_window._sensor_test_axis = axis
    main_window._sensor_test_alarmed = False

    # Try re-enabling hard limits
    main_window.worker.send_line("$21=1")
    main_window.on_log("> $21=1 (ทดสอบว่าเซ็นเซอร์ clear หรือยัง)")

    # After 1 second, check if alarm was triggered
    QTimer.singleShot(1000, lambda: _sensor_test_result(main_window, axis, locked_direction))


def _sensor_test_result(main_window, axis: str, locked_direction: str):
    """Check the result of the $21=1 test."""
    main_window._sensor_test_in_progress = False

    if main_window._sensor_test_alarmed:
        # Sensor still pressed → alarm was triggered → re-disable hard limits
        main_window.on_log(f"⚠ เซ็นเซอร์แกน {axis} ยังทำงานอยู่ — ล็อคปุ่มต่อ")
        main_window.worker._write_raw(b"$X\n$21=0\n")
        # Keep locked
        return

    # No alarm → sensor is clear!
    unlocked = False
    for d in ("+", "-"):
        if (axis, d) in main_window._locked_jog_directions:
            main_window._locked_jog_directions.discard((axis, d))
            unlocked = True

    if unlocked:
        main_window.update_jog_buttons_state()
        main_window.on_log(f"🔓 ปลดล็อคปุ่มทิศทาง {axis} (เซ็นเซอร์ clear แล้ว)")

    # If ALL directions are now unlocked, fully restore
    if not main_window._locked_jog_directions:
        main_window.on_log("> $21=1 (Hard limits ON) — เซ็นเซอร์ทุกแกนปลอดภัยแล้ว ✅")
        main_window._hard_limit_dialog_shown = False
        main_window._recovery_completed = False


def _compute_backoff_direction(main_window, axis: str) -> str:
    """Determine the direction to back off from a triggered limit switch.

    Uses MPos to determine which end of travel we're at.
    For standard GRBL CNC machines:
    - Home is at MPos ≈ 0 (the positive end for X/Y on many machines)
    - Work area is in the negative direction
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
        has_real_limits = not (lo == -1000.0 and hi == 1000.0)
        if has_real_limits:
            mid = (lo + hi) / 2.0
            return "-" if pos > mid else "+"
        else:
            # Heuristic: if near 0 or positive → at home/limit end → back off negative
            # If far negative → at other end → back off positive
            return "-" if pos > -5 else "+"

    # No position data — default to positive
    return "+"
