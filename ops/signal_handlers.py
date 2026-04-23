"""Signal handlers for worker events."""

from PySide6.QtWidgets import QMessageBox

from core.utils import _set_enabled


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
    _set_enabled(cp.jog_buttons, main_window.controller.is_connected() and (not locked))
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
        main_window.on_alarm(state)
    elif main_window.controller._alarm_active and not is_alarm:
        main_window.controller._alarm_active = False
        main_window._last_alarm_was_hard_limit = False
        cp = main_window.control_page
        _set_enabled(cp.jog_buttons, True)
        _set_enabled(_home_buttons(cp), True)


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


def on_alarm(main_window, msg: str):
    """Handle alarm state."""
    main_window.controller.handle_alarm(msg)
    main_window._last_alarm_was_hard_limit = "1" in msg
    for page in (main_window.control_page, main_window.run_page):
        page.state_lbl.setText(msg)
    _set_enabled(main_window.control_page.jog_buttons, False)
    _set_enabled(_home_buttons(main_window.control_page), False)
    if main_window._last_alarm_was_hard_limit:
        main_window.on_log("Hard limit! ขยับแกนออกจาก endstop ด้วยมือก่อน แล้วกด Unlock ($X)")
    else:
        main_window.on_log(f"{msg} — กด Unlock ($X) เพื่อ clear")


def on_grbl_reset(main_window):
    """Handle GRBL reset event."""
    was_hard_limit = getattr(main_window, '_last_alarm_was_hard_limit', False)
    was_alarm = main_window.controller._alarm_active
    ui_locked = main_window.controller._ui_locked
    main_window.controller._alarm_active = False
    main_window._last_alarm_was_hard_limit = False

    if was_alarm and not ui_locked:
        cp = main_window.control_page
        _set_enabled(cp.jog_buttons, True)
        _set_enabled(_home_buttons(cp), True)
        if not main_window.controller.is_streaming():
            main_window.on_stream_state("idle")

    main_window.controller.handle_grbl_reset()

    if ui_locked:
        # Keep unlock button active, keep jog/home locked
        main_window.control_page.unlock_btn.setEnabled(True)
        main_window.run_page.unlock_btn.setEnabled(True)
        cp = main_window.control_page
        _set_enabled(cp.jog_buttons, False)
        _set_enabled(_home_buttons(cp), False)
        main_window.on_log("⚠ เครื่องถูกล็อคโดย UI — กด Unlock ($X) เพื่อปลดล็อค")
    else:
        main_window.control_page.unlock_btn.setEnabled(False)
        main_window.run_page.unlock_btn.setEnabled(False)
