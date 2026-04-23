import json
from dataclasses import dataclass, asdict, fields as dc_fields
from pathlib import Path


SETTINGS_PATH = Path(__file__).with_name("settings.json")


@dataclass
class AppSettings:
    baud: int = 115200
    status_poll_ms: int = 150
    auto_unlock_after_connect: bool = True
    auto_unlock_after_reset: bool = False
    xmin: float = -1000.0; xmax: float = 1000.0
    ymin: float = -1000.0; ymax: float = 1000.0
    zmin: float = -1000.0; zmax: float = 1000.0
    connection_type: str = "serial"
    ip_address: str = "192.168.1.24"
    tcp_port: int = 8080
    last_port: str = ""
    safe_z: float = 5.0
    theme: str = "dark"
    language: str = "en"


def load_settings() -> AppSettings:
    try:
        if SETTINGS_PATH.exists():
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            known = {f.name for f in dc_fields(AppSettings)}
            return AppSettings(**{k: v for k, v in data.items() if k in known})
    except Exception:
        pass
    return AppSettings()


def save_settings(s: AppSettings) -> bool:
    try:
        SETTINGS_PATH.write_text(json.dumps(asdict(s), indent=2), encoding="utf-8")
        return True
    except Exception:
        return False
