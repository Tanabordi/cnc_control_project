"""Signal handlers for worker events."""

from PySide6.QtWidgets import QMessageBox, QPushButton
from PySide6.QtCore import QTimer

from core.utils import _set_enabled
from core.i18n import tr


def _home_buttons(cp):
    """Return list of all home buttons from a control page."""
    return [cp.home_all_btn, cp.home_x_btn, cp.home_y_btn, cp.home_z_btn]


def setup_signal_handlers(main_window):
    """Connect worker signals to handler methods in MainWindow."""
    worker = main_window.worker
    
    worker.status.connect(main_window.on_status)
    worker.log.connect(main_window.on_log)
    worker.connected.connect(main_window.on_connected)
    worker.stream_state.connect(main_window.on_stream_state)
    worker.line_sent.connect(main_window._on_line_sent)
    worker.line_ack.connect(main_window._on_line_ack)
    worker.line_error_at.connect(main_window._on_line_error_at)
    worker.alarm.connect(main_window.on_alarm)
    worker.grbl_reset.connect(main_window.on_grbl_reset)
    worker.stream_progress.connect(main_window._on_stream_progress)


def on_connected(main_window, ok: bool):
    """Handle connection state change."""
    main_window.controller.set_connected(ok)
    cp = main_window.control_page

    cp.connect_btn.setEnabled(not ok)
    cp.disconnect_btn.setEnabled(ok)

    _set_enabled(_home_buttons(cp) + [cp.zero_btn,
                  cp.go_zero_btn, cp.go_work_zero_btn, cp.reset_btn, cp.estop_btn], ok)
    cp.unlock_btn.setEnabled(False)
    main_window.run_page.unlock_btn.setEnabled(False)
    _set_enabled(cp.jog_buttons, ok)
    _set_enabled([cp.load_points_gcode_btn, cp.load_csv_pcb_btn, cp.capture_btn,
                  cp.update_btn, cp.delete_btn, cp.clear_btn,
                  cp.preview3d_btn, cp.move_btn, cp.export_gcode_btn, cp.export_panel_btn,
                  cp.import_vector_btn, cp.import_image_btn], ok)

    cp.update_btn.setEnabled(False)
    cp.console_send_btn.setEnabled(ok)
    cp.state_lbl.setText("Port opened" if ok else "Disconnected")
    main_window.run_page.set_connected(ok)
    main_window.run_page.reset_btn.setEnabled(ok)
    main_window.settings_page.set_connected(ok)

    if ok and main_window.settings.auto_unlock_after_connect:
        import time as _time
        main_window.controller._last_auto_x_time = _time.time()
        main_window.worker.send_line("$X")
        main_window.on_log("Auto unlock after connect ($X).")


def on_stream_state(main_window, st: str):
    """Handle stream state changes."""
    main_window.controller.set_streaming(st in ("running", "paused"))
    locked = main_window.controller.is_streaming()
    cp = main_window.control_page
    main_window.update_jog_buttons_state()
    _set_enabled([cp.move_btn, cp.load_points_gcode_btn, cp.load_csv_pcb_btn, cp.capture_btn,
                  cp.update_btn, cp.delete_btn, cp.clear_btn,
                  cp.export_gcode_btn, cp.export_panel_btn, cp.preview3d_btn,
                  cp.import_vector_btn, cp.import_image_btn], main_window.controller.is_connected() and (not locked))
    if locked:
        cp.update_btn.setEnabled(False)
    main_window.run_page.set_stream_state(st)


