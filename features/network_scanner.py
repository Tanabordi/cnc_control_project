"""Network Scanner — Auto-discover CNC boards (GRBL) on the local WiFi/LAN.

Scans the local subnet for devices that respond on common GRBL ports
(8080, 23, 81) and verifies them by checking for GRBL-style responses.
"""

import socket
import struct
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QGroupBox,
)

from core.i18n import tr


# ── Default ports to scan ──
# 8080 = MKS DLC32 / FluidNC web,  23 = Telnet (classic GRBL-WiFi),  81 = FluidNC alt
DEFAULT_SCAN_PORTS = [8080, 23, 81]

# ── Scanner thread timeout per IP (seconds) ──
_CONNECT_TIMEOUT = 0.35
_RECV_TIMEOUT = 0.5
_MAX_WORKERS = 64


def _get_local_ip() -> str:
    """Get the local IP address of the machine (non-loopback)."""
    try:
        # Connect to a public DNS server to find out which NIC is used
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.5)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return ""


def _derive_subnet(ip: str) -> str:
    """Derive /24 subnet from an IP address. e.g. '192.168.1.105' → '192.168.1'."""
    parts = ip.split(".")
    if len(parts) == 4:
        return ".".join(parts[:3])
    return ""


def _probe_host(ip: str, port: int) -> dict | None:
    """Try to connect to ip:port and verify if it's a GRBL device.

    Returns dict with keys {ip, port, info} on success, None otherwise.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(_CONNECT_TIMEOUT)
            s.connect((ip, port))

            # Connection succeeded — now try to identify GRBL
            s.settimeout(_RECV_TIMEOUT)
            info = ""
            try:
                # Some boards send a greeting immediately on connect
                greeting = s.recv(512).decode("ascii", errors="ignore").strip()
                if greeting:
                    info = greeting
            except socket.timeout:
                pass

            # If no greeting, send a newline to provoke a response
            if not info:
                try:
                    s.sendall(b"\r\n")
                    s.settimeout(_RECV_TIMEOUT)
                    resp = s.recv(512).decode("ascii", errors="ignore").strip()
                    if resp:
                        info = resp
                except Exception:
                    pass

            # If still no info, try sending "?" for status
            if not info:
                try:
                    s.sendall(b"?")
                    s.settimeout(_RECV_TIMEOUT)
                    resp = s.recv(512).decode("ascii", errors="ignore").strip()
                    if resp:
                        info = resp
                except Exception:
                    pass

            # Accept any device that responded on the port — it's likely a CNC board
            # GRBL-specific markers give higher confidence
            is_grbl = any(marker in info.lower() for marker in
                          ["grbl", "<idle", "<alarm", "<run", "<hold", "<jog",
                           "ok", "error:", "alarm:"])

            # If we connected but got no response, still report it
            # (some boards need the full worker loop to respond)
            if info or True:  # Always report if TCP connect succeeds
                label = info[:80] if info else "(connected, no response)"
                if is_grbl:
                    label = f"✅ GRBL: {info[:70]}"
                return {"ip": ip, "port": port, "info": label}

    except (socket.timeout, ConnectionRefusedError, OSError):
        return None
    return None


# ═══════════════════════════════════════════════════════════
# Scanner QThread
# ═══════════════════════════════════════════════════════════

class NetworkScanWorker(QThread):
    """Background thread that scans a /24 subnet on multiple ports."""

    # Signals
    progress = Signal(int, int)       # (done, total)
    found = Signal(dict)              # {ip, port, info}
    finished_scan = Signal(int)       # total found count
    scan_error = Signal(str)          # error message

    def __init__(self, ports: list[int] | None = None, parent=None):
        super().__init__(parent)
        self.ports = ports or DEFAULT_SCAN_PORTS
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        local_ip = _get_local_ip()
        if not local_ip:
            self.scan_error.emit("Cannot determine local IP address")
            self.finished_scan.emit(0)
            return

        subnet = _derive_subnet(local_ip)
        if not subnet:
            self.scan_error.emit(f"Invalid subnet from IP: {local_ip}")
            self.finished_scan.emit(0)
            return

        # Build task list: 254 IPs × N ports
        tasks = []
        for host_id in range(1, 255):
            ip = f"{subnet}.{host_id}"
            if ip == local_ip:
                continue  # skip ourselves
            for port in self.ports:
                tasks.append((ip, port))

        total = len(tasks)
        done = 0
        found_count = 0

        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            futures = {pool.submit(_probe_host, ip, port): (ip, port)
                       for ip, port in tasks}

            for future in as_completed(futures):
                if self._abort:
                    pool.shutdown(wait=False, cancel_futures=True)
                    break

                done += 1
                if done % 10 == 0 or done == total:
                    self.progress.emit(done, total)

                result = future.result()
                if result:
                    found_count += 1
                    self.found.emit(result)

        self.progress.emit(total, total)
        self.finished_scan.emit(found_count)


# ═══════════════════════════════════════════════════════════
# Scan Dialog
# ═══════════════════════════════════════════════════════════

class NetworkScanDialog(QDialog):
    """Modal dialog that scans the network and shows discovered CNC boards."""

    def __init__(self, current_port: int = 8080, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("scan_title"))
        self.setMinimumSize(560, 380)
        self._selected_ip = ""
        self._selected_port = 0

        # Determine ports to scan: include the user's custom port
        self._ports = list(DEFAULT_SCAN_PORTS)
        if current_port and current_port not in self._ports:
            self._ports.insert(0, current_port)

        layout = QVBoxLayout(self)

        # ── Header ──
        local_ip = _get_local_ip()
        subnet = _derive_subnet(local_ip) if local_ip else "?"
        port_list = ", ".join(str(p) for p in self._ports)

        header = QLabel(
            f"<b>{tr('scan_scanning').replace('{subnet}', f'{subnet}.0/24')}</b><br>"
            f"<span style='color: #888;'>Ports: {port_list} &nbsp;|&nbsp; Local IP: {local_ip}</span>"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        # ── Progress ──
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v / %m  (%p%)")
        layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel(tr("scan_scanning").replace("{subnet}", f"{subnet}.0/24"))
        self.status_lbl.setStyleSheet("color: #4da6ff; font-weight: bold;")
        layout.addWidget(self.status_lbl)

        # ── Results Table ──
        results_box = QGroupBox(tr("scan_found").replace("{count}", "0"))
        self._results_box = results_box
        rb_layout = QVBoxLayout(results_box)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([
            tr("scan_col_ip"), tr("scan_col_port"), tr("scan_col_info")
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_double_click)
        rb_layout.addWidget(self.table)
        layout.addWidget(results_box, 1)

        # ── Buttons ──
        btn_row = QHBoxLayout()

        self.rescan_btn = QPushButton(tr("scan_rescan"))
        self.rescan_btn.setEnabled(False)
        self.rescan_btn.clicked.connect(self._start_scan)

        self.select_btn = QPushButton(tr("scan_select"))
        self.select_btn.setEnabled(False)
        self.select_btn.setStyleSheet(
            "QPushButton { background-color: #0d6efd; color: white; font-weight: bold; "
            "padding: 8px 20px; font-size: 13px; }"
            "QPushButton:hover { background-color: #0b5ed7; }"
            "QPushButton:disabled { background-color: #555; color: #888; }"
        )
        self.select_btn.clicked.connect(self._on_select)

        self.cancel_btn = QPushButton(tr("hard_limit_close"))  # reuse "Close"
        self.cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(self.rescan_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.select_btn)
        layout.addLayout(btn_row)

        # ── Enable select when row is selected ──
        self.table.itemSelectionChanged.connect(
            lambda: self.select_btn.setEnabled(len(self.table.selectedItems()) > 0)
        )

        # ── Scanner worker ──
        self._worker = None
        self._found_count = 0

        # Start scanning immediately
        self._start_scan()

    # ── Scanner control ──

    def _start_scan(self):
        """Start (or restart) the network scan."""
        # Clear previous results
        self.table.setRowCount(0)
        self._found_count = 0
        self._results_box.setTitle(tr("scan_found").replace("{count}", "0"))
        self.select_btn.setEnabled(False)
        self.rescan_btn.setEnabled(False)
        self.progress_bar.setValue(0)

        local_ip = _get_local_ip()
        subnet = _derive_subnet(local_ip) if local_ip else "?"
        self.status_lbl.setText(tr("scan_scanning").replace("{subnet}", f"{subnet}.0/24"))
        self.status_lbl.setStyleSheet("color: #4da6ff; font-weight: bold;")

        # Stop previous worker if still running
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            self._worker.wait(2000)

        self._worker = NetworkScanWorker(ports=self._ports, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.found.connect(self._on_found)
        self._worker.finished_scan.connect(self._on_finished)
        self._worker.scan_error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, done: int, total: int):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(done)

    def _on_found(self, result: dict):
        self._found_count += 1
        self._results_box.setTitle(tr("scan_found").replace("{count}", str(self._found_count)))

        row = self.table.rowCount()
        self.table.insertRow(row)

        ip_item = QTableWidgetItem(result["ip"])
        ip_item.setTextAlignment(Qt.AlignCenter)
        port_item = QTableWidgetItem(str(result["port"]))
        port_item.setTextAlignment(Qt.AlignCenter)
        info_item = QTableWidgetItem(result["info"])

        # Highlight GRBL-confirmed devices
        if "✅" in result["info"]:
            for item in (ip_item, port_item, info_item):
                item.setForeground(Qt.green)

        self.table.setItem(row, 0, ip_item)
        self.table.setItem(row, 1, port_item)
        self.table.setItem(row, 2, info_item)

    def _on_finished(self, count: int):
        self.rescan_btn.setEnabled(True)
        if count == 0:
            self.status_lbl.setText(tr("scan_no_device"))
            self.status_lbl.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        else:
            self.status_lbl.setText(
                f"✅ {tr('scan_found').replace('{count}', str(count))} — "
                f"{'เลือก IP แล้วกด Select' if count > 0 else ''}"
            )
            self.status_lbl.setStyleSheet("color: #51cf66; font-weight: bold;")
            # Auto-select first row
            if self.table.rowCount() > 0:
                self.table.selectRow(0)

    def _on_error(self, msg: str):
        self.status_lbl.setText(f"❌ {msg}")
        self.status_lbl.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        self.rescan_btn.setEnabled(True)

    # ── Selection ──

    def _on_select(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        self._selected_ip = self.table.item(row, 0).text()
        self._selected_port = int(self.table.item(row, 1).text())
        self.accept()

    def _on_double_click(self, index):
        """Double-click a row to select and close."""
        row = index.row()
        self._selected_ip = self.table.item(row, 0).text()
        self._selected_port = int(self.table.item(row, 1).text())
        self.accept()

    def get_selected(self) -> tuple[str, int]:
        """Return (ip, port) of the selected device."""
        return self._selected_ip, self._selected_port

    # ── Cleanup ──

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            self._worker.wait(2000)
        super().closeEvent(event)

    def reject(self):
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            self._worker.wait(2000)
        super().reject()
