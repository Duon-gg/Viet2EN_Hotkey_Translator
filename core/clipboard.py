"""Safe Windows clipboard transactions for select → translate → replace."""

from __future__ import annotations

import copy
import ctypes
import logging
import re
import time
import uuid
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any

import keyboard
import pyperclip

from utils import config

LOGGER = logging.getLogger("viet2en.clipboard")

try:
    import win32clipboard
    import win32con
except ImportError:  # pragma: no cover - only used by source installs missing pywin32
    win32clipboard = None
    win32con = None


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


@dataclass(frozen=True)
class FocusContext:
    foreground_window: int
    focused_control: int
    process_id: int

    @classmethod
    def capture(cls) -> FocusContext:
        user32 = ctypes.windll.user32
        foreground = int(user32.GetForegroundWindow() or 0)
        process_id = wintypes.DWORD()
        thread_id = user32.GetWindowThreadProcessId(foreground, ctypes.byref(process_id))
        info = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
        focused = 0
        if thread_id and user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
            focused = int(info.hwndFocus or info.hwndCaret or 0)
        return cls(foreground, focused, int(process_id.value))

    def is_current(self) -> bool:
        current = FocusContext.capture()
        if current.foreground_window != self.foreground_window:
            return False
        if self.focused_control and current.focused_control:
            return current.focused_control == self.focused_control
        return current.process_id == self.process_id


@dataclass
class ClipboardSnapshot:
    formats: list[tuple[int, Any]]
    fallback_text: str = ""

    @classmethod
    def capture(cls) -> ClipboardSnapshot:
        if win32clipboard is None:
            return cls([], safe_paste())

        formats: list[tuple[int, Any]] = []
        if not _open_clipboard():
            return cls([], safe_paste())
        try:
            clipboard_format = 0
            while True:
                clipboard_format = win32clipboard.EnumClipboardFormats(clipboard_format)
                if not clipboard_format:
                    break
                try:
                    data = win32clipboard.GetClipboardData(clipboard_format)
                    if isinstance(data, (str, bytes, tuple, list, float, bool)):
                        formats.append((clipboard_format, copy.deepcopy(data)))
                    elif isinstance(data, int) and clipboard_format in {
                        getattr(win32con, "CF_LOCALE", -1),
                    }:
                        formats.append((clipboard_format, data))
                except Exception:
                    LOGGER.debug("Clipboard format %s could not be snapshotted", clipboard_format)
        finally:
            win32clipboard.CloseClipboard()
        return cls(formats, safe_paste())

    def restore(self) -> bool:
        if win32clipboard is None or not self.formats:
            return safe_copy(self.fallback_text)
        if not _open_clipboard():
            return False
        restored = 0
        try:
            win32clipboard.EmptyClipboard()
            for clipboard_format, data in self.formats:
                try:
                    if clipboard_format == win32con.CF_UNICODETEXT and isinstance(data, str):
                        win32clipboard.SetClipboardText(data, win32con.CF_UNICODETEXT)
                    else:
                        win32clipboard.SetClipboardData(clipboard_format, data)
                    restored += 1
                except Exception:
                    LOGGER.debug("Clipboard format %s could not be restored", clipboard_format)
        finally:
            win32clipboard.CloseClipboard()
        if not restored and self.fallback_text:
            return safe_copy(self.fallback_text)
        return restored > 0


@dataclass(frozen=True)
class ClipboardSelection:
    text: str
    focus: FocusContext


def _open_clipboard(max_retries: int = 12, delay: float = 0.025) -> bool:
    if win32clipboard is None:
        return False
    for _ in range(max_retries):
        try:
            win32clipboard.OpenClipboard()
            return True
        except Exception:
            time.sleep(delay)
    return False


def clipboard_sequence_number() -> int:
    if win32clipboard is not None:
        try:
            return int(win32clipboard.GetClipboardSequenceNumber())
        except Exception:
            pass
    return int(ctypes.windll.user32.GetClipboardSequenceNumber())