def on_status(main_window, payload: dict):
    """Handle status updates from machine."""
    state = payload.get("state") or "-"

    wx, wy, wz = payload["wpos"]
    mpos = payload.get("mpos")
    mx, my, mz = mpos if mpos else (wx, wy, wz)

    pn = payload.get("pn") or ""
    for page in (main_window.control_page, main_window.run_page):
        page.wpos_x.setText(f"{wx:.3f}")
        page.wpos_y.setText(f"{wy:.3f}")
        page.wpos_z.setText(f"{wz:.3f}")
        page.mpos_x.setText(f"{mx:.3f}")
        page.mpos_y.setText(f"{my:.3f}")
        page.mpos_z.setText(f"{mz:.3f}")
        page.pn_lbl.setText(pn if pn else "-")

    main_window.run_page.update_tool_position(wx, wy)

    # ── If recovery is in progress, only update position — skip all alarm logic ──
    if getattr(main_window, '_recovery_in_progress', False):
        for page in (main_window.control_page, main_window.run_page):
            page.state_lbl.setText(f"{state} [RECOVERING]")
        return

    # --- Software Limit Protection ---
    # If a limit switch is hit but GRBL is NOT in Alarm state (e.g. $21=0),
    # we force it into Alarm mode and immediately stop motion.
    if pn and not state.lower().startswith("alarm") and not main_window._hard_limit_dialog_shown:
        main_window.on_log(f"⚠ Software Limit Triggered (Pn: {pn}) - หยุดการทำงานฉุกเฉิน!")
        if main_window.controller.is_streaming() or state.lower() in ("run", "jog"):
            main_window.worker.send_reset()
        state = "Alarm"

    is_alarm = state.lower().startswith("alarm")
    ui_locked = main_window.controller._ui_locked

    # If UI is locked (after Reset/E-STOP), override the displayed state
    if ui_locked:
        for page in (main_window.control_page, main_window.run_page):
            page.state_lbl.setText(f"{state} [LOCKED]")
        # Keep unlock button enabled, keep jog/home disabled
        main_window.control_page.unlock_btn.setEnabled(True)
        main_window.run_page.unlock_btn.setEnabled(True)
        cp = main_window.control_page
        _set_enabled(cp.jog_buttons, False)
        _set_enabled(_home_buttons(cp), False)
        return

    # Normal (unlocked) state handling
    for page in (main_window.control_page, main_window.run_page):
        page.state_lbl.setText(state)

    main_window.control_page.unlock_btn.setEnabled(is_alarm)
    main_window.run_page.unlock_btn.setEnabled(is_alarm)

    if is_alarm and not main_window.controller._alarm_active:
        # Alarm first appeared via status report
        main_window.controller.handle_alarm(state)
        _set_enabled(main_window.control_page.jog_buttons, False)
        _set_enabled(_home_buttons(main_window.control_page), False)
        for page in (main_window.control_page, main_window.run_page):
            page.state_lbl.setText(state)

        # If we have Pn data AND no recovery was triggered yet, trigger it
        if pn and not main_window._hard_limit_dialog_shown:
            main_window._last_alarm_was_hard_limit = True
            main_window._hard_limit_pn = pn
            main_window._hard_limit_dialog_shown = True
            axes_str = pn
            log_msg = tr("hard_limit_log_hit").replace("{axes}", axes_str)
            main_window.on_log(log_msg)
            QTimer.singleShot(100, lambda: main_window.do_hard_limit_recovery(pn))

    elif is_alarm and main_window.controller._alarm_active:
        # Alarm still active — check if we now have Pn data we didn't have before
        if pn and not main_window._hard_limit_dialog_shown:
            main_window._last_alarm_was_hard_limit = True
            main_window._hard_limit_pn = pn
            main_window._hard_limit_dialog_shown = True
            axes_str = pn
            log_msg = tr("hard_limit_log_hit").replace("{axes}", axes_str)
            main_window.on_log(log_msg)
            QTimer.singleShot(100, lambda: main_window.do_hard_limit_recovery(pn))

    elif main_window.controller._alarm_active and not is_alarm:
        # Alarm cleared — but only restore controls if UI is NOT locked
        # (recovery sets _ui_locked=True, so we must not reset guards here)
        if main_window.controller._ui_locked or getattr(main_window, '_recovery_in_progress', False):
            # Alarm state cleared by GRBL, but UI is still locked from recovery.
            # Just clear alarm_active, keep everything else guarded.
            main_window.controller._alarm_active = False
        else:
            main_window.controller._alarm_active = False
            main_window._last_alarm_was_hard_limit = False
            main_window._hard_limit_pn = ""
            main_window._hard_limit_dialog_shown = False
            main_window.update_jog_buttons_state()
            _set_enabled(_home_buttons(main_window.control_page), True)


def on_log(main_window, msg: str):
    """Handle log messages."""
    main_window.control_page.append_log(msg)
    main_window.run_page.append_log(msg)
    main_window.settings_page.append_log(msg)


def _on_line_sent(main_window, idx: int, cmd: str):
    """Handle line sent event."""
    main_window.run_page.update_cmd_row_sent(idx)


def _on_line_ack(main_window, idx: int):
    """Handle line ack event."""
    main_window.run_page.update_cmd_row_ack(idx)


def _on_line_error_at(main_window, idx: int, msg: str):
    """Handle line error event."""
    main_window.run_page.update_cmd_row_error(idx, msg)


def _on_stream_progress(main_window, done: int, total: int):
    """Handle stream progress update."""
    main_window.run_page.update_progress(done, total)


