import sys
import datetime
sys.stdout = open("viet2en.log", "a", encoding="utf-8")
sys.stderr = sys.stdout
print(f"\n===== Session started: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====", flush=True)
sys.stdout.flush()



import os
import ctypes
import tkinter as tk
import keyboard
import threading

from utils import config
os.environ["ARGOS_PACKAGES_DIR"] = os.path.join(config.APP_DIR, "models")

from core import engine, clipboard
from ui import tray, settings

root = None

def on_status_change():
    """Callback khi engine thay đổi trạng thái (VD: load xong, hoặc bị auto unload)"""
    tray.update_tray_state()

def apply_hotkey():
    """Đăng ký phím tắt hệ thống"""
    keyboard.unhook_all()
    if tray.is_enabled:
        hk = config.config.get("hotkey", "f2").lower()
        keyboard.add_hotkey(hk, translate_action, suppress=True)

def toggle_enable(enabled):
    """Callback khi user bật/tắt dịch trên khay hệ thống"""
    apply_hotkey()

def open_settings():
    """Callback mở bảng settings"""
    if root:
        root.after(0, lambda: settings.open_settings_window(root, apply_hotkey))

def quit_app(icon, item):
    """Thoát ứng dụng"""
    icon.stop()
    if root:
        root.quit()
    os._exit(0)

def translate_action():
    """Hàm bắt sự kiện khi bấm phím tắt"""
    if tray.is_translating or not tray.is_enabled:
        return
        
    tray.set_translating_state(True)
    
    def _run():
        try:
            clipboard.execute_translation_cycle(engine.translate_text, tray.notify)
        finally:
            tray.set_translating_state(False)
            
    threading.Thread(target=_run, daemon=True).start()

def main():
    # [Chống chạy nhiều instance]
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, "Viet2EN_Translator_Mutex_Lock")
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)

    global root
    config.load_config()

    # Đăng ký callback cho engine
    engine.set_status_callback(on_status_change)
    
    print("[...] Đang khởi động Viet2EN Translator (Offline)...")
    
    # Không load model ngay lập tức (Lazy Load) -> Khởi động rất nhanh
    
    apply_hotkey()

    root = tk.Tk()
    root.withdraw()

    # Chạy system tray
    tray.run_tray(toggle_enable, open_settings, quit_app)

    # Tự động cập nhật trạng thái model_installed dựa trên thực tế đĩa
    models_ok = engine.check_models_installed_on_disk()
    config.config["model_installed"] = models_ok
    config.save_config()

    # Nếu model chưa cài thực tế trên đĩa, tự mở settings
    if not models_ok:
        root.after(500, open_settings)
    else:
        print(f"[OK] Sẵn sàng — nhấn {config.config.get('hotkey', 'f2').upper()} để dịch (Offline)", flush=True)

    root.mainloop()

if __name__ == "__main__":
    main()
