from dataclasses import dataclass


@dataclass
class Segment:
    kind: str  # "G0" or "G1"
    x0: float; y0: float; z0: float
    x1: float; y1: float; z1: float


@dataclass
class Point:
    name: str
    x: float; y: float; z: float
    feed_to_next: int = 1000
    laser_time_s: float = 0.0
