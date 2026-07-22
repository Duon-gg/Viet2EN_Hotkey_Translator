"""Configuration, data-directory, and Windows startup helpers."""

from __future__ import annotations

import copy
import json
import os
import secrets
import sys
import tempfile
import winreg
from pathlib import Path
from typing import Any

APP_NAME = "Vitra"
LEGACY_APP_NAME = "Viet2EN"
STARTUP_APP_NAME = "Vitra_Translator"
LEGACY_STARTUP_APP_NAME = "Viet2EN_Translator"


def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_NAME
    return get_app_dir() / ".vitra-data"


def get_legacy_data_dir() -> Path | None:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / LEGACY_APP_NAME
    return None


APP_DIR = get_app_dir()
DATA_DIR = get_data_dir()
LEGACY_DATA_DIR = get_legacy_data_dir()
MODEL_DIR = APP_DIR / "models"
CONFIG_FILE = DATA_DIR / "config.json"
LEGACY_CONFIG_FILE = APP_DIR / "config.json"
LEGACY_DATA_CONFIG_FILE = LEGACY_DATA_DIR / "config.json" if LEGACY_DATA_DIR is not None else None
LOG_FILE = DATA_DIR / "logs" / "vitra.log"

DEFAULT_CONFIG: dict[str, Any] = {
    "hotkey": "f2",
    "direction": "auto",
    "startup": False,
    "model_installed": False,
    "performance_mode": "balanced",
    "auto_unload_minutes": 30,
    "restore_delay_seconds": 0.35,
    "clipboard_timeout_seconds": 1.2,
    "compute_type": "auto",
    "device": "cpu",
    "browser_bridge_enabled": True,
    "browser_bridge_port": 8765,
    "browser_bridge_token": "",
    "browser_extract_timeout_seconds": 0.45,
    "uiautomation_enabled": True,
    "ocr_enabled": True,
    "ocr_min_confidence": 0.45,
    "normalize_accentless_vietnamese": True,
    "glossary": {},
}

config: dict[str, Any] = {}


def _clamp_number(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, result))


def _validated(raw: dict[str, Any] | None) -> dict[str, Any]:
    result = copy.deepcopy(DEFAULT_CONFIG)
    if isinstance(raw, dict):
        result.update(raw)

    hotkey = str(result.get("hotkey", "f2")).strip().lower()
    result["hotkey"] = hotkey if 1 <= len(hotkey) <= 50 else "f2"

    if result.get("direction") not in {"auto", "vi_en", "en_vi"}:
        result["direction"] = "auto"
    if result.get("performance_mode") not in {"performance", "balanced", "low_memory"}:
        result["performance_mode"] = "balanced"
    if result.get("compute_type") not in {"auto", "default", "int8", "int8_float32", "float32", "float16"}:
        result["compute_type"] = "auto"
    if result.get("device") not in {"cpu", "cuda", "auto"}:
        result["device"] = "cpu"

    result["startup"] = bool(result.get("startup", False))
    result["model_installed"] = bool(result.get("model_installed", False))
    result["browser_bridge_enabled"] = bool(result.get("browser_bridge_enabled", True))
    result["uiautomation_enabled"] = bool(result.get("uiautomation_enabled", True))
    result["ocr_enabled"] = bool(result.get("ocr_enabled", True))
    result["normalize_accentless_vietnamese"] = bool(result.get("normalize_accentless_vietnamese", True))

    result["auto_unload_minutes"] = int(_clamp_number(result.get("auto_unload_minutes"), 30, 1, 24 * 60))
    result["restore_delay_seconds"] = _clamp_number(result.get("restore_delay_seconds"), 0.35, 0.05, 5.0)
    result["clipboard_timeout_seconds"] = _clamp_number(
        result.get("clipboard_timeout_seconds"), 1.2, 0.2, 10.0
    )
    result["browser_extract_timeout_seconds"] = _clamp_number(
        result.get("browser_extract_timeout_seconds"), 0.45, 0.1, 3.0
    )
    result["ocr_min_confidence"] = _clamp_number(result.get("ocr_min_confidence"), 0.45, 0.0, 1.0)
    result["browser_bridge_port"] = int(_clamp_number(result.get("browser_bridge_port"), 8765, 1024, 65535))

    token = str(result.get("browser_bridge_token", "")).strip()
    result["browser_bridge_token"] = token if len(token) >= 24 else secrets.token_urlsafe(32)

    glossary = result.get("glossary", {})
    if not isinstance(glossary, dict):
        glossary = {}
    result["glossary"] = {
        str(source).strip(): str(target).strip()
        for source, target in glossary.items()
        if str(source).strip() and str(target).strip()
    }
    return result


def load_config() -> dict[str, Any]:
    """Load, migrate, validate, and persist the application configuration."""
    global config

    source: Path | None = None
    if CONFIG_FILE.exists():
        source = CONFIG_FILE
    elif LEGACY_DATA_CONFIG_FILE and LEGACY_DATA_CONFIG_FILE.exists():
        source = LEGACY_DATA_CONFIG_FILE
    elif LEGACY_CONFIG_FILE.exists():
        source = LEGACY_CONFIG_FILE

    raw: dict[str, Any] | None = None
    if source:
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[Config] Không thể đọc {source}: {exc}")

    config = _validated(raw)
    try:
        save_config()
    except OSError as exc:
        print(f"[Config] Không thể lưu cấu hình: {exc}")
    return config


def save_config() -> None:
    """Validate and atomically write configuration to LocalAppData."""
    global config
    config = _validated(config)
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(config, indent=4, ensure_ascii=False)

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=CONFIG_FILE.parent,
            prefix="config-",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_file.write(payload)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_path = Path(temp_file.name)
        os.replace(temp_path, CONFIG_FILE)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


def configure_runtime_environment() -> None:
    """Set Argos options before importing argostranslate modules."""
    if not config:
        load_config()
    os.environ["ARGOS_PACKAGES_DIR"] = str(MODEL_DIR)
    os.environ["ARGOS_COMPUTE_TYPE"] = str(config.get("compute_type", "auto"))
    device = str(config.get("device", "cpu"))
    os.environ["ARGOS_DEVICE_TYPE"] = "cpu" if device == "auto" else device


def set_startup(enable: bool) -> bool:
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            key_path,
            0,
            winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE,
        ) as registry_key:
            if enable:
                if getattr(sys, "frozen", False):
                    command = f'"{sys.executable}"'
                else:
                    command = f'wscript.exe "{APP_DIR / "run.vbs"}"'
                winreg.SetValueEx(registry_key, STARTUP_APP_NAME, 0, winreg.REG_SZ, command)
                try:
                    winreg.DeleteValue(registry_key, LEGACY_STARTUP_APP_NAME)
                except FileNotFoundError:
                    pass
            else:
                for app_name in (STARTUP_APP_NAME, LEGACY_STARTUP_APP_NAME):
                    try:
                        winreg.DeleteValue(registry_key, app_name)
                    except FileNotFoundError:
                        pass
        return True
    except OSError as exc:
        print(f"[Config] Lỗi thiết lập khởi động cùng Windows: {exc}")
        return False
