"""ZorinCare Pro — System Optimizer, Driver Booster, Deep Uninstaller & PC Control Center."""

from pathlib import Path
import os

APP_ID = "com.zorincare.pro"
APP_NAME = "ZorinCare Pro"
APP_VERSION = "1.0.0"

def get_config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else (Path.home() / ".config")
    path = base / "zorincare-pro"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return path

def get_data_dir() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else (Path.home() / ".local" / "share")
    path = base / "zorincare-pro"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return path

def get_backup_dir() -> Path:
    bdir = get_data_dir() / "backups"
    try:
        bdir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return bdir
