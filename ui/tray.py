"""System tray UI."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from core import browser_bridge, engine
from utils import config

LOGGER = logging.getLogger("viet2en.tray")
tray_icon: pystray.Icon | None = None
is_translating = False
is_enabled = True
_state_lock = threading.RLock()
ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "icon-v2.ico"


def create_image(is_busy: bool = False) -> Image.Image:
    try:
        image = Image.open(ICON_PATH).convert("RGBA")
    except Exception:
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((4, 4, 60, 60), radius=10, fill=(44, 62, 80))
        draw.text((18, 24), "V>E", fill="white")
    if is_busy:
        draw = ImageDraw.Draw(image)
        width, _height = image.size
        radius = max(4, int(width * 0.15))
        draw.ellipse((width - 2 * radius - 2, 2, width - 2, 2 * radius + 2), fill=(230, 81, 0, 255))
    return image


def update_tray_state() -> None:
    with _state_lock:
        icon = tray_icon
        enabled = is_enabled
        translating = is_translating
    if icon is None:
        return
    try:
        status = engine.get_status()
        state_labels = {
            "unloaded": "ngủ",
            "loading": "đang nạp",
            "ready": "sẵn sàng",
            "translating": "đang dịch",
            "installing": "đang cài",
            "error": "lỗi",
        }
        bridge_status = "browser ✓" if browser_bridge.BRIDGE.connected else "browser –"
        enabled_label = "bật" if enabled else "tắt"
        hotkey = str(config.config.get("hotkey", "f2")).upper()
        icon.title = (
            f"Viet2EN [{enabled_label}] • {hotkey} • "
            f"model {state_labels.get(str(status['state']), status['state'])} • {bridge_status}"
        )
        icon.icon = create_image(translating)
    except Exception:
        LOGGER.exception("Unable to update tray state")


def notify(title: str, message: str) -> None:
    if tray_icon:
        try:
            tray_icon.notify(message, title)
        except Exception:
            LOGGER.exception("Unable to show tray notification")


def set_translating_state(state: bool) -> None:
    global is_translating
    with _state_lock:
        is_translating = state
    update_tray_state()


def run_tray(
    toggle_callback: Callable[[bool], None],
    settings_callback: Callable[..., None],
    ocr_callback: Callable[..., None],
    quit_callback: Callable[..., None],
) -> pystray.Icon:
    global tray_icon, is_enabled

    def on_toggle(_icon, _item) -> None:
        global is_enabled
        with _state_lock:
            is_enabled = not is_enabled
            enabled = is_enabled
        toggle_callback(enabled)
        update_tray_state()

    menu = pystray.Menu(
        pystray.MenuItem("Bật dịch", on_toggle, checked=lambda _item: is_enabled),
        pystray.MenuItem("Dịch vùng màn hình (OCR)", ocr_callback),
        pystray.MenuItem("Cài đặt", settings_callback),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Thoát", quit_callback),
    )
    hotkey = str(config.config.get("hotkey", "f2")).upper()
    tray_icon = pystray.Icon(
        "Viet2EN",
        create_image(False),
        f"Viet2EN • {hotkey} • đang khởi động",
        menu,
    )
    threading.Thread(target=tray_icon.run, name="viet2en-tray", daemon=True).start()
    update_tray_state()
    return tray_icon
