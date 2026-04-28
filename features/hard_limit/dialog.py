"""Hard Limit notification dialog and fallback recovery trigger.

Extracted from features/signal_handlers.py for clear separation.
"""

from PySide6.QtWidgets import QMessageBox
from core.i18n import tr


def show_hard_limit_dialog(main_window, axes_str: str):
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


def fallback_hard_limit_recovery(main_window):
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