def safe_paste(max_retries: int = 5, delay: float = 0.04) -> str:
    for attempt in range(max_retries):
        try:
            value = pyperclip.paste()
            return value if isinstance(value, str) else str(value)
        except Exception as exc:
            if attempt == max_retries - 1:
                LOGGER.warning("Unable to read clipboard: %s", exc)
                return ""
            time.sleep(delay)
    return ""


def safe_copy(text: str, max_retries: int = 5, delay: float = 0.04) -> bool:
    for attempt in range(max_retries):
        try:
            pyperclip.copy(text)
            return True
        except Exception as exc:
            if attempt == max_retries - 1:
                LOGGER.warning("Unable to write clipboard: %s", exc)
                return False
            time.sleep(delay)
    return False


def wait_for_sequence_change(sequence: int, timeout: float, interval: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if clipboard_sequence_number() != sequence:
            return True
        time.sleep(interval)
    return False


def smart_strip(text: str) -> tuple[str, str, str]:
    match = re.match(r"^(\s*)(.*?)(\s*)$", text, re.DOTALL)
    if match:
        return match.group(1), match.group(2), match.group(3)
    return "", text, ""


def acquire_selected_text() -> ClipboardSelection | None:
    """Copy selection without leaving the user's clipboard modified."""
    original = ClipboardSnapshot.capture()
    focus = FocusContext.capture()
    sentinel = f"__VIET2EN_{uuid.uuid4().hex}__"
    if not safe_copy(sentinel):
        return None
    sentinel_sequence = clipboard_sequence_number()

    keyboard.send("ctrl+c")
    timeout = float(config.config.get("clipboard_timeout_seconds", 1.2))
    if not wait_for_sequence_change(sentinel_sequence, timeout):
        if clipboard_sequence_number() == sentinel_sequence:
            original.restore()
        return None

    copied_sequence = clipboard_sequence_number()
    selected_text = safe_paste()
    if clipboard_sequence_number() == copied_sequence:
        original.restore()

    if not selected_text or selected_text == sentinel or not selected_text.strip():
        return None
    return ClipboardSelection(selected_text, focus)


def paste_translation(selection: ClipboardSelection, translated: str) -> bool:
    """Paste once, only into the original focused control, then restore clipboard safely."""
    if not selection.focus.is_current():
        safe_copy(translated)
        return False

    before_paste = ClipboardSnapshot.capture()
    if not safe_copy(translated):
        return False
    translation_sequence = clipboard_sequence_number()
    keyboard.send("ctrl+v")
    time.sleep(float(config.config.get("restore_delay_seconds", 0.35)))

    # If another application or the user changed the clipboard, preserve that newer value.
    if clipboard_sequence_number() == translation_sequence:
        before_paste.restore()
    return True


def execute_translation_cycle(
    engine_translate_func: Callable[[str], str],
    on_status_notify: Callable[[str, str], None],
) -> bool:
    """Clipboard fallback used when browser DOM and UI Automation are unavailable."""
    selection = acquire_selected_text()
    if selection is None:
        on_status_notify(
            "Viet2EN",
            "Không lấy được vùng chọn bằng clipboard; đang cần UI Automation, extension hoặc OCR.",
        )
        return False

    leading, text_to_translate, trailing = smart_strip(selection.text)
    try:
        translated = engine_translate_func(text_to_translate)
    except Exception as exc:
        LOGGER.exception("Translation failed")
        on_status_notify("Viet2EN", f"Lỗi dịch: {str(exc)[:90]}")
        return False

    if not translated or translated.strip() == text_to_translate:
        on_status_notify("Viet2EN", "Kết quả không thay đổi; nội dung có thể không thuộc VI/EN.")
        return False

    final_text = leading + translated.strip() + trailing
    if not paste_translation(selection, final_text):
        on_status_notify(
            "Viet2EN",
            "Bạn đã đổi vị trí nhập. Bản dịch được giữ trong clipboard thay vì dán nhầm.",
        )
        return False
    return True
