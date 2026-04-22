import re
import time
from collections import deque

import serial

from PySide6.QtCore import QThread, Signal, QMutex

from core.utils import parse_xyz, extract_field, extract_state


class GrblWorker(QThread):
    status = Signal(dict)
    log = Signal(str)
    connected = Signal(bool)
    stream_state = Signal(str)      # idle, running, paused, done, error
    line_sent = Signal(int, str)    # (index, command)
    line_ack = Signal(int)          # index acked
    line_error_at = Signal(int, str)  # (index, error)
    grbl_param_line = Signal(str)   # raw "$N=value (desc)" lines from $$
    alarm = Signal(str)             # "ALARM:N" line
    grbl_reset = Signal()           # GRBL sent startup banner (reset occurred)
    stream_progress = Signal(int, int)  # (lines_done, lines_total)

    def __init__(self):
        super().__init__()
        self.ser = None
        self.port = None
        self.baud = 115200
        self._running = False
        self._last_status = None
        self.poll_interval_ms = 150
        self._alarm_pause_until = 0.0  # pause ? polling after ALARM

        self._stream_queue = deque()
        self._streaming = False
        self._stream_paused = False
        self._awaiting_ok = False
        self._current_stream_idx = -1
        self._mutex = QMutex()
        self._stream_total = 0
        self._stream_done = 0

        # --- Simulator ---
        self._is_sim = False
        self._sim_x = 0.0
        self._sim_y = 0.0
        self._sim_z = 0.0
        self._sim_queue = deque()

    def set_poll_interval_ms(self, ms: int):
        self.poll_interval_ms = max(30, int(ms))

    def connect_serial(self, port: str, baud: int = 115200):
        self.port = port
        self.baud = baud

        # --- Simulator bypass ---
        if port == "SIMULATOR":
            self._is_sim = True
            self._sim_x = 0.0
            self._sim_y = 0.0
            self._sim_z = 0.0
            self._sim_queue.clear()
            self.ser = None
            self.connected.emit(True)
            self.log.emit("Connected to SIMULATOR")
            return True

        try:
            self.ser = serial.Serial(port, baudrate=baud, timeout=0.1, write_timeout=0.5)
            time.sleep(0.25)
            try:
                self.ser.write(b"\r\n\r\n")
                time.sleep(0.1)
            except Exception:
                pass
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            self.connected.emit(True)
            self.log.emit(f"Connected: {port} @ {baud}")
            return True
        except Exception as e:
            self.log.emit(f"Connect error: {e}")
            self.connected.emit(False)
            self.ser = None
            return False

    def disconnect_serial(self):
        self._running = False
        self._stop_stream_internal("idle")

        # --- Simulator bypass ---
        if self._is_sim:
            self._is_sim = False
            self._sim_queue.clear()
            self.connected.emit(False)
            self.log.emit("Disconnected from SIMULATOR")
            return

        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass
        self.ser = None
        self.connected.emit(False)
        self.log.emit("Disconnected")

    def _write_raw(self, b: bytes):
        if not self.ser or not self.ser.is_open:
            return
        try:
            self.ser.write(b)
        except Exception as e:
            self.log.emit(f"Write error: {e}")

    def send_line(self, line: str):
        # --- Simulator bypass ---
        if self._is_sim:
            stripped = line.strip()
            self.log.emit(f"> {stripped}")
            self._sim_parse_and_update(stripped)
            self._sim_queue.append(stripped)
            return

        if not self.ser or not self.ser.is_open:
            return
        cmd = (line.strip() + "\n").encode("ascii", errors="ignore")
        try:
            self.ser.write(cmd)
            self.log.emit(f"> {line.strip()}")
        except Exception as e:
            self.log.emit(f"Write error: {e}")

    def _sim_parse_and_update(self, line: str):
        """Parse a G-code line and update simulated position (absolute coords)."""
        # Handle both normal G-code (G0/G1 X.. Y.. Z..) and jog ($J=...)
        text = line
        if text.upper().startswith("$J="):
            text = text[3:]  # strip '$J=' prefix

        m_x = re.search(r'[Xx]([\-+]?\d*\.?\d+)', text)
        m_y = re.search(r'[Yy]([\-+]?\d*\.?\d+)', text)
        m_z = re.search(r'[Zz]([\-+]?\d*\.?\d+)', text)
        if m_x:
            self._sim_x = float(m_x.group(1))
        if m_y:
            self._sim_y = float(m_y.group(1))
        if m_z:
            self._sim_z = float(m_z.group(1))

    def send_reset(self):
        self._write_raw(b"\x18")
        self.log.emit("> [CTRL+X reset]")

    def jog_cancel(self):
        self._write_raw(b"\x85")
        self.log.emit("> [JOG CANCEL 0x85]")

    def estop(self):
        self._write_raw(b"!")
        time.sleep(0.05)
        self._write_raw(b"\x18")
        self.log.emit("> [E-STOP: HOLD ! + CTRL+X]")

    def stop_run_estop(self):
        self._write_raw(b"!")
        time.sleep(0.05)
        try:
            self.send_line("M5")
        except Exception:
            pass
        self._write_raw(b"\x18")
        time.sleep(0.1)
        self._stop_stream_internal("idle")
        self.log.emit("> [STOP RUN: E-STOP style (! + M5 + CTRL+X) + clear stream]")

    # ---- Streaming ----
    def start_stream(self, gcode_lines: list[str]):
        if not self._is_sim and (not self.ser or not self.ser.is_open):
            self.stream_state.emit("error")
            self.log.emit("Stream error: not connected")
            return

        self._mutex.lock()
        try:
            self._stream_queue.clear()
            idx = 0
            for ln in gcode_lines:
                ln = ln.strip()
                if not ln or ln.startswith(";") or ln.startswith("("):
                    continue
                self._stream_queue.append((idx, ln))
                idx += 1
            self._streaming = True
            self._stream_paused = False
            self._awaiting_ok = False
            self._current_stream_idx = -1
            self._stream_total = idx
            self._stream_done = 0
        finally:
            self._mutex.unlock()

        self.stream_state.emit("running")
        self.stream_progress.emit(0, self._stream_total)
        self.log.emit(f"Streaming started ({self._stream_total} lines)")

    def pause_stream(self):
        if not self._streaming:
            return
        self._stream_paused = True
        self._write_raw(b"!")
        self.stream_state.emit("paused")
        self.log.emit("> [HOLD !]")

    def resume_stream(self):
        if not self._streaming:
            return
        self._stream_paused = False
        self._write_raw(b"~")
        self.stream_state.emit("running")
        self.log.emit("> [RESUME ~]")

    def _stop_stream_internal(self, final_state: str):
        self._mutex.lock()
        try:
            self._stream_queue.clear()
            self._streaming = False
            self._stream_paused = False
            self._awaiting_ok = False
        finally:
            self._mutex.unlock()
        self.stream_state.emit(final_state)

    def _maybe_send_next_stream_line(self):
        if not self._streaming or self._stream_paused or self._awaiting_ok:
            return

        self._mutex.lock()
        try:
            if not self._stream_queue:
                self._streaming = False
                self._stream_paused = False
                self._awaiting_ok = False
                should_finish = True
            else:
                idx, ln = self._stream_queue.popleft()
                self._awaiting_ok = True
                self._current_stream_idx = idx
                should_finish = False
        finally:
            self._mutex.unlock()

        if should_finish:
            self.stream_state.emit("done")
            self.log.emit("Streaming done")
            return

        self.line_sent.emit(idx, ln)
        self.send_line(ln)

    # ---- Thread loop ----
    def run(self):
        self._running = True
        while self._running:
            # --- Simulator bypass ---
            if self._is_sim:
                self._run_sim_tick()
                time.sleep(self.poll_interval_ms / 1000.0)
                continue

            if not self.ser or not self.ser.is_open:
                time.sleep(0.1)
                continue

            if time.time() < self._alarm_pause_until:
                time.sleep(0.05)
                continue

            try:
                self.ser.write(b"?")
            except Exception:
                time.sleep(0.1)
                continue

            try:
                data = self.ser.read(4096)
                if data:
                    text = data.decode("ascii", errors="ignore")
                    for line in text.splitlines():
                        line = line.strip()
                        if not line:
                            continue

                        if line.startswith("<") and line.endswith(">"):
                            state = extract_state(line)
                            wpos = None
                            mpos = None
                            wpos_str = extract_field(line, "WPos")
                            mpos_str = extract_field(line, "MPos")
                            if wpos_str:
                                wpos = parse_xyz(wpos_str)
                            if mpos_str:
                                mpos = parse_xyz(mpos_str)
                            if wpos is None and mpos is not None:
                                wpos = mpos
                            if wpos:
                                pn_str = extract_field(line, "Pn")
                                payload = {"state": state, "wpos": wpos, "mpos": mpos, "pn": pn_str or "", "raw": line}
                                self._last_status = payload
                                self.status.emit(payload)

                        elif line.lower().startswith("ok"):
                            self.log.emit("ok")
                            if self._streaming:
                                self._mutex.lock()
                                try:
                                    self._awaiting_ok = False
                                    ack_idx = self._current_stream_idx
                                    self._stream_done += 1
                                    done, total = self._stream_done, self._stream_total
                                finally:
                                    self._mutex.unlock()
                                self.line_ack.emit(ack_idx)
                                self.stream_progress.emit(done, total)
                                self._maybe_send_next_stream_line()

                        elif line.startswith("error") or line.startswith("ALARM"):
                            self.log.emit(line)
                            if line.startswith("ALARM"):
                                self.alarm.emit(line)
                                self._alarm_pause_until = time.time() + 2.0
                            if self._streaming:
                                self.line_error_at.emit(self._current_stream_idx, line)
                                self._stop_stream_internal("error")
                        elif re.match(r'^\$\d+=', line):
                            self.grbl_param_line.emit(line)
                            self.log.emit(line)
                        else:
                            if line.startswith("Grbl ") or line.startswith("GrblHAL"):
                                self.grbl_reset.emit()
                            self.log.emit(line)

            except Exception as e:
                self.log.emit(f"Read error: {e}")

            if self._streaming and not self._stream_paused:
                self._maybe_send_next_stream_line()

            time.sleep(self.poll_interval_ms / 1000.0)

    def _run_sim_tick(self):
        """One iteration of the simulator loop: emit fake status and process queued commands."""
        # Determine state
        sim_state = "Run" if (self._streaming and not self._stream_paused) else "Idle"
        raw = f"<{sim_state}|WPos:{self._sim_x:.3f},{self._sim_y:.3f},{self._sim_z:.3f}|MPos:{self._sim_x:.3f},{self._sim_y:.3f},{self._sim_z:.3f}>"
        wpos = (self._sim_x, self._sim_y, self._sim_z)
        mpos = (self._sim_x, self._sim_y, self._sim_z)
        payload = {"state": sim_state, "wpos": wpos, "mpos": mpos, "pn": "", "raw": raw}
        self._last_status = payload
        self.status.emit(payload)

        # Process queued commands (simulate "ok" responses)
        if self._sim_queue:
            self._sim_queue.popleft()
            time.sleep(0.05)  # simulate processing delay
            self.log.emit("ok")
            if self._streaming:
                self._mutex.lock()
                try:
                    self._awaiting_ok = False
                    ack_idx = self._current_stream_idx
                    self._stream_done += 1
                    done, total = self._stream_done, self._stream_total
                finally:
                    self._mutex.unlock()
                self.line_ack.emit(ack_idx)
                self.stream_progress.emit(done, total)
                self._maybe_send_next_stream_line()

        # Also try to push the next stream line if we're streaming
        if self._streaming and not self._stream_paused:
            self._maybe_send_next_stream_line()

    def last_wpos(self):
        return self._last_status["wpos"] if self._last_status else None
