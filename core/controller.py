from pathlib import Path
from typing import List, Tuple, Optional
import json
import time

from PySide6.QtWidgets import QMessageBox, QFileDialog

from core.models import Point
from core.settings import AppSettings
from core.utils import _strip_gcode_line, _parse_words, _read_text
from core.worker import GrblWorker


class CNCController:
    """Controller class for CNC operations, separating business logic from UI."""

    def __init__(self, worker: GrblWorker, settings: AppSettings):
        self.worker = worker
        self.settings = settings
        self.points: List[Point] = []
        self._connected = False
        self._streaming_now = False
        self._alarm_active = False
        self._last_auto_x_time = 0.0
        self._estop_triggered = False
        self._estop_time = 0.0
        self._ui_locked = False  # UI-level lock: blocks movement until user presses Unlock

    # -------- Connection Management --------
    def set_connected(self, connected: bool):
        self._connected = connected
        if connected:
            self._alarm_active = False

    def is_connected(self) -> bool:
        return self._connected

    def set_streaming(self, streaming: bool):
        self._streaming_now = streaming

    def is_streaming(self) -> bool:
        return self._streaming_now

    # -------- Soft Limits --------
    def soft_limits(self) -> Tuple[float, float, float, float, float, float]:
        s = self.settings
        return (s.xmin, s.xmax, s.ymin, s.ymax, s.zmin, s.zmax)

    def _has_meaningful_limits(self) -> bool:
        """Return True if soft limits are set to non-default values."""
        s = self.settings
        return not (s.xmin == -1000.0 and s.xmax == 1000.0 and
                    s.ymin == -1000.0 and s.ymax == 1000.0 and
                    s.zmin == -1000.0 and s.zmax == 1000.0)

    def within_limits(self, x: float, y: float, z: float) -> bool:
        xmin, xmax, ymin, ymax, zmin, zmax = self.soft_limits()
        return (xmin <= x <= xmax) and (ymin <= y <= ymax) and (zmin <= z <= zmax)

    # -------- Jog and Movement --------
    def jog(self, axis: str, delta: float, feed: float) -> bool:
        """Jog the machine by delta in specified axis. Returns True if successful."""
        # Check soft limits only if they are meaningfully configured
        if self._has_meaningful_limits():
            wpos = self.worker.last_wpos()
            if wpos:
                x, y, z = wpos
                nx, ny, nz = x, y, z
                if axis == "X":
                    nx = x + delta
                elif axis == "Y":
                    ny = y + delta
                elif axis == "Z":
                    nz = z + delta
                if not self.within_limits(nx, ny, nz):
                    self.worker.log.emit(
                        f"⚠ Jog blocked: {axis}{delta:+.3f} would exceed soft limits"
                    )
                    return False
            else:
                self.worker.log.emit(
                    "⚠ No position data yet — sending jog anyway (incremental)"
                )

        # Always send the incremental jog command
        self.worker.send_line(f"$J=G91 {axis}{delta:.3f} F{feed}")
        return True

    def move_to_position(self, x: float, y: float, z: float, feed: float) -> bool:
        """Move to absolute position. Returns True if successful."""
        if not self.within_limits(x, y, z):
            return False

        self.worker.send_line("G90")
        self.worker.send_line(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{feed}")
        return True

    # -------- Waypoints Management --------
    def add_point(self, x: float, y: float, z: float, feed: int, laser_time: float,
                  z_safe: float, power: int):
        """Add a new waypoint."""
        idx = len(self.points) + 1
        point = Point(
            name=f"P{idx}",
            x=x, y=y, z=z,
            feed_to_next=feed,
            laser_time_s=laser_time,
            z_safe=z_safe,
            power=power
        )
        self.points.append(point)

    def update_point(self, index: int, x: float, y: float, z: float, feed: int,
                     laser_time: float, z_safe: float, power: int) -> bool:
        """Update existing waypoint. Returns True if successful."""
        if not (0 <= index < len(self.points)):
            return False

        if not self.within_limits(x, y, z):
            return False

        point = self.points[index]
        point.x, point.y, point.z = x, y, z
        point.feed_to_next = feed
        point.laser_time_s = laser_time
        point.z_safe = z_safe
        point.power = power
        return True

    def delete_point(self, index: int) -> bool:
        """Delete waypoint at index. Returns True if successful."""
        if not (0 <= index < len(self.points)):
            return False
        self.points.pop(index)
        return True

    def clear_points(self):
        """Clear all waypoints."""
        self.points.clear()

    def get_points(self) -> List[Point]:
        """Get all waypoints."""
        return self.points.copy()

    def move_to_waypoint(self, index: int, feed: Optional[int] = None) -> bool:
        """Move to waypoint at index. Returns True if successful."""
        if not (0 <= index < len(self.points)):
            return False

        point = self.points[index]
        move_feed = feed if feed is not None else point.feed_to_next

        if not self.within_limits(point.x, point.y, point.z):
            return False

        self.worker.send_line("G90")
        self.worker.send_line(f"G1 X{point.x:.3f} Y{point.y:.3f} Z{point.z:.3f} F{move_feed}")
        return True

    # -------- G-code Generation --------
    def generate_gcode_lines(self, points: List[Point], panel_rows: int = 1,
                           panel_cols: int = 1) -> List[str]:
        """Generate G-code lines for waypoints, optionally as panel."""
        lines = ["G90", "G21", "G54"]  # Absolute mode, mm, coordinate system

        if panel_rows > 1 or panel_cols > 1:
            # Calculate panel offsets
            xs = [p.x for p in points]
            ys = [p.y for p in points]
            step_x = max(xs) - min(xs) if len(xs) > 1 else 50.0
            step_y = max(ys) - min(ys) if len(ys) > 1 else 50.0

            offsets = []
            for row in range(panel_rows):
                for col in range(panel_cols):
                    ox = col * step_x
                    oy = row * step_y
                    offsets.append((row, col, ox, oy))

            lines.extend(self._build_panel_lines(points, offsets))
        else:
            # Single PCB
            for point in points:
                lines.extend(self._point_lines(point))

        return lines

    def _point_lines(self, point: Point, ox: float = 0.0, oy: float = 0.0,
                    label: Optional[str] = None) -> List[str]:
        """Generate G-code lines for a single point."""
        feed = int(point.feed_to_next)
        name = label or point.name
        return [
            f"; {name}",
            f"G0 X{point.x + ox:.3f} Y{point.y + oy:.3f} Z{point.z_safe:.3f}",
            f"G1 Z{point.z:.3f} F{feed}",
            f"M3 S{point.power}",
            f"G4 P{point.laser_time_s:.3f}",
            "M5",
            f"G0 Z{point.z_safe:.3f}",
        ]

    def _build_panel_lines(self, points: List[Point], offsets: List[Tuple[int, int, float, float]]) -> List[str]:
        """Build G-code lines for panel replication."""
        lines = []
        for row, col, ox, oy in offsets:
            lines.append(f"; --- Panel [{row+1},{col+1}] offset X{ox:.3f} Y{oy:.3f} ---")
            for point in points:
                lines.extend(self._point_lines(point, ox, oy, label=f"[{row+1},{col+1}]{point.name}"))
        return lines

    # -------- File Operations --------
    def save_waypoints_json(self, filepath: str):
        """Save waypoints to JSON file."""
        data = [
            {
                "name": p.name,
                "x": p.x, "y": p.y, "z": p.z,
                "z_safe": p.z_safe,
                "feed": p.feed_to_next,
                "time": p.laser_time_s,
                "power": p.power,
            }
            for p in self.points
        ]
        Path(filepath).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_waypoints_json(self, filepath: str) -> bool:
        """Load waypoints from JSON file. Returns True if successful."""
        try:
            data = json.loads(Path(filepath).read_text(encoding="utf-8"))
        except Exception:
            return False

        points = []
        for i, d in enumerate(data):
            try:
                points.append(Point(
                    name=d.get("name", f"P{i+1}"),
                    x=float(d["x"]), y=float(d["y"]), z=float(d["z"]),
                    z_safe=float(d.get("z_safe", -2.0)),
                    feed_to_next=int(d.get("feed", 1200)),
                    laser_time_s=float(d.get("time", 0.0)),
                    power=int(d.get("power", 255)),
                ))
            except Exception:
                return False

        self.points = points
        return True

    def load_points_from_gcode(self, filepath: str, default_feed: int) -> bool:
        """Load waypoints from G-code file. Returns True if successful."""
        points = []
        last_x = last_y = last_z = 0.0
        last_f = default_feed

        for raw in _read_text(filepath):
            line = _strip_gcode_line(raw)
            if not line:
                continue
            w = _parse_words(line)
            if not w:
                continue
            g = w.get("G", None)
            if g in (0, 1):
                x = w.get("X", last_x)
                y = w.get("Y", last_y)
                z = w.get("Z", last_z)
                if "F" in w and w["F"] is not None:
                    last_f = int(w["F"])
                if ("X" in w) or ("Y" in w) or ("Z" in w):
                    idx = len(points) + 1
                    points.append(Point(
                        name=f"P{idx}",
                        x=float(x), y=float(y), z=float(z),
                        feed_to_next=last_f,
                        laser_time_s=0.0
                    ))
                last_x, last_y, last_z = x, y, z

        self.points = points
        return True

    # -------- Alarm and Reset Handling --------
    def handle_alarm(self, alarm_state: str):
        """Handle alarm state changes."""
        self._alarm_active = True

    def handle_grbl_reset(self):
        """Handle GRBL reset event."""
        now = time.time()
        if self._estop_triggered or (now - self._estop_time < 3.0):
            self._estop_triggered = False
            return

        if self._connected and self.settings.auto_unlock_after_reset:
            if now - self._last_auto_x_time > 2.0:
                self._last_auto_x_time = now
                self.worker.send_line("$X")