def on_alarm(main_window, msg: str, pn_axes: str = ""):
    """Handle alarm signal from worker — with hard-limit direction awareness.

    This is called when worker emits alarm signal (ALARM:N line received).
    msg will be something like "ALARM:1", "ALARM:2", etc.
    """
    # ── If recovery is already in progress, ignore duplicate ALARM signals ──
    if getattr(main_window, '_recovery_in_progress', False):
        return

    main_window.controller.handle_alarm(msg)

    # Detect hard limit: ALARM:1 is always hard limit in GRBL
    is_hard_limit = msg.upper().startswith("ALARM:1") or msg.upper() == "ALARM:1"
    main_window._last_alarm_was_hard_limit = is_hard_limit

    for page in (main_window.control_page, main_window.run_page):
        page.state_lbl.setText(msg)

    # Disable ALL jog buttons and home buttons immediately (safety first)
    _set_enabled(main_window.control_page.jog_buttons, False)
    _set_enabled(_home_buttons(main_window.control_page), False)

    if is_hard_limit:
        # Try to get Pn from signal args, or from worker's last known value
        pn = pn_axes or main_window.worker._last_pn or ""
        main_window._hard_limit_pn = pn

        if pn:
            # We have axis info right now — start auto-recovery immediately
            main_window._hard_limit_dialog_shown = True
            axes_str = pn
            log_msg = tr("hard_limit_log_hit").replace("{axes}", axes_str)
            main_window.on_log(log_msg)
            QTimer.singleShot(100, lambda: main_window.do_hard_limit_recovery(pn))
        else:
            # No Pn data yet — wait for it from status reports (on_status will handle)
            main_window._hard_limit_dialog_shown = False
            main_window.on_log("⚠ ALARM:1 (Hard Limit) detected — waiting for axis data from Pn:...")
            # Set a fallback timer: if Pn never arrives, start recovery with "?" after 3 seconds
            QTimer.singleShot(3000, lambda: _fallback_hard_limit_recovery(main_window))
    else:
        main_window._hard_limit_pn = ""
        main_window._hard_limit_dialog_shown = False
        main_window.on_log(f"{msg} — กด Unlock ($X) เพื่อ clear")


def _fallback_hard_limit_recovery(main_window):
    """Fallback: trigger recovery with '?' if Pn data never arrived after ALARM:1."""
    if not main_window._last_alarm_was_hard_limit:
        return  # alarm was already cleared
    if getattr(main_window, '_hard_limit_dialog_shown', False):
        return  # recovery was already triggered with proper axis data
    if getattr(main_window, '_recovery_in_progress', False):
        return  # recovery already running

    main_window._hard_limit_dialog_shown = True
    # Try one more time to get Pn from worker
    pn = main_window._hard_limit_pn or main_window.worker._last_pn or "?"
    axes_str = pn if pn else "?"
    log_msg = tr("hard_limit_log_hit").replace("{axes}", axes_str)
    main_window.on_log(log_msg)
    main_window.do_hard_limit_recovery(pn)

def _show_hard_limit_dialog(main_window, axes_str: str):
    """Show QMessageBox.critical informing user that auto-recovery is done and UI is locked."""
    dlg = QMessageBox(main_window)
    dlg.setIcon(QMessageBox.Warning)
    dlg.setWindowTitle(tr("hard_limit_title"))
    dlg.setText(tr("hard_limit_msg").replace("{axes}", axes_str))

    # Custom buttons
    unlock_btn = dlg.addButton(tr("hard_limit_unlock"), QMessageBox.AcceptRole)
    unlock_btn.setStyleSheet(
        "QPushButton { background-color: #0d6efd; color: white; font-weight: bold; "
        "padding: 8px 16px; font-size: 13px; }"
        "QPushButton:hover { background-color: #0b5ed7; }"
    )

    dlg.exec()

    if dlg.clickedButton() == unlock_btn:
        main_window._do_unlock()


def on_grbl_reset(main_window):
    """Handle GRBL reset event."""
    was_hard_limit = getattr(main_window, '_last_alarm_was_hard_limit', False)
    was_alarm = main_window.controller._alarm_active
    ui_locked = main_window.controller._ui_locked
    
    # Protect hard limit state if we are currently recovering
    is_recovering = (getattr(main_window, '_hard_limit_dialog_shown', False) or
                     getattr(main_window, '_recovery_in_progress', False))
    
    if not is_recovering:
        main_window.controller._alarm_active = False
        main_window._last_alarm_was_hard_limit = False
        main_window._hard_limit_pn = ""
        main_window._hard_limit_dialog_shown = False
        main_window._locked_jog_directions.clear()

    if was_alarm and not ui_locked and not is_recovering:
        main_window.update_jog_buttons_state()
        _set_enabled(_home_buttons(main_window.control_page), True)
        if not main_window.controller.is_streaming():
            main_window.on_stream_state("idle")

    main_window.controller.handle_grbl_reset()

    if ui_locked:
        # Keep unlock button active, keep jog/home locked
        main_window.control_page.unlock_btn.setEnabled(True)
        main_window.run_page.unlock_btn.setEnabled(True)
        main_window.update_jog_buttons_state()
        _set_enabled(_home_buttons(main_window.control_page), False)
        main_window.on_log("⚠ เครื่องถูกล็อคโดย UI — กด Unlock ($X) เพื่อปลดล็อค")
    else:
        main_window.control_page.unlock_btn.setEnabled(False)
        main_window.run_page.unlock_btn.setEnabled(False)
