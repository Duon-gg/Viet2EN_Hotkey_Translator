"""Viet2EN desktop application entry point."""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
import tkinter as tk

import keyboard
from PIL import ImageGrab

from utils import config

config.load_config()
config.configure_runtime_environment()

from core import browser_bridge, clipboard, engine, ocr, uiautomation_reader  # noqa: E402
from ui import ocr_selector, settings, tray  # noqa: E402
from utils.logging_setup import configure_logging  # noqa: E402

LOGGER = configure_logging()


class Viet2ENApplication:
    def __init__(self) -> None:
        self.root: tk.Tk | None = None
        self._mutex_handle = 0
        self._translation_lock = threading.Lock()
        self._quitting = False

    def acquire_single_instance(self) -> bool:
        kernel32 = ctypes.windll.kernel32
        self._mutex_handle = int(kernel32.CreateMutexW(None, False, "Viet2EN_Translator_Mutex_Lock"))
        return kernel32.GetLastError() != 183

    def apply_hotkeys(self) -> None:
        keyboard.unhook_all()
        if not tray.is_enabled:
            return
        hotkey = str(config.config.get("hotkey", "f2")).strip().lower()
        try:
            keyboard.add_hotkey(hotkey, lambda: self.translate_action(None), suppress=True)
            if "+" not in hotkey:
                keyboard.add_hotkey(f"ctrl+{hotkey}", lambda: self.translate_action("vi_en"), suppress=True)
                keyboard.add_hotkey(f"shift+{hotkey}", lambda: self.translate_action("en_vi"), suppress=True)
        except Exception as exc:
            LOGGER.exception("Unable to register hotkey %s", hotkey)
            tray.notify("Viet2EN", f"Hotkey không hợp lệ: {exc}")

    def toggle_enable(self, _enabled: bool) -> None:
        self.apply_hotkeys()

    def on_engine_status_change(self) -> None:
        if self.root:
            try:
                self.root.after(0, tray.update_tray_state)
            except tk.TclError:
                pass

    def open_settings(self, *_args) -> None:
        root = self.root
        if root:
            root.after(0, lambda: settings.open_settings_window(root, self.settings_saved))

    def settings_saved(self) -> None:
        self.apply_hotkeys()
        browser_bridge.BRIDGE.stop()
        browser_bridge.BRIDGE.start()
        engine.SERVICE.unload()
        engine.preload_async()
        tray.update_tray_state()

    @staticmethod
    def _translate_preserving_whitespace(text: str, direction: str | None) -> str:
        leading, body, trailing = clipboard.smart_strip(text)
        translated = engine.translate_text(body, direction)
        return leading + translated.strip() + trailing

    def _translate_from_browser(self, direction: str | None) -> bool:
        selection = browser_bridge.BRIDGE.extract_selection()
        if selection is None:
            return False
        translated = self._translate_preserving_whitespace(selection.text, direction)
        if not translated or translated.strip() == selection.text.strip():
            tray.notify("Viet2EN", "Bản dịch không thay đổi")
            return True
        if not browser_bridge.BRIDGE.apply_translation(selection, translated):
            clipboard.safe_copy(translated)
        return True

    def _translate_from_uia(self, direction: str | None) -> bool:
        selection = uiautomation_reader.extract_selected_text()
        if selection is None:
            return False
        # Capture the target before model inference. A cold translation can take
        # several seconds, so pasting must be rejected if the user moved away.
        focus = clipboard.FocusContext.capture()
        translated = self._translate_preserving_whitespace(selection.text, direction)
        if not translated or translated.strip() == selection.text.strip():
            tray.notify("Viet2EN", "Bản dịch không thay đổi")
            return True

        clipboard_selection = clipboard.ClipboardSelection(selection.text, focus)
        if not uiautomation_reader.selection_is_still_focused(selection) or not clipboard.paste_translation(
            clipboard_selection, translated
        ):
            clipboard.safe_copy(translated)
        return True

    def _translation_pipeline(self, direction: str | None) -> bool:
        try:
            if self._translate_from_browser(direction):
                return True
        except Exception:
            LOGGER.exception("Browser translation path failed")

        try:
            if self._translate_from_uia(direction):
                return True
        except Exception:
            LOGGER.exception("UI Automation translation path failed")

        return clipboard.execute_translation_cycle(
            lambda text: engine.translate_text(text, direction),
            tray.notify,
        )

    def translate_action(self, direction: str | None) -> None:
        if not tray.is_enabled or not self._translation_lock.acquire(blocking=False):
            return
        tray.set_translating_state(True)

        def worker() -> None:
            success = False
            try:
                success = self._translation_pipeline(direction)
            except Exception as exc:
                LOGGER.exception("Translation pipeline failed")
                tray.notify("Viet2EN", f"Lỗi dịch: {str(exc)[:90]}")
            finally:
                tray.set_translating_state(False)
                self._translation_lock.release()
            if not success and config.config.get("ocr_enabled", True):
                self.request_ocr()

        threading.Thread(target=worker, name="viet2en-translation", daemon=True).start()

    def request_ocr(self, *_args) -> None:
        root = self.root
        if not root or not config.config.get("ocr_enabled", True):
            tray.notify("Viet2EN OCR", "OCR đang tắt trong Settings")
            return
        root.after(0, lambda: ocr_selector.select_screen_region(root, self._run_ocr_region))

    def _run_ocr_region(self, bbox: tuple[int, int, int, int]) -> None:
        def worker() -> None:
            try:
                image = ImageGrab.grab(bbox=bbox, all_screens=True)
                result = ocr.SERVICE.extract(image)
                if result is None:
                    tray.notify("Viet2EN OCR", "Không nhận diện được văn bản trong vùng đã chọn")
                    return
                translated = self._translate_preserving_whitespace(result.text, None)
                clipboard.safe_copy(translated)
            except Exception as exc:
                LOGGER.exception("OCR flow failed")
                tray.notify("Viet2EN OCR", f"Lỗi OCR: {str(exc)[:90]}")

        threading.Thread(target=worker, name="viet2en-ocr", daemon=True).start()

    def quit(self, *_args) -> None:
        if self._quitting:
            return
        self._quitting = True
        LOGGER.info("Viet2EN is shutting down")
        try:
            keyboard.unhook_all()
            browser_bridge.BRIDGE.stop()
            engine.shutdown()
            ocr.SERVICE.unload()
            if tray.tray_icon:
                tray.tray_icon.stop()
        finally:
            if self._mutex_handle:
                ctypes.windll.kernel32.CloseHandle(self._mutex_handle)
                self._mutex_handle = 0
            if self.root:
                try:
                    self.root.quit()
                    self.root.destroy()
                except tk.TclError:
                    pass

    def run(self) -> int:
        if not self.acquire_single_instance():
            return 0

        LOGGER.info("Starting Viet2EN Translator")
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

        engine.set_status_callback(self.on_engine_status_change)
        tray.run_tray(self.toggle_enable, self.open_settings, self.request_ocr, self.quit)
        browser_bridge.BRIDGE.start()
        self.apply_hotkeys()

        models_ok = engine.check_models_installed_on_disk()
        if config.config.get("model_installed") != models_ok:
            config.config["model_installed"] = models_ok
            config.save_config()
        if models_ok:
            engine.preload_async()
            tray.notify("Viet2EN", f"Sẵn sàng — nhấn {str(config.config['hotkey']).upper()} để dịch")
        else:
            self.root.after(500, self.open_settings)

        try:
            self.root.mainloop()
        finally:
            self.quit()
        return 0


def main() -> int:
    app = Viet2ENApplication()
    return app.run()


def _log_unhandled(exc_type, exc_value, exc_traceback) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.getLogger("viet2en").critical(
        "Unhandled exception",
        exc_info=(exc_type, exc_value, exc_traceback),
    )


if __name__ == "__main__":
    sys.excepthook = _log_unhandled
    raise SystemExit(main())
