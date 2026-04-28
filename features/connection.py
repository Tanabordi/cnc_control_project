"""Connection management — Serial / TCP / Simulator.

Extracted from gui/app.py to keep MainWindow slim.
"""

import socket

from PySide6.QtWidgets import QMessageBox, QApplication
from PySide6.QtCore import Qt

from core.settings import save_settings


def refresh_ports(main_window):
    """Refresh list of available serial ports."""
    import serial.tools.list_ports
    main_window.control_page.port_box.clear()
    ports = [p.device for p in serial.tools.list_ports.comports()]
    ports.append("SIMULATOR")
    main_window.control_page.port_box.addItems(ports)
    main_window.on_log(f"Found ports: {', '.join(ports) if ports else '(none)'}")


def do_connect(main_window):
    """Connect to serial port or TCP socket."""
    cp = main_window.control_page
    if cp.radio_serial.isChecked():
        # Serial Connection
        port = cp.port_box.currentText().strip()
        if not port:
            QMessageBox.warning(main_window, "No Port", "Please select a COM port.")
            return
        main_window.settings.connection_type = "serial"
        main_window.settings.last_port = port
        save_settings(main_window.settings)
        ok = main_window.worker.connect_serial(port, int(main_window.settings.baud))
    else:
        # TCP Connection
        ip = cp.ip_input.text().strip()
        if not ip:
            QMessageBox.warning(main_window, "Invalid Input", "Please enter a valid IP address.")
            return
        port = cp.port_tcp_input.value()
        main_window.settings.connection_type = "tcp"
        main_window.settings.ip_address = ip
        main_window.settings.tcp_port = port
        save_settings(main_window.settings)
        ok = main_window.worker.connect_tcp(ip, port)

    if ok and not main_window.worker.isRunning():
        main_window.worker.start()


def test_tcp_connection(main_window):
    """Test TCP connection without starting the main worker loop."""
    ip = main_window.control_page.ip_input.text().strip()
    port = main_window.control_page.port_tcp_input.value()
    if not ip:
        QMessageBox.warning(main_window, "Invalid Input", "Please enter a valid IP address.")
        return

    main_window.on_log(f"Testing TCP connection to {ip}:{port}...")
    QApplication.processEvents()  # Force UI to update log before blocking
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3.0)
            s.connect((ip, port))
        main_window.on_log("Test Connection OK: บอร์ดตอบสนองสำเร็จ!")
        QMessageBox.information(main_window, "Test TCP", f"Connection to {ip}:{port} successful!")
    except Exception as e:
        main_window.on_log(f"Test Connection Failed: {e}")
        main_window.on_log("โปรดตรวจสอบว่าเลข Port ถูกต้องตามการตั้งค่าของบอร์ด หรือตรวจสอบการเชื่อมต่อ WiFi/LAN")
        QMessageBox.critical(main_window, "Test TCP", f"Connection failed:\n{e}\n\nโปรดตรวจสอบว่าเลข Port ถูกต้อง")
    finally:
        QApplication.restoreOverrideCursor()


def do_disconnect(main_window):
    """Disconnect from serial port."""
    main_window.worker.disconnect_serial()


def scan_network(main_window):
    """Open network scan dialog to discover CNC boards on the local network."""
    from features.network_scanner import NetworkScanDialog

    current_port = main_window.control_page.port_tcp_input.value()
    main_window.on_log(f"🔍 Scanning network for CNC boards (ports: 8080, 23, 81, {current_port})...")

    dlg = NetworkScanDialog(current_port=current_port, parent=main_window)
    if dlg.exec() == NetworkScanDialog.Accepted:
        ip, port = dlg.get_selected()
        if ip:
            main_window.control_page.ip_input.setText(ip)
            main_window.control_page.port_tcp_input.setValue(port)

            # Switch to TCP mode if not already
            main_window.control_page.radio_tcp.setChecked(True)

            # Save to settings
            main_window.settings.connection_type = "tcp"
            main_window.settings.ip_address = ip
            main_window.settings.tcp_port = port
            save_settings(main_window.settings)

            main_window.on_log(f"✅ Selected: {ip}:{port} — กด Connect เพื่อเชื่อมต่อ")

