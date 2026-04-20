from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel

from ops.gcode import FigureCanvas, NavigationToolbar, Figure
from core.models import Point
from core.utils import clamp


class Preview3DWindow(QDialog):
    def __init__(self, points: list[Point], safe_z: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preview 3D - Real Motion Path")
        self.resize(1100, 750)

        lay = QVBoxLayout(self)
        if FigureCanvas is None or Figure is None:
            lay.addWidget(QLabel("matplotlib not available. Install with: pip install matplotlib"))
            return

        self.fig = Figure()
        self.canvas = FigureCanvas(self.fig)
        if NavigationToolbar is not None:
            lay.addWidget(NavigationToolbar(self.canvas, self))
        lay.addWidget(self.canvas, 1)

        self.ax = self.fig.add_subplot(111, projection="3d")
        self._draw(points, safe_z)

    def _set_equal_3d(self, ax, xs, ys, zs):
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        minz, maxz = min(zs), max(zs)
        cx, cy, cz = (minx + maxx) / 2, (miny + maxy) / 2, (minz + maxz) / 2
        rx, ry, rz = (maxx - minx) / 2, (maxy - miny) / 2, (maxz - minz) / 2
        r = max(rx, ry, rz, 1e-6) * 1.10
        ax.set_xlim(cx - r, cx + r)
        ax.set_ylim(cy - r, cy + r)
        ax.set_zlim(cz - r, cz + r)

    def _draw(self, points: list[Point], safe_z: float):
        ax = self.ax
        ax.clear()

        if not points or len(points) < 2:
            ax.text(0, 0, 0, "Need >= 2 points", color="red")
            self.canvas.draw_idle()
            return

        x, y, z = points[0].x, points[0].y, points[0].z
        segs = []
        if z != safe_z:
            segs.append(("G0", (x, y, z), (x, y, safe_z)))
            z = safe_z

        for p in points[1:]:
            tx, ty, tz = p.x, p.y, p.z
            if (x, y) != (tx, ty):
                segs.append(("G0", (x, y, safe_z), (tx, ty, safe_z)))
            if safe_z != tz:
                segs.append(("G1", (tx, ty, safe_z), (tx, ty, tz)))
            x, y, z = tx, ty, tz
            if z != safe_z:
                segs.append(("G0", (x, y, z), (x, y, safe_z)))
                z = safe_z

        for kind, p0, p1 in segs:
            x0, y0, z0 = p0
            x1, y1, z1 = p1
            ax.plot([x0, x1], [y0, y1], [z0, z1],
                    linestyle="--" if kind == "G0" else "-")

        xs = [p.x for p in points]
        ys = [p.y for p in points]
        zs = [p.z for p in points]
        ax.scatter(xs, ys, zs, marker="o")
        for i, p in enumerate(points, start=1):
            ax.text(p.x, p.y, p.z, f"{i}", fontsize=9)

        ax.set_xlabel("X (mm)")
        ax.set_ylabel("Y (mm)")
        ax.set_zlabel("Z (mm)")
        ax.set_title("G1 = solid, G0 = dashed (Real motion preview)")
        self._set_equal_3d(ax, xs, ys, zs + [safe_z])
        self.canvas.draw_idle()
