from models import Segment
from utils import _strip_gcode_line, _parse_words

# Optional: matplotlib
try:
    import matplotlib
    matplotlib.use("QtAgg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
    from matplotlib.figure import Figure
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
except Exception:
    FigureCanvas = NavigationToolbar = Figure = None


def parse_gcode_to_segments(lines: list[str]):
    abs_mode, cur_motion = True, 0
    x = y = z = 0.0
    segs: list[Segment] = []
    first_point = None

    for raw in lines:
        line = _strip_gcode_line(raw)
        if not line:
            continue
        w = _parse_words(line)
        if not w:
            continue

        if w.get("G") == 90:
            abs_mode = True
            continue
        if w.get("G") == 91:
            abs_mode = False
            continue
        if "G" in w and w["G"] in (0, 1):
            cur_motion = w["G"]

        if not any(k in w for k in ("X", "Y", "Z")):
            continue

        x0, y0, z0 = x, y, z
        tx = w.get("X", x0 if abs_mode else 0.0)
        ty = w.get("Y", y0 if abs_mode else 0.0)
        tz = w.get("Z", z0 if abs_mode else 0.0)

        if abs_mode:
            x1, y1, z1 = float(tx), float(ty), float(tz)
        else:
            x1, y1, z1 = x0 + float(tx), y0 + float(ty), z0 + float(tz)

        if (x0, y0, z0) != (x1, y1, z1):
            kind = "G1" if cur_motion == 1 else "G0"
            segs.append(Segment(kind, x0, y0, z0, x1, y1, z1))
            if first_point is None:
                first_point = (x0, y0, z0)
        x, y, z = x1, y1, z1

    if first_point is None:
        first_point = (0.0, 0.0, 0.0)
    return segs, first_point, (x, y, z)
